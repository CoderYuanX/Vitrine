from pathlib import Path

_DESKTOP = """[Desktop Entry]
Type=Application
Name=ManageWidgets
Exec={exec_cmd}
X-GNOME-Autostart-enabled=true
"""

_LEGACY_FILENAME = "managewidgets-core.desktop"   # 历史文件名;实际自启的也是面板,仅作迁移/兼容


def autostart_path() -> Path:
    # 文件名与实际自启目标(manager 面板)一致;旧的 *-core.desktop 见 _legacy_path
    return Path.home() / ".config" / "autostart" / "managewidgets-manager.desktop"


def _legacy_path() -> Path:
    # 由 autostart_path 派生,使测试只 monkeypatch 一处即可覆盖新旧两个路径
    return autostart_path().with_name(_LEGACY_FILENAME)


def enable_autostart(exec_cmd: str) -> None:
    p = autostart_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_DESKTOP.format(exec_cmd=exec_cmd))
    legacy = _legacy_path()                            # 迁移:清掉旧名,避免新旧两份自启项重复拉起
    if legacy.exists():
        legacy.unlink()


def disable_autostart() -> None:
    for p in (autostart_path(), _legacy_path()):      # 新旧都清,确保彻底关闭
        if p.exists():
            p.unlink()


def is_autostart_enabled() -> bool:
    # 改名前已开启的老用户(只有 *-core.desktop)仍识别为已启用
    return autostart_path().exists() or _legacy_path().exists()
