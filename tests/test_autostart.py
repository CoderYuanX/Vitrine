from core import autostart

_LEGACY = "managewidgets-core.desktop"


def _patch(tmp_path, monkeypatch):
    # 自启文件名与实际自启目标(manager 面板)一致;_legacy_path 由 autostart_path 派生,
    # 故只 monkeypatch 这一个即可把新旧两个路径都指向 tmp,绝不触碰真实 ~/.config/autostart
    target = tmp_path / "autostart" / "managewidgets-manager.desktop"
    monkeypatch.setattr(autostart, "autostart_path", lambda: target)
    return target


def test_enable_disable_autostart(tmp_path, monkeypatch):
    target = _patch(tmp_path, monkeypatch)
    assert autostart.is_autostart_enabled() is False
    autostart.enable_autostart("/usr/bin/python -m manager")
    assert target.exists()
    assert "-m manager" in target.read_text()
    assert "Core" not in target.read_text()              # Name 不再误标为 Core
    assert autostart.is_autostart_enabled() is True
    autostart.disable_autostart()
    assert autostart.is_autostart_enabled() is False


def test_enable_migrates_legacy_core_desktop(tmp_path, monkeypatch):
    # 启用时把历史的 *-core.desktop 清掉,避免新旧两份自启项重复拉起面板
    target = _patch(tmp_path, monkeypatch)
    legacy = target.with_name(_LEGACY)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("old")
    autostart.enable_autostart("/usr/bin/python -m manager")
    assert target.exists()                               # 新名已写入
    assert not legacy.exists()                            # 旧名已清除


def test_legacy_only_counts_as_enabled(tmp_path, monkeypatch):
    # 改名前已开启自启的老用户(只有 *-core.desktop)仍应识别为"已启用"
    target = _patch(tmp_path, monkeypatch)
    legacy = target.with_name(_LEGACY)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("old")
    assert autostart.is_autostart_enabled() is True


def test_disable_removes_legacy_too(tmp_path, monkeypatch):
    # 关闭自启要新旧都清,否则旧文件残留导致"关了还自启"
    target = _patch(tmp_path, monkeypatch)
    legacy = target.with_name(_LEGACY)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("old")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("new")
    autostart.disable_autostart()
    assert not target.exists()
    assert not legacy.exists()
