import asyncio
import json
import threading
import time

import websockets

from core.hub import Conn, Hub


class CoreServer:
    def __init__(self, hub: Hub, host: str = "127.0.0.1", port: int = 0,
                 heartbeat: float = 2.0, notices=None):
        self._hub = hub
        self._host = host
        self._port = port
        self._heartbeat = heartbeat             # status 心跳广播周期(秒);<=0 关闭
        self._notices = notices or []           # 启动告警(如 config_reset),进入 status.core.notices
        self._hb_task = None
        self._actual_port = None
        self._conns: dict = {}                  # ws -> Conn
        self._tasks: dict = {}                  # topic -> asyncio.Task
        self._loop = None
        self._server = None
        self._started_at = time.time()
        self._stop_event = None
        import core
        self._version = core.__version__                  # 缓存:避免每次心跳 _full_status 再 import

    def actual_port(self) -> int:
        return self._actual_port

    async def serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        try:                                              # 端口回退:占用→交给 OS 选端口
            server = await websockets.serve(self._handler, self._host, self._port)
        except OSError:
            server = await websockets.serve(self._handler, self._host, 0)
        try:
            self._server = server
            self._actual_port = server.sockets[0].getsockname()[1]
            for topic in self._hub.topics():
                if self._hub.is_active(topic):
                    self._start_topic(topic)
            if self._heartbeat > 0:
                self._hb_task = self._loop.create_task(self._heartbeat_loop())
            await self._stop_event.wait()
        finally:
            if self._hb_task:
                self._hb_task.cancel()
            for t in list(self._tasks.values()):
                t.cancel()
            server.close()
            await server.wait_closed()

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(self._heartbeat)
                await self._broadcast_status()
        except asyncio.CancelledError:
            return

    def _start_topic(self, topic: str):
        if topic in self._tasks:
            self._tasks[topic].cancel()
        self._tasks[topic] = self._loop.create_task(self._poll_loop(topic))

    async def _poll_loop(self, topic: str, immediate: bool = False):
        try:
            if not immediate:
                await asyncio.sleep(self._hub.interval(topic))
            while True:
                try:
                    value = self._hub.poll(topic)
                    self._hub.record(topic, value, ts=time.time())
                    await self._push(topic, value)
                except Exception as exc:                 # provider 采集异常:记错,不杀循环
                    self._hub.record(topic, None, ts=time.time(), error=str(exc))
                    await self._broadcast_status()       # 立即让面板看到错误态,不等心跳
                await asyncio.sleep(self._hub.interval(topic))
        except asyncio.CancelledError:
            return

    async def _send_authed(self, frame, topic=None):
        # 向已鉴权(且按 topic 过滤后订阅了的)连接发帧;send 失败的连接就地清理,
        # 不等 recv 循环察觉,避免对死连接反复无效 send
        dead = []
        for ws, conn in list(self._conns.items()):
            if not conn.authed:
                continue
            if topic is not None and topic not in conn.subscriptions:
                continue
            try:
                await ws.send(frame)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._conns.pop(ws, None)

    async def _push(self, topic: str, value):
        frame = json.dumps({"type": "data", "topic": topic, "data": value, "ts": time.time()})
        await self._send_authed(frame, topic=topic)

    def _full_status(self, notices=None) -> dict:
        # core 实时段由 server 组装(port/clients/uptime/version);providers 数组来自 hub
        return {
            "core": {
                "port": self._actual_port,
                "clients": sum(1 for c in self._conns.values() if c.authed),
                "uptime": time.time() - self._started_at,
                "version": self._version,
                "notices": notices if notices is not None else self._notices,
            },
            "providers": self._hub.providers_snapshot(),
        }

    async def _broadcast_status(self):
        frame = json.dumps({"type": "status", "status": self._full_status()})
        await self._send_authed(frame)

    def _apply_effects(self, reply):
        # 由 _handler 在收到 reply 后调用(同一事件循环内)
        for topic in reply.reset_timer:
            # 立即 poll 一次并以新周期重启
            if topic in self._tasks:
                self._tasks[topic].cancel()
            if self._hub.is_active(topic):
                self._tasks[topic] = self._loop.create_task(self._poll_loop(topic, immediate=True))
        # set_provider 改变 enabled:同步启停该 provider 所有 topic
        for topic in self._hub.topics():
            active = self._hub.is_active(topic)
            running = topic in self._tasks and not self._tasks[topic].done()
            if active and not running:
                self._start_topic(topic)
            if not active and running:
                self._tasks[topic].cancel()

    async def _handler(self, ws):
        conn = Conn()
        self._conns[ws] = conn
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"type": "error", "code": "bad_request",
                                              "message": "invalid json"}))
                    continue
                reply = self._hub.handle(conn, msg)
                for out in reply.direct:
                    await ws.send(json.dumps(out))
                if reply.status_request_id is not None:
                    await ws.send(json.dumps({"type": "status", "id": reply.status_request_id,
                                              "status": self._full_status()}))
                if reply.broadcast_status or reply.reset_timer:
                    self._apply_effects(reply)
                if reply.broadcast_status:
                    await self._broadcast_status()
                if reply.shutdown:
                    self._stop_event.set()
                    break
                if reply.close:
                    break
        except websockets.ConnectionClosed:
            pass
        finally:
            self._conns.pop(ws, None)

    async def stop(self) -> None:
        if self._stop_event:
            self._stop_event.set()

    def stop_threadsafe(self) -> None:
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(lambda: self._stop_event.set())
            except RuntimeError:
                pass


def start_in_thread(hub: Hub, host: str = "127.0.0.1", port: int = 0, heartbeat: float = 2.0):
    server = CoreServer(hub, host, port, heartbeat=heartbeat)
    ready = threading.Event()
    error = []                                            # serve 启动失败时把异常带回主线程

    def run():
        async def main():
            ready_task = asyncio.create_task(server.serve())
            # 等 actual_port 就绪后通知
            while server.actual_port() is None:
                if ready_task.done():
                    await ready_task   # serve() 在绑定前就结束 → re-raise 其异常
                    return
                await asyncio.sleep(0.01)
            ready.set()
            await ready_task
        try:
            asyncio.run(main())
        except Exception as exc:                          # 绑定失败等:带回调用方,别让其拿到 port=None
            error.append(exc)
            ready.set()                                   # 立即解除等待,不空等 5s

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    if not ready.wait(timeout=5):
        raise TimeoutError("core server 未在 5s 内就绪")
    if error:
        raise error[0]
    return server, thread, server.actual_port()
