# 落盘日志系统 + 7 天自动清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 deskwidgets 加一套落盘日志系统:`core`/`manager` 各写一个按天轮转、7 天自动清理的日志文件,收编现有 `print(stderr)`/被吞异常,主要服务于人/AI 排障。

**Architecture:** 新增 `core/logs.py::setup_logging(component)`,把 file + stderr handler 挂在**包级 logger**(`core`/`manager`,`propagate=False`)上,实现进程内隔离与幂等;用标准库 `TimedRotatingFileHandler` 子类(重写 `_open` 保证 0600)按天轮转,叠加启动清理删除 >7 天旧文件。各模块用 `getLogger(__name__)` 埋点。

**Tech Stack:** Python 3.11 标准库 `logging` / `logging.handlers`,无新依赖。pytest。

## Global Constraints

- 不引入任何第三方依赖(仅标准库)。
- 日志目录权限 `0o700`,日志文件权限 `0o600`(与 `core.json` 一致)。
- handler 挂在包级 logger `logging.getLogger(component)`,`component` 仅 `"core"`/`"manager"`,其余 `ValueError`;`propagate = False`。
- 永不记录:token、完整 runtime payload、完整 WebSocket `hello` 握手消息。只记 port/pid/version、请求 action/id、鉴权成败。
- Formatter 固定:`"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`。
- 默认级别 INFO;env `MANAGEWIDGETS_LOG_LEVEL` 可覆盖(名称大小写不敏感 + 标准数值 10/20/30/40/50),非法回退 INFO。
- 默认保留 7 天;env `MANAGEWIDGETS_LOG_RETENTION_DAYS` 覆盖,非整数/≤0 回退 7。
- 启动清理只扫前缀 `core.log*` / `manager.log*`,删 mtime > 保留天数者;单文件删除失败收集进 `cleanup_warnings`、不阻断启动。
- 日志调用一律 `getLogger(__name__)`,不得成为恢复路径的新失败点(未 setup 时走 lastResort,不抛异常)。
- 运行测试:`.venv/bin/python -m pytest`。

---

### Task 1: 级别 / 保留天数解析helpers

**Files:**
- Create: `core/logs.py`
- Test: `tests/test_logs.py`

**Interfaces:**
- Produces:
  - `_resolve_level(explicit, env_value) -> tuple[int, str | None]` —— 返回 `(numeric_level, warning_or_None)`,`explicit` 优先于 `env_value`;非法回退 `(logging.INFO, "<text>")`,文本含原始值、来源(`argument`/`env`)、`INFO`。
  - `_resolve_retention_days(explicit, env_value) -> int` —— `explicit` 优先;非整数/≤0 回退 7。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_logs.py
import logging

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
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_logs.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.logs'`

- [ ] **Step 3: 写最小实现**

```python
# core/logs.py
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
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_logs.py -q`
Expected: PASS（8 passed）

- [ ] **Step 5: 提交**

```bash
git add core/logs.py tests/test_logs.py
git commit -m "feat(logs): 级别/保留天数解析 helpers"
```

---

### Task 2: 0600 安全轮转 handler

**Files:**
- Modify: `core/logs.py`
- Test: `tests/test_logs.py`

**Interfaces:**
- Produces: `_SecureTimedRotatingFileHandler(TimedRotatingFileHandler)` —— 重写 `_open()`,初始与轮转新建文件均 `0o600`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_logs.py 追加
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
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_logs.py::test_secure_handler_initial_and_rollover_0600 -q`
Expected: FAIL — `ImportError: cannot import name '_SecureTimedRotatingFileHandler'`

- [ ] **Step 3: 写最小实现**

```python
# core/logs.py 顶部 import 增补
import os
from logging.handlers import TimedRotatingFileHandler


