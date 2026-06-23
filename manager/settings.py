import os
import sys
import tempfile
from pathlib import Path

import tomllib
import tomli_w


def settings_path() -> Path:
    return Path.home() / ".config" / "managewidgets" / "manager.toml"


def load_close_to_tray() -> bool | None:
    path = settings_path()
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return None
    except (tomllib.TOMLDecodeError, OSError):
        return None
    val = data.get("close_to_tray")
    return val if isinstance(val, bool) else None


def save_close_to_tray(value: bool) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".manager.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(tomli_w.dumps({"close_to_tray": bool(value)}).encode("utf-8"))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def decide_close(pref: bool | None) -> str:
    if pref is True:
        return "tray"
    if pref is False:
        return "quit"
    return "ask"


def autostart_exec_cmd() -> str:
    return f"{sys.executable} -m manager"
