import asyncio
import logging
import os
import signal
import sys
import threading
import time

from core import __version__
from core.config import default_config_path, load_config, save_config
from core.logs import setup_logging
from core.hub import Hub
from core.providers.system import SystemProvider
from core.providers.time import TimeProvider
from core.server import CoreServer
from core.state import (
    acquire_instance_lock,
    default_state_dir,
    generate_token,
    read_runtime,
    remove_runtime,
    write_runtime,
)

logger = logging.getLogger(__name__)


def build_hub(config, token: str, on_change=None) -> Hub:
    return Hub([SystemProvider(), TimeProvider()], config, token, on_change=on_change)


def main(argv=None) -> int:
    state_dir = default_state_dir()
    lock_path = state_dir / "core.lock"
    runtime_path = state_dir / "core.json"

    lock = acquire_instance_lock(lock_path)
    if lock is None:
        existing = read_runtime(runtime_path)
        port = existing.get("port") if existing else "?"
        logger.warning("core already running (port=%s); not starting second instance", port)
        return 3

    remove_runtime(runtime_path)                          # 拿到锁 = 无有效实例,残留一律丢弃
    setup_logging("core")
    logger.info("core starting: pid=%s version=%s", os.getpid(), __version__)
    config_path = default_config_path()
    config, notices = load_config(config_path)            # 保留 notices(如 config_reset)
    token = generate_token()
    # provider/interval 改动 → 写回 config.toml(spec:运行中改动持久化)
    hub = build_hub(config, token, on_change=lambda cfg: save_config(cfg, config_path))
    server = CoreServer(hub, host="127.0.0.1", port=config.port, notices=notices)

    started = time.time()

    def run_server():
        async def main_coro():
            serve_task = asyncio.create_task(server.serve())
            while server.actual_port() is None:
                if serve_task.done():
                    await serve_task   # serve() ended before binding — re-raise its error
                    return             # (defensive) if it returned cleanly, stop waiting
                await asyncio.sleep(0.01)
            write_runtime(runtime_path, pid=os.getpid(),
                          port=server.actual_port(), token=token,
                          started_at=started, version=__version__)
            await serve_task
        asyncio.run(main_coro())

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    stop = threading.Event()

    def _graceful(signum, frame):
        server.stop_threadsafe()
        stop.set()

    signal.signal(signal.SIGTERM, _graceful)
    signal.signal(signal.SIGINT, _graceful)

    try:
        while t.is_alive() and not stop.is_set():
            t.join(timeout=0.2)
    finally:
        server.stop_threadsafe()
        t.join(timeout=5)
        remove_runtime(runtime_path)
        logger.info("core stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
