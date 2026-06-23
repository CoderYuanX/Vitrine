import logging

_DEFAULT_RETENTION_DAYS = 7
_NAME_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_NUMERIC_LEVELS = {10, 20, 30, 40, 50}


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