# core/logs.py 追加
class _SecureTimedRotatingFileHandler(TimedRotatingFileHandler):
    """按天轮转,且初始与轮转新建文件都以 0o600 创建。

    open() 的 opener 回调收 (path, flags)、用 os.open 以 0o600 创建并返回 fd
    （不是把整个 _open 换成 os.open —— _open 需返回 stream 而非 fd）。
    """

    def _open(self):
        return open(self.baseFilename, self.mode, encoding=self.encoding,
                    opener=lambda path, flags: os.open(path, flags, 0o600))
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_logs.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/logs.py tests/test_logs.py
git commit -m "feat(logs): 0600 安全轮转 handler"
```

---

### Task 3: 启动清理

**Files:**
- Modify: `core/logs.py`
- Test: `tests/test_logs.py`

**Interfaces:**
- Produces: `_cleanup_old_logs(log_dir, retention_days) -> list[str]` —— 删除 `log_dir` 下 `core.log*`/`manager.log*` 中 mtime 早于 `retention_days` 天者;删除失败收集为 warning 文本列表返回,不抛异常。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_logs.py 追加
import os
import time
from pathlib import Path


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
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_logs.py -k cleanup -q`
Expected: FAIL — `ImportError: cannot import name '_cleanup_old_logs'`

- [ ] **Step 3: 写最小实现**

```python
# core/logs.py 顶部 import 增补
import time
from pathlib import Path

# core/logs.py 追加（常量放模块顶部已有常量旁）
_LOG_PREFIXES = ("core.log", "manager.log")


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
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_logs.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/logs.py tests/test_logs.py
git commit -m "feat(logs): 启动清理（前缀限定 + 失败收集）"
```

---

### Task 4: setup_logging 编排

**Files:**
- Modify: `core/logs.py`
- Test: `tests/test_logs.py`

**Interfaces:**
- Consumes: `_resolve_level`, `_resolve_retention_days`, `_cleanup_old_logs`, `_SecureTimedRotatingFileHandler`（Task 1-3）。
- Produces: `setup_logging(component, *, log_dir=None, level=None, retention_days=None) -> Path` —— 配置组件包级 logger,返回 `{component}.log` 路径。

- [ ] **Step 1: 写失败测试 + 测试隔离 fixture**

```python
# tests/test_logs.py 追加
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
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_logs.py -k "creates_file or isolation or permissions" -q`
Expected: FAIL — `AttributeError: module 'core.logs' has no attribute 'setup_logging'`

- [ ] **Step 3: 写实现**

```python
# core/logs.py 顶部 import 增补
import sys

from core.state import default_state_dir

# core/logs.py 常量增补
_COMPONENTS = ("core", "manager")
_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_HANDLER_TAG = "_managewidgets"


def setup_logging(component, *, log_dir=None, level=None, retention_days=None):
    if component not in _COMPONENTS:
        raise ValueError(f"unknown logging component: {component!r}")

    log_dir = Path(log_dir) if log_dir is not None else default_state_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(log_dir, 0o700)                               # 即便目录已存在也收紧

    retention = _resolve_retention_days(
        retention_days, os.environ.get("MANAGEWIDGETS_LOG_RETENTION_DAYS"))
    cleanup_warnings = _cleanup_old_logs(log_dir, retention)   # handler 未挂,暂存 warning

    numeric_level, level_warning = _resolve_level(
        level, os.environ.get("MANAGEWIDGETS_LOG_LEVEL"))

    logger = logging.getLogger(component)
    logger.setLevel(numeric_level)
    logger.propagate = False
    for h in [h for h in logger.handlers if getattr(h, _HANDLER_TAG, False)]:
        logger.removeHandler(h)
        h.close()

    path = log_dir / f"{component}.log"
    fmt = logging.Formatter(_FORMAT)

    file_handler = _SecureTimedRotatingFileHandler(
        str(path), when="midnight", backupCount=retention,
        encoding="utf-8", delay=False, utc=False)
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(fmt)
    setattr(file_handler, _HANDLER_TAG, True)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(max(numeric_level, logging.WARNING))
    stream_handler.setFormatter(fmt)
    setattr(stream_handler, _HANDLER_TAG, True)
    logger.addHandler(stream_handler)

    for msg in cleanup_warnings:                           # handler 挂好后补发延后的 warning
        logger.warning(msg)
    if level_warning:
        logger.warning(level_warning)
    logger.info("logging initialized: component=%s level=%s retention=%dd file=%s",
                component, logging.getLevelName(numeric_level), retention, path)
    return path
```

- [ ] **Step 4: 运行,确认通过(整文件)**

Run: `.venv/bin/python -m pytest tests/test_logs.py -q`
Expected: PASS（全部 logs 用例）

- [ ] **Step 5: 提交**

```bash
git add core/logs.py tests/test_logs.py
git commit -m "feat(logs): setup_logging 编排（包级 logger/权限/清理/级别落盘）"
```

