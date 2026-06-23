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


import pytest

from core import logs


@pytest.fixture(autouse=True)
def _restore_component_loggers():
    saved = {}
    for name in ("core", "manager"):
        lg = logging.getLogger(name)
        saved[name] = (lg.level, lg.propagate)
    yield
    for name, (level, propagate) in saved.items():
        lg = logging.getLogger(name)
        for h in [h for h in lg.handlers if getattr(h, "_managewidgets", False)]:
            lg.removeHandler(h)
            h.close()
        lg.setLevel(level)
        lg.propagate = propagate


def test_creates_file_and_writes(tmp_path):
    path = logs.setup_logging("core", log_dir=tmp_path)
    logging.getLogger("core.x").info("hello-line")
    assert path == tmp_path / "core.log"
    assert "hello-line" in path.read_text()


def test_level_filtering(tmp_path):
    path = logs.setup_logging("core", log_dir=tmp_path, level="WARNING")
    logging.getLogger("core.x").info("info-line")
    logging.getLogger("core.x").warning("warn-line")
    text = path.read_text()
    assert "info-line" not in text and "warn-line" in text


def test_idempotent_no_handler_doubling(tmp_path):
    logs.setup_logging("core", log_dir=tmp_path)
    logs.setup_logging("core", log_dir=tmp_path)
    lg = logging.getLogger("core")
    tagged = [h for h in lg.handlers if getattr(h, "_managewidgets", False)]
    assert len(tagged) == 2                                # 1 file + 1 stream,非 4


def test_same_process_isolation(tmp_path):
    logs.setup_logging("core", log_dir=tmp_path)
    logs.setup_logging("manager", log_dir=tmp_path)
    logging.getLogger("core.a").info("from-core")
    logging.getLogger("manager.b").info("from-manager")
    core_text = (tmp_path / "core.log").read_text()
    mgr_text = (tmp_path / "manager.log").read_text()
    assert "from-core" in core_text and "from-core" not in mgr_text
    assert "from-manager" in mgr_text and "from-manager" not in core_text


def test_permissions_dir_and_file(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    os.chmod(d, 0o755)
    path = logs.setup_logging("core", log_dir=d)
    assert d.stat().st_mode & 0o777 == 0o700               # 已存在目录也收紧
    assert path.stat().st_mode & 0o777 == 0o600


def test_invalid_component_raises_and_no_file(tmp_path):
    with pytest.raises(ValueError):
        logs.setup_logging("bad/name", log_dir=tmp_path)
    assert list(tmp_path.glob("*")) == []                  # 校验先于建目录/挂 handler


def test_invalid_level_warning_written(tmp_path, monkeypatch):
    monkeypatch.setenv("MANAGEWIDGETS_LOG_LEVEL", "bogus")
    path = logs.setup_logging("core", log_dir=tmp_path)
    text = path.read_text()
    assert "invalid log level" in text and "bogus" in text and "INFO" in text


def test_invalid_level_via_argument_falls_back(tmp_path):
    logs.setup_logging("core", log_dir=tmp_path, level="bogus")
    assert logging.getLogger("core").level == logging.INFO


def test_retention_env_override_and_invalid(monkeypatch):
    monkeypatch.setenv("MANAGEWIDGETS_LOG_RETENTION_DAYS", "3")
    assert logs._resolve_retention_days(None, os.environ.get("MANAGEWIDGETS_LOG_RETENTION_DAYS")) == 3
    monkeypatch.setenv("MANAGEWIDGETS_LOG_RETENTION_DAYS", "nope")
    assert logs._resolve_retention_days(None, os.environ.get("MANAGEWIDGETS_LOG_RETENTION_DAYS")) == 7
