from manager.config_store import ConfigStore


def test_default_disabled(tmp_path):
    assert ConfigStore(tmp_path / "c.json").is_enabled("clock") is False


def test_set_enabled(tmp_path):
    c = ConfigStore(tmp_path / "c.json")
    c.set_enabled("clock", True)
    assert c.is_enabled("clock") is True


def test_geometry_roundtrip(tmp_path):
    c = ConfigStore(tmp_path / "c.json")
    c.save_geometry("clock", 300, 150, 1.5)
    w = c.get_widget("clock")
    assert (w["x"], w["y"], w["zoom"]) == (300, 150, 1.5)


def test_enabled_and_geometry_coexist(tmp_path):
    p = tmp_path / "c.json"
    ConfigStore(p).set_enabled("clock", True)
    ConfigStore(p).save_geometry("clock", 10, 20, 2.0)
    w = ConfigStore(p).get_widget("clock")
    assert w["enabled"] is True and w["x"] == 10 and w["zoom"] == 2.0


def test_corrupt_falls_back(tmp_path):
    p = tmp_path / "c.json"; p.write_text("{ bad")
    assert ConfigStore(p).is_enabled("clock") is False
