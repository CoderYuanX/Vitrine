import json

from core.config import DEFAULT_PORT
from manager.discovery import discover


def test_discover_prefers_runtime(tmp_path):
    rt = tmp_path / "core.json"
    rt.write_text(json.dumps({"port": 40123, "token": "tok"}))
    host, port, token = discover(rt, tmp_path / "config.toml")
    assert (host, port, token) == ("127.0.0.1", 40123, "tok")


def test_discover_falls_back_to_config(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("port = 41000\n")
    host, port, token = discover(tmp_path / "none.json", cfg)
    assert port == 41000 and token is None


def test_discover_defaults(tmp_path):
    host, port, token = discover(tmp_path / "none.json", tmp_path / "none.toml")
    assert (host, port, token) == ("127.0.0.1", DEFAULT_PORT, None)
