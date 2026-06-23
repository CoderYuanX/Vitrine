import sys

from manager.settings import (
    autostart_exec_cmd,
    decide_close,
    load_close_to_tray,
    save_close_to_tray,
    settings_path,
)


def test_decide_close_mapping():
    assert decide_close(True) == "tray"
    assert decide_close(False) == "quit"
    assert decide_close(None) == "ask"


def test_load_missing_returns_none(tmp_path, monkeypatch):
    target = tmp_path / "manager.toml"
    monkeypatch.setattr("manager.settings.settings_path", lambda: target)
    assert load_close_to_tray() is None


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "manager.toml"
    monkeypatch.setattr("manager.settings.settings_path", lambda: target)
    save_close_to_tray(True)
    assert target.exists()
    assert load_close_to_tray() is True
    save_close_to_tray(False)
    assert load_close_to_tray() is False


def test_corrupt_returns_none(tmp_path, monkeypatch):
    target = tmp_path / "manager.toml"
    target.write_text("this is not [ valid toml ===")
    monkeypatch.setattr("manager.settings.settings_path", lambda: target)
    assert load_close_to_tray() is None


def test_autostart_exec_cmd_targets_manager():
    cmd = autostart_exec_cmd()
    assert cmd == f"{sys.executable} -m manager"
    assert "-m manager" in cmd