---

### Task 5: core/config 配置损坏落日志

**Files:**
- Modify: `core/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 无（用 `getLogger(__name__)`,未 setup 时走 lastResort,不依赖 Task 1-4 运行时）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py 追加
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
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_config.py::test_load_config_logs_warning_on_corrupt -q`
Expected: FAIL — 无 WARNING 记录(`assert any(...)` 失败)

- [ ] **Step 3: 写实现**

`core/config.py` 顶部加:

```python
import logging

logger = logging.getLogger(__name__)
```

在 `load_config` 的 `except (tomllib.TOMLDecodeError, ValueError, OSError):` 分支里、构造 `notice` 之后、`return` 之前加一行:

```python
        logger.warning("config corrupt, reset; backup=%s",
                       backup.name if backup else "(backup failed)")
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/config.py tests/test_config.py
git commit -m "feat(logs): 配置损坏重置落 WARNING"
```

---

### Task 6: core/server 埋点 + provider poll 错误落盘(集成)

**Files:**
- Modify: `core/server.py`
- Test: `tests/test_core_integration.py`

**Interfaces:**
- Consumes: `core.logs.setup_logging`（Task 4）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_core_integration.py 追加（文件已有 BoomProvider / start_in_thread / Hub / Config / time）
def test_provider_poll_error_written_to_log(tmp_path):
    from core import logs

    logs.setup_logging("core", log_dir=tmp_path)
    log_path = tmp_path / "core.log"
    hub = Hub([BoomProvider()], Config.default(), token="secret")
    server, thread, port = start_in_thread(hub, "127.0.0.1", 0)
    try:
        deadline = time.time() + 4
        while time.time() < deadline:
            if log_path.exists() and "boom.x" in log_path.read_text():
                break
            time.sleep(0.1)
        text = log_path.read_text()
        assert "boom" in text          # provider id + 异常文本
        assert "boom.x" in text        # topic
        assert "Traceback" in text     # 堆栈
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)
        lg = logging.getLogger("core")                     # 还原,避免污染同文件其它用例
        for h in [h for h in lg.handlers if getattr(h, "_managewidgets", False)]:
            lg.removeHandler(h); h.close()
        lg.propagate = True
```

并在文件顶部 import 增补 `import logging`（若无）。

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_core_integration.py::test_provider_poll_error_written_to_log -q`
Expected: FAIL — `core.log` 中无 `Traceback`/`boom.x`

- [ ] **Step 3: 写实现**

`core/server.py` 顶部加:

```python
import logging

logger = logging.getLogger(__name__)
```

在 `_poll_loop` 的 `except Exception as exc:` 分支补一行(记录前不改既有 record/broadcast 行为):

```python
                except Exception as exc:                 # provider 采集异常:记错,不杀循环
                    logger.exception("provider %s poll %s failed",
                                     self._hub.provider_id_of(topic), topic)
                    self._hub.record(topic, None, ts=time.time(), error=str(exc))
                    await self._broadcast_status()
```

在 `serve()` 里 `self._actual_port = ...` 之后加 listening 行;`except OSError:` 回退分支加 warning:

```python
        except OSError:
            logger.warning("preferred port %s unavailable, falling back to OS-assigned",
                           self._port)
            server = await websockets.serve(self._handler, self._host, 0)
```
```python
            self._actual_port = server.sockets[0].getsockname()[1]
            logger.info("core server listening on %s:%s", self._host, self._actual_port)
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_core_integration.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/server.py tests/test_core_integration.py
git commit -m "feat(logs): server provider poll 异常落 ERROR+堆栈,端口绑定记日志"
```

---

### Task 7: core 入口接线 + 启动/拒绝/关停日志

**Files:**
- Modify: `core/__main__.py`
- Test: `tests/test_main_cli.py`

**Interfaces:**
- Consumes: `core.logs.setup_logging`（Task 4）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_main_cli.py 追加
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
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_main_cli.py::test_core_writes_log_file -q`
Expected: FAIL — `core.log` 不存在

- [ ] **Step 3: 写实现**

`core/__main__.py` 顶部加:

```python
import logging

from core.logs import setup_logging

