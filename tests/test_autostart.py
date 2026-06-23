from core import autostart


def test_enable_disable_autostart(tmp_path, monkeypatch):
    target = tmp_path / "autostart" / "managewidgets-core.desktop"
    monkeypatch.setattr(autostart, "autostart_path", lambda: target)
    assert autostart.is_autostart_enabled() is False
    autostart.enable_autostart("/usr/bin/managewidgets-core")
    assert target.exists()
    assert "managewidgets-core" in target.read_text()
    assert autostart.is_autostart_enabled() is True
    autostart.disable_autostart()
    assert autostart.is_autostart_enabled() is False
