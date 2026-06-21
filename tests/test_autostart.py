from manager import autostart


def test_disabled_by_default(tmp_path):
    assert autostart.is_enabled(tmp_path / "a.desktop") is False


def test_enable_writes_desktop(tmp_path):
    p = tmp_path / "a.desktop"
    autostart.set_enabled(True, "python /opt/main.py", p)
    assert p.exists()
    assert autostart.is_enabled(p) is True
    assert "python /opt/main.py" in p.read_text()


def test_disable_removes(tmp_path):
    p = tmp_path / "a.desktop"
    autostart.set_enabled(True, "x", p)
    autostart.set_enabled(False, "x", p)
    assert autostart.is_enabled(p) is False
