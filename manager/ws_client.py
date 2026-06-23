import asyncio
import json
import logging
import threading

import websockets

logger = logging.getLogger(__name__)


class CoreClient:
    def __init__(self, host, port, token, on_event, on_state):
        self._host = host
        self._port = port
        self._token = token
        self._on_event = on_event                         # 调用方负责切回 GTK 主线程
        self._on_state = on_state
        self._loop = None
        self._thread = None
        self._ws = None
        self._stop = False
        self._wake = None                                 # asyncio.Event,用于打断重连退避(stop 时唤醒)
        self._connected = False                           # 是否已鉴权连上(供面板停止决策)
        self._subs = set()
        self._pending = {}                                # id -> on_reply
        self._outbox = []                                 # 待发送队列(未连上时暂存,连上后 flush)
        self._outlock = threading.Lock()

    def is_connected(self) -> bool:
        return self._connected

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def subscribe(self, topics):
        self._subs.update(topics)                         # _subs 是订阅的事实来源
        if self._connected:                               # 已连:立即补订新 topic
            self.send({"action": "subscribe", "topics": list(topics)})
        # 未连:连接成功时由 _main 统一按 _subs 发送一次,避免重复 subscribe

    def send(self, msg, on_reply=None):
        # 入队而非直发:未连上/重连中也不丢,连上(hello ok)后统一 flush
        with self._outlock:                               # _pending 与 _outbox 同锁,跨线程一致
            if on_reply and msg.get("id"):
                self._pending[msg["id"]] = on_reply
            self._outbox.append(msg)
        if self._loop:
            self._loop.call_soon_threadsafe(lambda: self._loop.create_task(self._flush()))

    async def _flush(self):
        if self._ws is None or not self._connected:
            return
        with self._outlock:
            pending, self._outbox = self._outbox, []
        for i, m in enumerate(pending):
            try:
                await self._ws.send(json.dumps(m))
            except Exception:
                with self._outlock:                       # 失败:当前 m + 剩余未发的整体放回队首(保序)
                    self._outbox[:0] = pending[i:]
                break

    def _fail_pending(self, code: str) -> None:
        # 把所有待应答回调以 error 兜底触发并清空(连接拆除/停止时调用):
        # 在途请求随连接丢失,面板据此回显失败而非永久等待
        with self._outlock:
            pending, self._pending = self._pending, {}
        for cb in pending.values():
            try:
                cb({"type": "error", "code": code, "message": "connection lost"})
            except Exception:
                pass

    def _run(self):
        asyncio.run(self._main())

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        backoff = 0.5
        while not self._stop:
            had_session = False                           # 本轮是否真正连上过(决定断连是否要兜底 pending)
            try:
                async with websockets.connect(f"ws://{self._host}:{self._port}") as ws:
                    self._ws = ws
                    await ws.send(json.dumps({"id": "hello", "action": "hello", "token": self._token}))
                    ack = json.loads(await ws.recv())
                    if ack.get("type") != "ok":
                        logger.warning("鉴权失败,停止重连")
                        self._on_state("error")
                        self._ws = None
                        await ws.close()
                        # 鉴权失败不无限重连
                        self._on_state("disconnected")
                        return
                    self._connected = True
                    had_session = True
                    logger.info("connected to core at %s:%s", self._host, self._port)
                    self._on_state("connected")
                    backoff = 0.5
                    if self._subs:                        # 每次(重)连重订阅 + flush 暂存的控制消息
                        with self._outlock:
                            self._outbox.insert(0, {"action": "subscribe", "topics": list(self._subs)})
                    await self._flush()
                    async for raw in ws:
                        msg = json.loads(raw)
                        rid = msg.get("id")
                        cb = None
                        if rid is not None and msg.get("type") in ("ok", "error"):
                            with self._outlock:
                                cb = self._pending.pop(rid, None)
                        if cb is not None:
                            cb(msg)
                        else:
                            self._on_event(msg)
            except Exception:
                self._on_state("disconnected")
            finally:
                self._ws = None
                self._connected = False
                if had_session:                           # 连上过又断:在途请求随连接丢失,兜底回调
                    self._fail_pending("disconnected")
            if self._stop:
                break
            try:                                          # 可被 stop() 唤醒的退避等待(替代裸 sleep)
                await asyncio.wait_for(self._wake.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
            backoff = min(backoff * 2, 10)
        self._fail_pending("disconnected")                # 退出循环(stop):清掉所有未应答回调,不留悬挂

    def stop(self):
        self._stop = True
        if self._loop:
            def _wake_and_close():
                if self._wake is not None:               # 唤醒退避中的 sleep,立即退出循环
                    self._wake.set()
                if self._ws is not None:
                    self._loop.create_task(self._ws.close())
            try:
                self._loop.call_soon_threadsafe(_wake_and_close)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)
