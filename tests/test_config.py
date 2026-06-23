from pathlib import Path

import tomllib

from core.config import Config, DEFAULT_PORT, load_config, save_config


def test_load_missing_returns_default(tmp_path):
    cfg, notices = load_config(tmp_path / "config.toml")
    assert cfg.port == DEFAULT_PORT
    assert notices == []


def test_save_then_load_roundtrip(tmp_path):
    p = tmp_path / "config.toml"
    cfg = Config.default()
    cfg.port = 40000
    cfg.providers_enabled["system"] = False
    cfg.intervals["system.cpu"] = 5.0
    save_config(cfg, p)
    loaded, notices = load_config(p)
    assert loaded.port == 40000
    assert loaded.providers_enabled["system"] is False
    assert loaded.intervals["system.cpu"] == 5.0
    assert notices == []


def test_corrupt_config_backed_up_and_reset(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("this is not [ valid toml =====")
    cfg, notices = load_config(p)
    assert cfg.port == DEFAULT_PORT                      # 回退默认
    backups = list(tmp_path.glob("config.toml.bak.*"))
    assert len(backups) == 1                              # 原文件被备份
    assert [n["code"] for n in notices] == ["config_reset"]


def test_save_is_valid_toml(tmp_path):
    p = tmp_path / "config.toml"
    save_config(Config.default(), p)
    with p.open("rb") as f:
        tomllib.load(f)                                   # 不抛即合法


def test_load_config_logs_warning_on_corrupt(tmp_path, caplog):
    import logging

    from core.config import load_config

    p = tmp_path / "config.toml"
    p.write_text("not valid ===")
    with caplog.at_level(logging.WARNING, logger="core.config"):
        cfg, notices = load_config(p)
    assert notices and notices[0]["code"] == "config_reset"
    assert any(r.levelno == logging.WARNING and "config" in r.getMessage().lower()
               for r in caplog.records)
