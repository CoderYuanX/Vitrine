from pathlib import Path

_DESKTOP = """[Desktop Entry]
Type=Application
Name=ManageWidgets Core
Exec={exec_cmd}
X-GNOME-Autostart-enabled=true
"""


def autostart_path() -> Path:
    return Path.home() / ".config" / "autostart" / "managewidgets-core.desktop"


def enable_autostart(exec_cmd: str) -> None:
    p = autostart_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_DESKTOP.format(exec_cmd=exec_cmd))


def disable_autostart() -> None:
    p = autostart_path()
    if p.exists():
        p.unlink()


def is_autostart_enabled() -> bool:
    return autostart_path().exists()
