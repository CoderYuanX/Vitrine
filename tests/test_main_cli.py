import json
import os
import socket
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import pytest
from websockets.sync.client import connect

REPO = Path(__file__).resolve().parents[1]
PY = str(REPO / ".venv" / "bin" / "python")


def _env(tmp_path):
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)                          # 隔离 ~/.config 与 ~/.local/state
    env["PYTHONPATH"] = str(REPO)
    return env


def _runtime(tmp_path):
    return tmp_path / ".local" / "state" / "managewidgets" / "core.json"


def _config(tmp_path):
    return tmp_path / ".config" / "managewidgets" / "config.toml"


def _connect_authed(data):
    ws = connect(f"ws://127.0.0.1:{data['port']}")
    ws.send(json.dumps({"id": "h", "action": "hello", "token": data["token"]}))
    end = time.time() + 4
    while time.time() < end:
        if json.loads(ws.recv(timeout=4)).get("id") == "h":
            return ws
    raise AssertionError("hello 未确认")


def _wait_ok(ws, rid, timeout=4):
    end = time.time() + timeout
    while time.time() < end:
        m = json.loads(ws.recv(timeout=timeout))
        if m.get("id") == rid and m.get("type") in ("ok", "error"):
            return m
    raise AssertionError(f"未收到 {rid} 的 ok/error")


def _wait_runtime(path, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        time.sleep(0.1)
    raise AssertionError("runtime 文件未在超时内出现")


def test_core_writes_runtime_with_token_and_0600(tmp_path):
    proc = subprocess.Popen([PY, "-m", "core"], env=_env(tmp_path))
    try:
        data = _wait_runtime(_runtime(tmp_path))
        assert data["pid"] == proc.pid
        assert isinstance(data["port"], int) and data["port"] > 0
        assert len(data["token"]) >= 43
        mode = oct(os.stat(_runtime(tmp_path)).st_mode)[-3:]
        assert mode == "600"
        # 端口确实在监听
        with socket.create_connection(("127.0.0.1", data["port"]), timeout=2):
            pass
    finally:
        proc.terminate(); proc.wait(timeout=5)


def test_second_instance_refused(tmp_path):
    p1 = subprocess.Popen([PY, "-m", "core"], env=_env(tmp_path))
    try:
        _wait_runtime(_runtime(tmp_path))
        p2 = subprocess.run([PY, "-m", "core"], env=_env(tmp_path),
                            capture_output=True, timeout=10)
        assert p2.returncode == 3                         # 第二实例被拒
    finally:
        p1.terminate(); p1.wait(timeout=5)


def test_sigterm_cleans_runtime(tmp_path):
    proc = subprocess.Popen([PY, "-m", "core"], env=_env(tmp_path))
    rt = _runtime(tmp_path)
    _wait_runtime(rt)
    proc.terminate(); proc.wait(timeout=5)
    assert not rt.exists()                                # 优雅退出删除 runtime


def test_config_changes_persist_across_restart(tmp_path):
    proc = subprocess.Popen([PY, "-m", "core"], env=_env(tmp_path))
    try:
        data = _wait_runtime(_runtime(tmp_path))
        ws = _connect_authed(data)
        ws.send(json.dumps({"id": "iv", "action": "set_interval",
                            "topic": "system.cpu", "interval": 5.0}))
        assert _wait_ok(ws, "iv")["type"] == "ok"
        ws.send(json.dumps({"id": "sp", "action": "set_provider",
                            "provider": "system", "enabled": False}))
        assert _wait_ok(ws, "sp")["type"] == "ok"
        ws.close()
    finally:
        proc.terminate(); proc.wait(timeout=5)
    with _config(tmp_path).open("rb") as f:               # 改动已写回 config.toml
        saved = tomllib.load(f)
    assert saved["intervals"]["system.cpu"] == 5.0
    assert saved["providers_enabled"]["system"] is False


def test_corrupt_config_surfaces_config_reset_notice(tmp_path):
    cfg = _config(tmp_path)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("not valid toml ===")
    proc = subprocess.Popen([PY, "-m", "core"], env=_env(tmp_path))
    try:
        data = _wait_runtime(_runtime(tmp_path))
        ws = _connect_authed(data)
        ws.send(json.dumps({"id": "ls", "action": "list_providers"}))
        end = time.time() + 4
        status = None
        while time.time() < end:
            m = json.loads(ws.recv(timeout=4))
            if m.get("type") == "status" and m.get("id") == "ls":
                status = m["status"]; break
        assert status is not None
        assert "config_reset" in [n["code"] for n in status["core"]["notices"]]
        ws.close()
    finally:
        proc.terminate(); proc.wait(timeout=5)
    assert len(list(cfg.parent.glob("config.toml.bak.*"))) == 1   # 损坏文件已备份


def test_core_writes_log_file(tmp_path):
    proc = subprocess.Popen([PY, "-m", "core"], env=_env(tmp_path))
    try:
        _wait_runtime(_runtime(tmp_path))
        log = tmp_path / ".local" / "state" / "managewidgets" / "logs" / "core.log"
        end = time.time() + 5
        while time.time() < end and not log.exists():
            time.sleep(0.1)
        assert log.exists()
        assert oct(os.stat(log).st_mode)[-3:] == "600"
        assert "logging initialized" in log.read_text()
    finally:
        proc.terminate(); proc.wait(timeout=5)
