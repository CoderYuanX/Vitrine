import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_DEFAULT_RETENTION_DAYS = 7
_NAME_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_NUMERIC_LEVELS = {10, 20, 30, 40, 50}
_LOG_PREFIXES = ("core.log", "manager.log")


def _parse_level(raw):
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw in _NUMERIC_LEVELS else None
    if isinstance(raw, str):
        s = raw.strip()
        if s.upper() in _NAME_LEVELS:
            return _NAME_LEVELS[s.upper()]
        if s.isdigit() and int(s) in _NUMERIC_LEVELS:
            return int(s)
    return None


def _resolve_level(explicit, env_value):
    for source, raw in (("argument", explicit), ("env", env_value)):
        if raw is None:
            continue
        level = _parse_level(raw)
        if level is not None:
            return level, None
        return logging.INFO, f"invalid log level from {source}: {raw!r}; using INFO"
    return logging.INFO, None


def _resolve_retention_days(explicit, env_value):
    for raw in (explicit, env_value):
        if raw is None:
            continue
        try:
            n = int(raw)
        except (TypeError, ValueError):
            return _DEFAULT_RETENTION_DAYS
        return n if n > 0 else _DEFAULT_RETENTION_DAYS
    return _DEFAULT_RETENTION_DAYS


def _cleanup_old_logs(log_dir, retention_days):
    warnings = []
    cutoff = time.time() - retention_days * 86400
    for prefix in _LOG_PREFIXES:
        for path in Path(log_dir).glob(prefix + "*"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError as exc:
                warnings.append(f"failed to remove old log {path.name}: {exc}")
    return warnings


class _SecureTimedRotatingFileHandler(TimedRotatingFileHandler):
    """按天轮转,且初始与轮转新建文件都以 0o600 创建。

    open() 的 opener 回调收 (path, flags)、用 os.open 以 0o600 创建并返回 fd
    （不是把整个 _open 换成 os.open —— _open 需返回 stream 而非 fd）。
    """

    def _open(self):
        return open(self.baseFilename, self.mode, encoding=self.encoding,
                    opener=lambda path, flags: os.open(path, flags, 0o600))