logger = logging.getLogger(__name__)
```

在 `main()` 中:第二实例拒绝分支(`if lock is None:`)把 `print(...)` 改为(不调用 setup_logging,避免两进程抢写同一文件,走 lastResort 到 stderr):

```python
    if lock is None:
        existing = read_runtime(runtime_path)
        port = existing.get("port") if existing else "?"
        logger.warning("core already running (port=%s); not starting second instance", port)
        return 3
```

紧接 `remove_runtime(runtime_path)` 之后(确认是唯一实例后再配置文件日志):

```python
    setup_logging("core")
    logger.info("core starting: pid=%s version=%s", os.getpid(), __version__)
```

在 `finally:`(`remove_runtime(runtime_path)` 之后)加关停行:

```python
    finally:
        server.stop_threadsafe()
        t.join(timeout=5)
        remove_runtime(runtime_path)
        logger.info("core stopped")
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_main_cli.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/__main__.py tests/test_main_cli.py
git commit -m "feat(logs): core 入口接线 setup_logging + 启动/拒绝/关停日志"
```

---

### Task 8: manager 埋点 + 入口接线

**Files:**
- Modify: `manager/app.py`, `manager/supervisor.py`, `manager/ws_client.py`
- Test: `tests/test_manager_app_logic.py`, `tests/test_core_supervisor.py`, `tests/test_ws_client.py`

**Interfaces:**
- Consumes: `core.logs.setup_logging`（Task 4）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_manager_app_logic.py 追加
def test_show_error_logs(caplog):
    import logging
    app = _app()
    app._win = None
    with caplog.at_level(logging.ERROR, logger="manager.app"):
        app._show_error("boom-msg")
    assert any("boom-msg" in r.getMessage() for r in caplog.records)
```

```python
# tests/test_core_supervisor.py 追加
def test_start_core_logs_on_popen_failure(monkeypatch, caplog):
    import logging
    import manager.supervisor as sup_mod
    sup = _sup()
    monkeypatch.setattr(sup_mod.subprocess, "Popen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    with caplog.at_level(logging.ERROR, logger="manager.supervisor"):
        sup.start_core()
    assert any(r.levelno == logging.ERROR for r in caplog.records)
```

```python
# tests/test_ws_client.py 追加
def test_bad_token_logs_warning(caplog):
    import logging
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with caplog.at_level(logging.WARNING, logger="manager.ws_client"):
            client = CoreClient("127.0.0.1", port, "WRONG",
                                on_event=lambda m: None, on_state=lambda s: None)
            client.start()
            deadline = time.time() + 4
            while time.time() < deadline and not any(
                    r.name == "manager.ws_client" for r in caplog.records):
                time.sleep(0.05)
            client.stop()
        assert any(r.name == "manager.ws_client" and r.levelno >= logging.WARNING
                   for r in caplog.records)
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_manager_app_logic.py::test_show_error_logs tests/test_core_supervisor.py::test_start_core_logs_on_popen_failure tests/test_ws_client.py::test_bad_token_logs_warning -q`
Expected: FAIL（三处均无对应日志记录)

- [ ] **Step 3: 写实现**

`manager/app.py` 顶部加 `import logging` 与 `logger = logging.getLogger(__name__)`(置于 import 段后)。

`_build_tray` 的 `except Exception as exc:` 分支,把 `print(...)` + `traceback.print_exc()` 替换为:

```python
        except Exception:                                 # 缺 AyatanaAppIndicator3 等 → 降级
            logger.warning("托盘不可用,降级为普通窗口", exc_info=True)
            return None
```
（删除原 `import traceback` 那两行 print/print_exc。)

`_show_error` 开头加日志(无论有无窗口都落盘):

```python
    def _show_error(self, message):
        logger.error("操作失败: %s", message)
        if self._win is None:
            return
        ...
```
（删除原 `print(f"[manager] {message}", file=sys.stderr)` 行。)

`main()` 开头(`app = ManagerApp()` 之前)接线:

```python
def main(argv=None) -> int:
    from core.logs import setup_logging
    setup_logging("manager")
    app = ManagerApp()
    return app.run(argv if argv is not None else sys.argv)
```

`manager/supervisor.py` 顶部加 `import logging` 与 `logger = logging.getLogger(__name__)`。

`start_core` 的 `except OSError as exc:` 把 `print(...)` 换为:

```python
        except OSError:
            logger.exception("启动底座失败")
            self._start_polls_active = False
            self._on_state("disconnected")
            return
```

