import fcntl
import json
import os
import secrets
import tempfile
from pathlib import Path


def default_state_dir() -> Path:
    return Path.home() / ".local" / "state" / "managewidgets"


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def acquire_instance_lock(lock_path: Path):
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh                                            # 调用方须保持引用;进程退出自动释放


def write_runtime(path: Path, *, pid: int, port: int, token: str,
                  started_at: float, version: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pid": pid, "port": port, "token": token,
               "started_at": started_at, "version": version}
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".core.", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)                             # 先收紧权限再写,避免 chmod 前可读窗口
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_runtime(path: Path) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def remove_runtime(path: Path) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def cmdline_is_core(cmdline: str) -> bool:
    # 同时识别 console_script(`managewidgets-core`)与 `python -m core` / `core/__main__.py`
    if "managewidgets-core" in cmdline:
        return True
    parts = cmdline.split()
    if "-m" in parts and "core" in parts:
        return True
    return any(p.endswith("core/__main__.py") for p in parts)


def pid_is_core(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmdline = f.read().replace(b"\x00", b" ").decode("utf-8", "replace")
    except OSError:
        return False
    return cmdline_is_core(cmdline)
