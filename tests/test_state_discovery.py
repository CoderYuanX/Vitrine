import os
import stat

import pytest

from core import state


def test_generate_token_strength():
    t = state.generate_token()
    assert isinstance(t, str)
    assert len(t) >= 43                                  # token_urlsafe(32) ≈ 43 chars
    assert " " not in t and "\n" not in t


def test_write_runtime_is_0600(tmp_path):
    p = tmp_path / "core.json"
    state.write_runtime(p, pid=111, port=35355, token="abc", started_at=1.0, version="0.1.0")
    mode = stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600                                  # 非 group/world 可读
    d = state.read_runtime(p)
    assert d["pid"] == 111 and d["port"] == 35355 and d["token"] == "abc"


def test_read_runtime_missing_or_corrupt(tmp_path):
    assert state.read_runtime(tmp_path / "none.json") is None
    bad = tmp_path / "core.json"
    bad.write_text("{ not json")
    assert state.read_runtime(bad) is None


def test_instance_lock_excludes_second(tmp_path):
    lock = tmp_path / "core.lock"
    h1 = state.acquire_instance_lock(lock)
    assert h1 is not None
    assert state.acquire_instance_lock(lock) is None      # 第二次拿不到
    h1.close()                                            # 释放后可再拿
    h2 = state.acquire_instance_lock(lock)
    assert h2 is not None
    h2.close()


def test_cmdline_is_core():
    assert state.cmdline_is_core("/x/.venv/bin/managewidgets-core")
    assert state.cmdline_is_core("/x/.venv/bin/python -m core")          # 面板/README 用的入口
    assert state.cmdline_is_core("/usr/bin/python3 /x/core/__main__.py")
    assert not state.cmdline_is_core("/usr/bin/python3 some_other_app.py")
    assert not state.cmdline_is_core("/usr/bin/python3 -m coreutils")    # 不误判
