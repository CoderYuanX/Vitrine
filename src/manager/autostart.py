from pathlib import Path

_DEFAULT = Path.home() / ".config" / "autostart" / "deepin-widgets.desktop"


def _path(path):
    return Path(path) if path else _DEFAULT


def is_enabled(path=None):
    return _path(path).is_file()


def set_enabled(on, exec_cmd, path=None):
    p = _path(path)
    if on:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=桌面小组件\n"
            f"Exec={exec_cmd}\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
    elif p.is_file():
        p.unlink()