`_reconnect_when_ready` 超时分支加 warning:

```python
        if self._start_polls >= 20:
            self._start_polls_active = False
            logger.warning("底座启动超时,放弃重连")
            self._on_state("start_failed")
            return False
```

`_handle_control_reply` 错误分支加 warning(只记非敏感字段):

```python
    def _handle_control_reply(self, reply):
        if reply.get("type") == "error":
            logger.warning("控制操作被拒: code=%s message=%s",
                           reply.get("code"), reply.get("message"))
            self._on_event(reply)
            self._request_status_refresh()
        return False
```

`manager/ws_client.py` 顶部加 `import logging` 与 `logger = logging.getLogger(__name__)`。

`_main` 中鉴权失败分支(`if ack.get("type") != "ok":`)加 warning(不记 token):

```python
                    if ack.get("type") != "ok":
                        logger.warning("鉴权失败,停止重连")
                        self._on_state("error")
                        ...
```

连接成功处加 info(`self._on_state("connected")` 之后):

```python
                    self._connected = True
                    had_session = True
                    logger.info("connected to core at %s:%s", self._host, self._port)
                    self._on_state("connected")
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_manager_app_logic.py tests/test_core_supervisor.py tests/test_ws_client.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add manager/app.py manager/supervisor.py manager/ws_client.py tests/test_manager_app_logic.py tests/test_core_supervisor.py tests/test_ws_client.py
git commit -m "feat(logs): manager 埋点（托盘降级/启动/控制/鉴权）+ 入口接线"
```

---

### Task 9: README 日志小节

**Files:**
- Modify: `README.md`

**Interfaces:** 无（纯文档）。

- [ ] **Step 1: 项目结构补 `core/logs.py`**

把 `项目结构` 代码块里 `core/` 那行下增补一行:

```
core/                数据底座:provider 采集、WebSocket hub、状态/配置、自启
  └─ logs.py         setup_logging:按天轮转 + 7 天清理的落盘日志(core/manager 各一文件)
```

- [ ] **Step 2: 新增「日志」小节**

在 `🧪 测试` 小节之前插入:

```markdown
## 🪵 日志

两进程各写一份按天轮转、**默认保留 7 天**(自动清理)的日志,便于人/AI 排障:

```
~/.local/state/managewidgets/logs/
  ├─ core.log       # 底座
  └─ manager.log    # 面板
```

实时跟看:

```bash
tail -f ~/.local/state/managewidgets/logs/manager.log    # 面板
tail -f ~/.local/state/managewidgets/logs/core.log       # 底座
```

- 目录 `0700` / 文件 `0600`;默认级别 INFO,`MANAGEWIDGETS_LOG_LEVEL=DEBUG` 可调更细。
- 保留天数 `MANAGEWIDGETS_LOG_RETENTION_DAYS`(默认 7)。
- provider 采集失败、连接/鉴权、控制被拒、托盘降级等均带来源与堆栈。
```

- [ ] **Step 3: 提交**

```bash
git add README.md
git commit -m "docs(readme): 日志小节 + 项目结构补 core/logs.py"
```

---

## 自查

- **Spec 覆盖**:选型/位置/格式 → Task 4(Formatter、包 logger、路径);轮转清理 → Task 2+3+4;入口 → Task 4(`setup_logging`)、Task 7(core)、Task 8(manager);埋点表 6 模块 → core/config(T5)、core/server(T6)、core/__main__(T7)、manager app/supervisor/ws_client(T8);敏感信息禁记 → Global Constraints + T8 实现只记 code/message/非 token;测试清单 11 项 + 集成 → T1(级别/保留解析含 8/10)、T2(test6 轮转权限)、T3(test7 清理)、T4(test1-5/9/11 + retention env)、T6(集成 BoomProvider 读 core.log);README → T9。无遗漏。
- **Placeholder 扫描**:无 TBD/TODO;每个代码步含完整代码与确切命令。
- **类型一致**:`setup_logging` 签名、`_resolve_level`/`_resolve_retention_days`/`_cleanup_old_logs`/`_SecureTimedRotatingFileHandler`/`_HANDLER_TAG`/`_LOG_PREFIXES`/`_COMPONENTS`/`_FORMAT` 在 T1-4 定义后被一致引用;测试统一用 `_managewidgets` 标记与包 logger 名 `core`/`manager`。
