import logging
import os
import time
from pathlib import Path

from core.logs import _resolve_level, _resolve_retention_days


def test_resolve_level_names_case_insensitive():
    assert _resolve_level("debug", None) == (logging.DEBUG, None)
    assert _resolve_level("Warning", None) == (logging.WARNING, None)


def test_resolve_level_standard_ints():
    assert _resolve_level("30", None) == (logging.WARNING, None)
    assert _resolve_level(30, None) == (logging.WARNING, None)


def test_resolve_level_invalid_arg_falls_back_with_warning():
    level, warn = _resolve_level("bogus", None)
    assert level == logging.INFO
    assert "bogus" in warn and "argument" in warn and "INFO" in warn


def test_resolve_level_out_of_range_int_invalid():
    level, warn = _resolve_level("999", None)
    assert level == logging.INFO and warn is not None


def test_resolve_level_arg_over_env():
    assert _resolve_level("ERROR", "DEBUG") == (logging.ERROR, None)


def test_resolve_level_env_used_when_no_arg():
    level, warn = _resolve_level(None, "bogus")
    assert level == logging.INFO and "env" in warn


def test_resolve_level_default_info():
    assert _resolve_level(None, None) == (logging.INFO, None)


def test_resolve_retention_default_invalid_and_override():
    assert _resolve_retention_days(None, None) == 7
    assert _resolve_retention_days("abc", None) == 7
    assert _resolve_retention_days(0, None) == 7
    assert _resolve_retention_days(-3, None) == 7
    assert _resolve_retention_days(14, None) == 14
    assert _resolve_retention_days(None, "10") == 10


def test_secure_handler_initial_and_rollover_0600(tmp_path):
    from core.logs import _SecureTimedRotatingFileHandler

    p = tmp_path / "core.log"
    h = _SecureTimedRotatingFileHandler(str(p), when="midnight", backupCount=7,
                                        encoding="utf-8", delay=False)
    try:
        rec = logging.LogRecord("core.x", logging.INFO, __file__, 0, "msg", None, None)
        h.emit(rec)
        assert p.stat().st_mode & 0o777 == 0o600          # 初始文件
        h.doRollover()
        h.emit(rec)
        assert p.stat().st_mode & 0o777 == 0o600          # 轮转新建文件
    finally:
        h.close()


def test_cleanup_deletes_old_keeps_recent_ignores_others(tmp_path):
    from core.logs import _cleanup_old_logs

    old = time.time() - 8 * 86400
    for name in ("core.log.old", "manager.log.old", "other.log.old", "notes.txt"):
        f = tmp_path / name
        f.write_text("x")
        os.utime(f, (old, old))
    (tmp_path / "core.log").write_text("x")               # 近期文件

    warnings = _cleanup_old_logs(tmp_path, 7)

    names = {p.name for p in tmp_path.iterdir()}
    assert "core.log.old" not in names                     # 两端过期都删
    assert "manager.log.old" not in names
    assert "core.log" in names                             # 近期保留
    assert "other.log.old" in names and "notes.txt" in names   # 非本系统前缀不动
    assert warnings == []


def test_cleanup_failure_collected_not_raised(tmp_path, monkeypatch):
    from core.logs import _cleanup_old_logs

    old = time.time() - 8 * 86400
    f = tmp_path / "core.log.old"
    f.write_text("x")
    os.utime(f, (old, old))

    def boom(self, *a, **k):
        raise OSError("nope")

    monkeypatch.setattr(Path, "unlink", boom)
    warnings = _cleanup_old_logs(tmp_path, 7)
    assert any("core.log.old" in w for w in warnings)      # 失败被收集而非抛出
