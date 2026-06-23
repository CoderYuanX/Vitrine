from pathlib import Path

from core.config import DEFAULT_PORT, load_config
from core.state import read_runtime


def discover(runtime_path: Path, config_path: Path) -> tuple[str, int, str | None]:
    rt = read_runtime(runtime_path)
    if rt and rt.get("port"):
        return "127.0.0.1", int(rt["port"]), rt.get("token")
    cfg, _ = load_config(config_path)
    return "127.0.0.1", int(cfg.port), None
