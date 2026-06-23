# 桌面小组件管理器(第一版:底座 + 管理面板)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个跨发行版的数据底座(常驻进程,采集系统/时间数据并经本地 WebSocket 供数)+ 一个 GTK 管理面板(实时显示并控制底座),作为后续桌面小组件平台的地基。

**Architecture:** 两进程经 `ws://127.0.0.1` 解耦。底座把**纯同步的协议/注册表逻辑(`Hub`)**与**asyncio 传输+调度循环(`server`)**分离,使协议、鉴权、校验可无事件循环单测;面板用 GTK3,WebSocket 客户端跑在独立线程的 asyncio loop 里,UI 更新一律经 `GLib.idle_add` 回主线程。

**Tech Stack:** Python 3.12;`psutil`(系统数据)、`websockets`(传输,含 `websockets.sync.client` 用于测试)、`tomllib`(读)+`tomli-w`(写)配置、PyGObject/GTK 3.0(面板)。依赖装在 `venv --system-site-packages` 内。

## Global Constraints

逐条来自 spec(`docs/superpowers/specs/2026-06-23-widget-manager-platform-design.md`),每个 task 隐含遵守:

- **仅监听 `127.0.0.1`**,拒绝非环回来源;默认端口 `35355`,被占用则顺延。
- **token**:`secrets.token_urlsafe(32)`(256-bit,≥43 个 url-safe 字符);禁用时间戳/PID/`random`/短随机;每次启动重新生成。
- **runtime 文件** `~/.local/state/managewidgets/core.json` 权限 `0600`,内容 `{pid,port,token,started_at,version}`;写法 `mkstemp → fchmod(0600) → 写 → rename`。
- **实例锁**:`flock(LOCK_EX|LOCK_NB)` on `~/.local/state/managewidgets/core.lock`;拿不到即退出。**flock 是实例判定的唯一事实来源**;pid+cmdline 校验只用于 `SIGTERM` 防误杀。
- **interval 边界** `[0.5, 3600]` 秒;越界/非数字 → `invalid_interval`,不改现状。`set_interval` 成功后**立即 poll 一次并重置该 topic 定时器**。
- **错误 code 枚举**:`unauthorized`、`unknown_topic`、`unknown_provider`、`invalid_interval`、`bad_request`。
- **第一版无 topic 级 enabled**:topic 是否活跃 = 其 provider 的 `enabled`。
- **配置** `~/.config/managewidgets/config.toml`;损坏时备份为 `config.toml.bak.YYYYMMDDTHHMMSS`、重建默认、向 `status.core.notices` 追加 `config_reset`。
- **平台**:X11 优先;面板用 GTK **3.0**(本机无 GTK4)。
- **鉴权**:客户端首条消息必须是 `hello` 且带正确 token,否则 `unauthorized` 并断开。全控 token 仅作管理凭证,本版不注入任何小组件。

**包布局**(repo 根下,`core` 与 `manager` 为顶层包):

```
managewidgets/
  pyproject.toml
  .gitignore
  conftest.py
  core/
    __init__.py            # __version__ = "0.1.0"
    providers/{__init__,base,system,time}.py
    config.py
    state.py
    hub.py                 # 纯同步:注册表 + 鉴权 + 请求处理 + 状态快照
    server.py              # asyncio 传输 + 调度循环
    __main__.py            # 入口:锁→配置→server→runtime→信号
  manager/
    __init__.py
    discovery.py           # 读 runtime/config 得到 (port, token)
    ws_client.py           # 线程内 asyncio WS 客户端 + 重连 + 回包关联
    app.py                 # GTK3 应用入口
    pages/{__init__,overview,datasources,widgets_placeholder}.py
  tests/
    test_providers.py test_config.py test_state_discovery.py
    test_hub.py test_core_integration.py test_main_cli.py
    test_discovery.py test_ws_client.py test_manager_smoke.py
```

> 说明:计划在 spec §7 建议结构上新增 `core/hub.py`(把协议逻辑从 asyncio 传输中分离以便纯单测)和 `manager/discovery.py`(端口/token 发现单独成单元),其余一致。

---

### Task 1: 项目脚手架 + venv + Provider 基类 + TimeProvider

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `conftest.py`, `core/__init__.py`, `core/providers/__init__.py`, `core/providers/base.py`, `core/providers/time.py`
- Test: `tests/test_providers.py`

**Interfaces:**
- Produces:
  - `core/__init__.py`: `__version__ = "0.1.0"`
  - `class Provider`: 类属性 `id: str`;方法 `topics() -> list[str]`、`default_interval(topic: str) -> float`、`poll(topic: str) -> dict`(基类抛 `NotImplementedError`)
  - `class TimeProvider(Provider)`: `id = "time"`;`topics() == ["time.now"]`;`default_interval("time.now") == 1.0`;`poll("time.now") -> {"iso": str, "epoch": float, "tz": str}`

- [ ] **Step 1: 先写 `.gitignore`、`pyproject.toml`、`conftest.py`**

`.gitignore`:
```
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

`pyproject.toml`(用 `packages.find` 自动发现,避免显式列尚未创建的包导致安装失败):
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "managewidgets"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["psutil>=5.9", "websockets>=12", "tomli-w>=1.0"]

[project.scripts]
managewidgets-core = "core.__main__:main"
managewidgets-manager = "manager.app:main"

[tool.setuptools.packages.find]
include = ["core*", "manager*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`conftest.py`(空文件,确保 repo 根在 `sys.path`,使 `import core` 可用):
```python
# 让 pytest 从 repo 根导入 core/ 与 manager/ 包
```

- [ ] **Step 2: 建 venv 并装依赖**

PyGObject(`gi`)无法可靠用 pip 装,依赖系统包 + `--system-site-packages`;**前置系统包**(若缺):`python3-gi`、`gir1.2-gtk-3.0`、`gir1.2-webkit2-4.1`。运行时/测试依赖一律装进 venv,**不依赖系统是否预装** psutil/websockets/pytest:

```bash
cd /home/coderyuan/Desktop/managewidgets
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --quiet psutil websockets tomli-w pytest
.venv/bin/python -c "import gi, psutil, websockets, pytest, tomllib, tomli_w; print('deps OK')"
```
Expected: 末行打印 `deps OK`(`gi` 来自系统包,其余来自 venv)

- [ ] **Step 3: 写失败测试 `tests/test_providers.py`**

```python
from core.providers.time import TimeProvider


def test_time_provider_topics_and_interval():
    p = TimeProvider()
    assert p.id == "time"
    assert p.topics() == ["time.now"]
    assert p.default_interval("time.now") == 1.0


def test_time_provider_poll_shape():
    data = TimeProvider().poll("time.now")
    assert set(data) == {"iso", "epoch", "tz"}
    assert isinstance(data["iso"], str) and "T" in data["iso"]
    assert isinstance(data["epoch"], float)
    assert isinstance(data["tz"], str) and data["tz"]
```

- [ ] **Step 4: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'core.providers.time'`）

- [ ] **Step 5: 写 `core/__init__.py` 与 Provider 基类**

`core/__init__.py`:
```python
__version__ = "0.1.0"
```

`core/providers/__init__.py`: 空文件。

`core/providers/base.py`:
```python
class Provider:
    """所有数据源的统一接口。provider 自身无状态(enabled/interval 覆盖由 Hub 持有)。"""

    id: str = ""

    def topics(self) -> list[str]:
        raise NotImplementedError

    def default_interval(self, topic: str) -> float:
        raise NotImplementedError

    def poll(self, topic: str) -> dict:
        raise NotImplementedError
```

- [ ] **Step 6: 写 `core/providers/time.py`**

```python
from datetime import datetime

from core.providers.base import Provider


class TimeProvider(Provider):
    id = "time"

    def topics(self) -> list[str]:
        return ["time.now"]

    def default_interval(self, topic: str) -> float:
        return 1.0

    def poll(self, topic: str) -> dict:
        now = datetime.now().astimezone()
        return {
            "iso": now.isoformat(),
            "epoch": now.timestamp(),
            "tz": now.tzname() or "",
        }
```

- [ ] **Step 7: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: PASS（2 passed）

- [ ] **Step 8: 提交**

```bash
git add .gitignore pyproject.toml conftest.py core tests/test_providers.py
git commit -m "feat(core): 脚手架 + Provider 基类 + TimeProvider"
```

---

### Task 2: SystemProvider(CPU/内存)

**Files:**
- Create: `core/providers/system.py`
- Test: `tests/test_providers.py`(追加)

**Interfaces:**
- Produces: `class SystemProvider(Provider)`: `id = "system"`;`topics() == ["system.cpu", "system.mem"]`;`default_interval` → `system.cpu`=1.0、`system.mem`=2.0;`poll("system.cpu") -> {"percent": float, "per_core": list[float]}`;`poll("system.mem") -> {"percent": float, "used": int, "total": int}`

- [ ] **Step 1: 追加失败测试到 `tests/test_providers.py`**

```python
from core.providers.system import SystemProvider


def test_system_provider_topics_and_intervals():
    p = SystemProvider()
    assert p.id == "system"
    assert p.topics() == ["system.cpu", "system.mem"]
    assert p.default_interval("system.cpu") == 1.0
    assert p.default_interval("system.mem") == 2.0


def test_system_provider_cpu_shape():
    data = SystemProvider().poll("system.cpu")
    assert isinstance(data["percent"], float)
    assert isinstance(data["per_core"], list)
    assert all(isinstance(x, float) for x in data["per_core"])


def test_system_provider_mem_shape():
    data = SystemProvider().poll("system.mem")
    assert isinstance(data["percent"], float)
    assert data["total"] > 0
    assert 0 <= data["used"] <= data["total"]
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_providers.py -k system -v`
Expected: FAIL（`No module named 'core.providers.system'`）

- [ ] **Step 3: 写 `core/providers/system.py`**

```python
import psutil

from core.providers.base import Provider

_INTERVALS = {"system.cpu": 1.0, "system.mem": 2.0}


class SystemProvider(Provider):
    id = "system"

    def topics(self) -> list[str]:
        return ["system.cpu", "system.mem"]

    def default_interval(self, topic: str) -> float:
        return _INTERVALS[topic]

    def poll(self, topic: str) -> dict:
        if topic == "system.cpu":
            return {
                "percent": float(psutil.cpu_percent(interval=None)),
                "per_core": [float(x) for x in psutil.cpu_percent(interval=None, percpu=True)],
            }
        if topic == "system.mem":
            vm = psutil.virtual_memory()
            return {"percent": float(vm.percent), "used": int(vm.used), "total": int(vm.total)}
        raise ValueError(f"unknown topic: {topic}")
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add core/providers/system.py tests/test_providers.py
git commit -m "feat(core): SystemProvider(CPU/内存)"
```

---

### Task 3: 配置读写 + 损坏备份回退

**Files:**
- Create: `core/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - 常量:`DEFAULT_PORT = 35355`、`INTERVAL_MIN = 0.5`、`INTERVAL_MAX = 3600.0`
  - `@dataclass class Config`: 字段 `port: int`、`providers_enabled: dict[str, bool]`、`intervals: dict[str, float]`(**不含 autostart——自启状态以 `.desktop` 文件为准,见 Task 11**);类方法 `Config.default() -> Config`
  - `default_config_path() -> pathlib.Path`(`~/.config/managewidgets/config.toml`)
  - `load_config(path: Path) -> tuple[Config, list[dict]]`:返回 `(config, notices)`;`notices` 每项 `{"code": str, "message": str}`。文件不存在→默认配置+空 notices;文件损坏→把原文件改名为 `config.toml.bak.<UTC紧凑时间戳>`、返回默认配置 + `[{"code":"config_reset","message": ...}]`
  - `save_config(cfg: Config, path: Path) -> None`:原子写(临时文件→rename),父目录自动创建

- [ ] **Step 1: 写失败测试 `tests/test_config.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL（`No module named 'core.config'`）

- [ ] **Step 3: 写 `core/config.py`**

```python
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import tomllib
import tomli_w

DEFAULT_PORT = 35355
INTERVAL_MIN = 0.5
INTERVAL_MAX = 3600.0


# 说明:自启状态以 XDG `~/.config/autostart/*.desktop` 文件为单一事实来源(见 Task 11),
# 不在 config.toml 里重复保存,避免两处状态不一致(与 spec §3.6 一致)。
@dataclass
class Config:
    port: int = DEFAULT_PORT
    providers_enabled: dict = field(default_factory=lambda: {"system": True, "time": True})
    intervals: dict = field(default_factory=dict)   # topic -> 覆盖间隔;缺省走 provider 默认

    @classmethod
    def default(cls) -> "Config":
        return cls()

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "providers_enabled": self.providers_enabled,
            "intervals": self.intervals,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        base = cls.default()
        return cls(
            port=int(d.get("port", base.port)),
            providers_enabled={**base.providers_enabled, **d.get("providers_enabled", {})},
            intervals={str(k): float(v) for k, v in d.get("intervals", {}).items()},
        )


def default_config_path() -> Path:
    return Path.home() / ".config" / "managewidgets" / "config.toml"


def load_config(path: Path) -> tuple[Config, list[dict]]:
    path = Path(path)
    if not path.exists():
        return Config.default(), []
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
        return Config.from_dict(data), []
    except (tomllib.TOMLDecodeError, ValueError, OSError):
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup = path.with_name(f"{path.name}.bak.{ts}")
        try:
            path.rename(backup)
        except OSError:
            backup = None
        notice = {
            "code": "config_reset",
            "message": f"配置文件损坏,已重置;原文件备份为 {backup.name if backup else '(备份失败)'}",
        }
        return Config.default(), [notice]


def save_config(cfg: Config, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".config.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(tomli_w.dumps(cfg.to_dict()).encode("utf-8"))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add core/config.py tests/test_config.py
git commit -m "feat(core): 配置读写 + 损坏备份回退"
```

---

### Task 4: runtime 状态 + token + flock 实例锁

**Files:**
- Create: `core/state.py`
- Test: `tests/test_state_discovery.py`

**Interfaces:**
- Produces:
  - `default_state_dir() -> Path`(`~/.local/state/managewidgets`)
  - `generate_token() -> str`(`secrets.token_urlsafe(32)`)
  - `acquire_instance_lock(lock_path: Path)`:成功返回打开的文件对象(须保持引用以持锁),失败返回 `None`
  - `write_runtime(path: Path, *, pid: int, port: int, token: str, started_at: float, version: str) -> None`:`mkstemp → fchmod(0o600) → 写 → rename`
  - `read_runtime(path: Path) -> dict | None`:不存在/损坏返回 `None`
  - `remove_runtime(path: Path) -> None`
  - `cmdline_is_core(cmdline: str) -> bool`:判断 `/proc/<pid>/cmdline`(NUL 已转空格)是否属于本程序——识别 `managewidgets-core`(console_script)、`python -m core`、`core/__main__.py` 三种入口
  - `pid_is_core(pid: int) -> bool`:pid 存活且 `cmdline_is_core` 为真(用于 §3.7 防误杀)

- [ ] **Step 1: 写失败测试 `tests/test_state_discovery.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_state_discovery.py -v`
Expected: FAIL（`No module named 'core.state'` 或属性缺失）

- [ ] **Step 3: 写 `core/state.py`**

```python
import fcntl
import json
import os
import secrets
import tempfile
from pathlib import Path


def default_state_dir() -> Path:
    return Path.home() / ".local" / "state" / "managewidgets"


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def acquire_instance_lock(lock_path: Path):
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh                                            # 调用方须保持引用;进程退出自动释放


def write_runtime(path: Path, *, pid: int, port: int, token: str,
                  started_at: float, version: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pid": pid, "port": port, "token": token,
               "started_at": started_at, "version": version}
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".core.", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)                             # 先收紧权限再写,避免 chmod 前可读窗口
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_runtime(path: Path) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def remove_runtime(path: Path) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def cmdline_is_core(cmdline: str) -> bool:
    # 同时识别 console_script(`managewidgets-core`)与 `python -m core` / `core/__main__.py`
    if "managewidgets-core" in cmdline:
        return True
    parts = cmdline.split()
    if "-m" in parts and "core" in parts:
        return True
    return any(p.endswith("core/__main__.py") for p in parts)


def pid_is_core(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmdline = f.read().replace(b"\x00", b" ").decode("utf-8", "replace")
    except OSError:
        return False
    return cmdline_is_core(cmdline)
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_state_discovery.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add core/state.py tests/test_state_discovery.py
git commit -m "feat(core): runtime 状态 + 256bit token + flock 实例锁"
```

---

### Task 5: Hub —— 注册表 / 订阅 / 状态快照(纯同步)

**Files:**
- Create: `core/hub.py`
- Test: `tests/test_hub.py`

**Interfaces:**
- Produces:
  - `@dataclass class Conn`: `authed: bool = False`、`subscriptions: set = field(default_factory=set)`
  - `@dataclass class Reply`: `direct: list[dict] = []`(回给本连接的消息)、`broadcast_status: bool = False`、`reset_timer: list[str] = []`(需立即重采并重置定时器的 topic)、`shutdown: bool = False`、`close: bool = False`、`status_request_id: str | None = None`(置位时 server 据该 id 给请求方回完整 status)
  - `class Hub`:
    - `__init__(self, providers: list[Provider], config: Config, token: str, on_change=None)`(`on_change(config)` 在 provider/interval 改动后调用,用于持久化;不传则纯内存,保持单测纯净)
    - `topics() -> list[str]`(所有 provider 的 topic 扁平化)
    - `provider_id_of(topic) -> str | None`
    - `is_active(topic) -> bool`(provider enabled)
    - `interval(topic) -> float`(config 覆盖否则 provider 默认)
    - `record(topic, value, ts, error=None) -> None`(供 server 调度回填 last_value/last_ts/last_error)
    - `providers_snapshot(self) -> list[dict]`(§3.5 的 `providers` 数组,纯逻辑;`core` 实时段由 server 组装,因为 port/clients/uptime 是 server 才知道的)
    - `handle(self, conn: Conn, msg: dict) -> Reply`(Task 6 实现完整动作;本 task 先实现 `subscribe`/`unsubscribe`/`list_providers` 且**假定已鉴权**;`list_providers` 仅置 `Reply.status_request_id`,由 server 回完整 status)

- [ ] **Step 1: 写失败测试 `tests/test_hub.py`**

```python
from core.config import Config
from core.hub import Conn, Hub
from core.providers.system import SystemProvider
from core.providers.time import TimeProvider


def make_hub():
    return Hub([SystemProvider(), TimeProvider()], Config.default(), token="secret")


def test_topics_and_interval_defaults():
    h = make_hub()
    assert set(h.topics()) == {"system.cpu", "system.mem", "time.now"}
    assert h.provider_id_of("system.cpu") == "system"
    assert h.interval("system.cpu") == 1.0
    assert h.interval("system.mem") == 2.0


def test_interval_override_from_config():
    cfg = Config.default()
    cfg.intervals["system.cpu"] = 7.0
    h = Hub([SystemProvider(), TimeProvider()], cfg, token="secret")
    assert h.interval("system.cpu") == 7.0


def test_subscribe_known_topic():
    h = make_hub()
    conn = Conn(authed=True)
    reply = h.handle(conn, {"id": "r1", "action": "subscribe", "topics": ["system.cpu"]})
    assert "system.cpu" in conn.subscriptions
    assert reply.direct == [{"type": "ok", "id": "r1"}]


def test_subscribe_unknown_topic_errors():
    h = make_hub()
    conn = Conn(authed=True)
    reply = h.handle(conn, {"id": "r2", "action": "subscribe", "topics": ["nope.x"]})
    assert "nope.x" not in conn.subscriptions
    assert reply.direct[0]["type"] == "error"
    assert reply.direct[0]["code"] == "unknown_topic"


def test_unsubscribe():
    h = make_hub()
    conn = Conn(authed=True, subscriptions={"system.cpu"})
    h.handle(conn, {"action": "unsubscribe", "topics": ["system.cpu"]})
    assert "system.cpu" not in conn.subscriptions


def test_providers_snapshot_shape():
    h = make_hub()
    h.record("system.cpu", {"percent": 12.0}, ts=100.0)
    providers = h.providers_snapshot()                    # 纯 providers 数组(core 实时段由 server 组装)
    sysprov = next(p for p in providers if p["id"] == "system")
    assert sysprov["enabled"] is True
    assert sysprov["status"] == "running"
    cpu = next(t for t in sysprov["topics"] if t["topic"] == "system.cpu")
    assert cpu["interval"] == 1.0
    assert cpu["last_value"] == {"percent": 12.0}
    assert cpu["last_ts"] == 100.0
    assert cpu["last_error"] is None


def test_list_providers_signals_status_request():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"id": "r3", "action": "list_providers"})
    # Hub 不直接建完整 status(缺 port/clients/uptime),只signal server 用 id 回 status
    assert reply.status_request_id == "r3"
    assert reply.direct == []
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_hub.py -v`
Expected: FAIL（`No module named 'core.hub'`）

- [ ] **Step 3: 写 `core/hub.py`(本 task 仅实现已鉴权的 subscribe/unsubscribe/list_providers)**

```python
from dataclasses import dataclass, field

from core.config import Config
from core.providers.base import Provider


@dataclass
class Conn:
    authed: bool = False
    subscriptions: set = field(default_factory=set)


@dataclass
class Reply:
    direct: list = field(default_factory=list)
    broadcast_status: bool = False
    reset_timer: list = field(default_factory=list)
    shutdown: bool = False
    close: bool = False
    status_request_id: object = None                      # 非 None 时 server 据该 id 回完整 status


class Hub:
    def __init__(self, providers: list[Provider], config: Config, token: str, on_change=None):
        self._providers = {p.id: p for p in providers}
        self._config = config
        self._token = token
        self._on_change = on_change            # 配置变更回调:on_change(config) -> None(用于持久化)
        self._topic_provider = {}
        self._defaults = {}
        for p in providers:
            for t in p.topics():
                self._topic_provider[t] = p.id
                self._defaults[t] = p.default_interval(t)
        self._enabled = {pid: config.providers_enabled.get(pid, True) for pid in self._providers}
        self._last = {t: {"value": None, "ts": None, "error": None} for t in self._topic_provider}

    def _persist(self) -> None:
        if self._on_change:
            self._on_change(self._config)

    # ---- 查询 ----
    def topics(self) -> list[str]:
        return list(self._topic_provider)

    def provider_id_of(self, topic: str):
        return self._topic_provider.get(topic)

    def is_active(self, topic: str) -> bool:
        pid = self._topic_provider.get(topic)
        return bool(pid) and self._enabled.get(pid, False)

    def interval(self, topic: str) -> float:
        return float(self._config.intervals.get(topic, self._defaults[topic]))

    def poll(self, topic: str) -> dict:
        return self._providers[self._topic_provider[topic]].poll(topic)

    def record(self, topic: str, value, ts: float, error=None) -> None:
        if topic in self._last:
            self._last[topic] = {"value": value, "ts": ts, "error": error}

    # ---- providers 快照(纯逻辑;core 实时段由 server 组装)----
    def providers_snapshot(self) -> list:
        providers = []
        for pid, p in self._providers.items():
            topics = []
            has_error = False
            for t in p.topics():
                last = self._last[t]
                if last["error"]:
                    has_error = True
                topics.append({
                    "topic": t, "interval": self.interval(t),
                    "last_value": last["value"], "last_ts": last["ts"],
                    "last_error": last["error"],
                })
            if not self._enabled[pid]:
                status = "disabled"
            elif has_error:
                status = "error"
            else:
                status = "running"
            providers.append({"id": pid, "enabled": self._enabled[pid],
                              "status": status, "topics": topics})
        return providers

    # ---- 请求处理(本 task:已鉴权的数据类动作)----
    def handle(self, conn: Conn, msg: dict) -> Reply:
        action = msg.get("action")
        rid = msg.get("id")
        if action == "subscribe":
            unknown = [t for t in msg.get("topics", []) if t not in self._topic_provider]
            if unknown:
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unknown_topic", "message": f"unknown topic: {unknown[0]}"}])
            conn.subscriptions.update(msg.get("topics", []))
            return Reply(direct=[{"type": "ok", "id": rid}])
        if action == "unsubscribe":
            conn.subscriptions.difference_update(msg.get("topics", []))
            return Reply(direct=[{"type": "ok", "id": rid}])
        if action == "list_providers":
            return Reply(status_request_id=rid)            # server 据 id 回完整 status
        return Reply(direct=[{"type": "error", "id": rid,
                              "code": "bad_request", "message": f"unknown action: {action}"}])
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_hub.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
git add core/hub.py tests/test_hub.py
git commit -m "feat(core): Hub 注册表/订阅/状态快照(纯同步)"
```

---

### Task 6: Hub —— 鉴权 + 控制动作 + 校验

**Files:**
- Modify: `core/hub.py`(扩展 `handle`)
- Test: `tests/test_hub.py`(追加)

**Interfaces:**
- Consumes: Task 5 的 `Hub`、`Conn`、`Reply`、`Config`、`INTERVAL_MIN/MAX`
- Produces: `Hub.handle` 新增处理 `hello`(鉴权)、`set_provider`、`set_interval`、`shutdown`;未鉴权连接除 `hello` 外一律 `unauthorized` 且 `close=True`;`set_provider` 改 `self._enabled[pid]` **并同步 `self._config.providers_enabled[pid]`**;`set_interval` 改 `self._config.intervals[topic]`;两者**改完即调 `self._persist()`(持久化)**并 `broadcast_status`(set_interval 另带 `reset_timer`,由 server 立即重采并重置该 topic 定时器)

- [ ] **Step 1: 追加失败测试到 `tests/test_hub.py`**

```python
from core.config import INTERVAL_MAX, INTERVAL_MIN


def test_unauthed_non_hello_rejected():
    h = make_hub()
    conn = Conn(authed=False)
    reply = h.handle(conn, {"id": "a", "action": "subscribe", "topics": ["system.cpu"]})
    assert reply.direct[0]["type"] == "error"
    assert reply.direct[0]["code"] == "unauthorized"
    assert reply.close is True
    assert "system.cpu" not in conn.subscriptions


def test_hello_wrong_token_rejected():
    h = make_hub()
    conn = Conn(authed=False)
    reply = h.handle(conn, {"id": "h", "action": "hello", "token": "WRONG"})
    assert reply.direct[0]["code"] == "unauthorized"
    assert reply.close is True
    assert conn.authed is False


def test_hello_correct_token_authes():
    h = make_hub()
    conn = Conn(authed=False)
    reply = h.handle(conn, {"id": "h", "action": "hello", "token": "secret"})
    assert conn.authed is True
    assert reply.direct[0] == {"type": "ok", "id": "h"}


def test_set_provider_disables_and_broadcasts():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"id": "s", "action": "set_provider",
                                         "provider": "system", "enabled": False})
    assert reply.direct[0] == {"type": "ok", "id": "s"}
    assert reply.broadcast_status is True
    assert h.is_active("system.cpu") is False


def test_set_provider_unknown():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"action": "set_provider", "provider": "ghost", "enabled": True})
    assert reply.direct[0]["code"] == "unknown_provider"


def test_set_interval_valid_repolls():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"id": "i", "action": "set_interval",
                                         "topic": "system.cpu", "interval": 3.0})
    assert reply.direct[0] == {"type": "ok", "id": "i"}
    assert h.interval("system.cpu") == 3.0
    assert reply.reset_timer == ["system.cpu"]
    assert reply.broadcast_status is True


def test_set_interval_out_of_range():
    h = make_hub()
    for bad in [0.1, 99999, "x", -1]:
        reply = h.handle(Conn(authed=True), {"action": "set_interval",
                                             "topic": "system.cpu", "interval": bad})
        assert reply.direct[0]["code"] == "invalid_interval"
    assert h.interval("system.cpu") == 1.0                # 未被改动


def test_set_interval_unknown_topic():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"action": "set_interval", "topic": "no.x", "interval": 2})
    assert reply.direct[0]["code"] == "unknown_topic"


def test_shutdown():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"id": "q", "action": "shutdown"})
    assert reply.direct[0] == {"type": "ok", "id": "q"}
    assert reply.shutdown is True


def test_bad_request_missing_action():
    h = make_hub()
    reply = h.handle(Conn(authed=True), {"id": "b"})
    assert reply.direct[0]["code"] == "bad_request"


def test_set_provider_and_interval_persist_via_on_change():
    from core.config import Config
    saved = []
    cfg = Config.default()
    h = Hub([SystemProvider(), TimeProvider()], cfg, token="secret",
            on_change=lambda c: saved.append((dict(c.providers_enabled), dict(c.intervals))))
    h.handle(Conn(authed=True), {"action": "set_provider", "provider": "system", "enabled": False})
    h.handle(Conn(authed=True), {"action": "set_interval", "topic": "system.cpu", "interval": 4.0})
    assert len(saved) == 2                                 # 每次改动都触发持久化
    assert cfg.providers_enabled["system"] is False        # 同步回了 config 对象
    assert cfg.intervals["system.cpu"] == 4.0
    assert saved[-1][0]["system"] is False and saved[-1][1]["system.cpu"] == 4.0
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_hub.py -v`
Expected: FAIL（新用例失败:未鉴权未拦截 / 无 hello、set_provider、set_interval、shutdown 分支）

- [ ] **Step 3: 改 `core/hub.py` 的 `handle` 方法**

把 `handle` 整体替换为下面版本(在数据类动作前加鉴权门与控制动作):

```python
    def handle(self, conn: Conn, msg: dict) -> Reply:
        from core.config import INTERVAL_MAX, INTERVAL_MIN
        if not isinstance(msg, dict) or "action" not in msg:
            return Reply(direct=[{"type": "error", "id": (msg or {}).get("id") if isinstance(msg, dict) else None,
                                  "code": "bad_request", "message": "missing action"}])
        action = msg.get("action")
        rid = msg.get("id")

        # 鉴权门:未鉴权时只允许 hello
        if not conn.authed:
            if action != "hello":
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unauthorized", "message": "must authenticate first"}],
                             close=True)
            if msg.get("token") != self._token:
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unauthorized", "message": "bad token"}], close=True)
            conn.authed = True
            return Reply(direct=[{"type": "ok", "id": rid}])

        if action == "hello":
            return Reply(direct=[{"type": "ok", "id": rid}])

        if action == "subscribe":
            unknown = [t for t in msg.get("topics", []) if t not in self._topic_provider]
            if unknown:
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unknown_topic", "message": f"unknown topic: {unknown[0]}"}])
            conn.subscriptions.update(msg.get("topics", []))
            return Reply(direct=[{"type": "ok", "id": rid}])

        if action == "unsubscribe":
            conn.subscriptions.difference_update(msg.get("topics", []))
            return Reply(direct=[{"type": "ok", "id": rid}])

        if action == "list_providers":
            return Reply(status_request_id=rid)            # server 据 id 回完整 status

        if action == "set_provider":
            pid = msg.get("provider")
            if pid not in self._providers:
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unknown_provider", "message": f"unknown provider: {pid}"}])
            enabled = bool(msg.get("enabled", True))
            self._enabled[pid] = enabled
            self._config.providers_enabled[pid] = enabled    # 同步回 config
            self._persist()                                  # 持久化(运行中改动写回)
            return Reply(direct=[{"type": "ok", "id": rid}], broadcast_status=True)

        if action == "set_interval":
            topic = msg.get("topic")
            if topic not in self._topic_provider:
                return Reply(direct=[{"type": "error", "id": rid,
                                      "code": "unknown_topic", "message": f"unknown topic: {topic}"}])
            iv = msg.get("interval")
            if not isinstance(iv, (int, float)) or isinstance(iv, bool) or not (INTERVAL_MIN <= iv <= INTERVAL_MAX):
                return Reply(direct=[{"type": "error", "id": rid, "code": "invalid_interval",
                                      "message": f"interval must be in [{INTERVAL_MIN}, {INTERVAL_MAX}]"}])
            self._config.intervals[topic] = float(iv)
            self._persist()                                  # 持久化(运行中改动写回)
            return Reply(direct=[{"type": "ok", "id": rid}], broadcast_status=True,
                         reset_timer=[topic])

        if action == "shutdown":
            return Reply(direct=[{"type": "ok", "id": rid}], shutdown=True)

        return Reply(direct=[{"type": "error", "id": rid,
                              "code": "bad_request", "message": f"unknown action: {action}"}])
```

> 注意:删除 Task 5 里旧的 `handle`,只保留这一份。`test_subscribe_*`、`test_list_providers_*` 等旧用例此时仍须用 `Conn(authed=True)`(已是)。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_hub.py -v`
Expected: PASS（全部 18 passed,含持久化 on_change 用例）

- [ ] **Step 5: 提交**

```bash
git add core/hub.py tests/test_hub.py
git commit -m "feat(core): Hub 鉴权 + 控制动作 + 校验"
```

---

### Task 7: server —— asyncio 传输 + 调度循环

**Files:**
- Create: `core/server.py`
- Test: `tests/test_core_integration.py`

**Interfaces:**
- Consumes: `Hub`、`Conn`、`Reply`、`Provider` 列表、`websockets`
- Produces:
  - `class CoreServer`:
    - `__init__(self, hub: Hub, host="127.0.0.1", port=0, heartbeat=2.0, notices=None)`(`heartbeat`=status 广播周期秒,≤0 关闭;`notices`=启动告警,进入 `status.core.notices`)
    - `async def serve(self) -> None`(**绑定端口含占用回退**:先试 `self._port`,`OSError` 则用 `0` 交给 OS;启动各 active topic 调度 + status 心跳,阻塞直到 `stop()`)
    - `def actual_port() -> int`(绑定后的真实端口)
    - `def _full_status(self, notices=None) -> dict`(server 组装 `core` 实时段 port/clients/uptime/version + `hub.providers_snapshot()`)
    - `async def stop()` / `def stop_threadsafe()`(优雅停)
    - 内部:每个 active topic 一个 `asyncio.Task`,`sleep(interval) → poll → record → 推送订阅者`;**poll 抛异常 → record(error) 并立即 `_broadcast_status()`**(面板即时见错误态);`reset_timer` 取消并以"立即 poll 一次再进周期"重启;`set_provider` 改 enabled 后按 `is_active` 同步启停 topic 任务;`status_request_id` 时给请求方回 `{type:status,id,...}`;`broadcast_status` 与心跳向所有已鉴权连接发 `status`
  - `start_in_thread(hub, host, port, heartbeat=2.0) -> tuple[CoreServer, threading.Thread, int]`:后台线程跑 `serve`,返回 server、线程、真实端口

- [ ] **Step 1: 写失败测试 `tests/test_core_integration.py`**

```python
import json
import time

from websockets.sync.client import connect

from core.config import Config
from core.hub import Hub
from core.providers.base import Provider
from core.providers.system import SystemProvider
from core.providers.time import TimeProvider
from core.server import start_in_thread


def _hub():
    return Hub([SystemProvider(), TimeProvider()], Config.default(), token="secret")


class BoomProvider(Provider):
    id = "boom"

    def topics(self):
        return ["boom.x"]

    def default_interval(self, topic):
        return 0.5

    def poll(self, topic):
        raise RuntimeError("boom")


# 注意:server 每 ~2s 广播一次 status 心跳,故 data/ok/status 帧会交错。
# 所有断言都按"读到匹配帧为止"进行,绝不假设帧顺序。
def _recv(ws):
    return json.loads(ws.recv(timeout=2))


def _recv_until(ws, pred, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        try:
            m = json.loads(ws.recv(timeout=timeout))
        except Exception:
            break
        if pred(m):
            return m
    raise AssertionError("未在超时内收到期望帧")


def _ok(ws, rid):
    return _recv_until(ws, lambda m: m.get("type") in ("ok", "error") and m.get("id") == rid)


def _hello(ws):
    ws.send(json.dumps({"id": "h", "action": "hello", "token": "secret"}))
    assert _ok(ws, "h")["type"] == "ok"


def test_subscribe_receives_data():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            _hello(ws)
            ws.send(json.dumps({"id": "s", "action": "subscribe", "topics": ["time.now"]}))
            assert _ok(ws, "s")["type"] == "ok"
            msg = _recv_until(ws, lambda m: m.get("type") == "data" and m.get("topic") == "time.now")
            assert "iso" in msg["data"]
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_unauthed_data_request_closed():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            ws.send(json.dumps({"action": "subscribe", "topics": ["time.now"]}))
            reply = _recv(ws)
            assert reply["code"] == "unauthorized"
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_set_interval_changes_push_rate():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            _hello(ws)
            ws.send(json.dumps({"id": "iv", "action": "set_interval", "topic": "time.now", "interval": 0.5}))
            assert _ok(ws, "iv")["type"] == "ok"
            ws.send(json.dumps({"id": "s", "action": "subscribe", "topics": ["time.now"]}))
            assert _ok(ws, "s")["type"] == "ok"
            # 0.5s 周期,~1.6s 内应收到 ≥2 帧 time.now data
            deadline = time.time() + 1.6
            count = 0
            while time.time() < deadline:
                try:
                    m = json.loads(ws.recv(timeout=2))
                except Exception:
                    break
                if m.get("type") == "data" and m.get("topic") == "time.now":
                    count += 1
            assert count >= 2
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_disable_provider_stops_topic():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            _hello(ws)
            ws.send(json.dumps({"id": "s", "action": "subscribe", "topics": ["time.now"]}))
            assert _ok(ws, "s")["type"] == "ok"
            _recv_until(ws, lambda m: m.get("type") == "data" and m.get("topic") == "time.now")
            ws.send(json.dumps({"id": "d", "action": "set_provider", "provider": "time", "enabled": False}))
            assert _ok(ws, "d")["type"] == "ok"
            time.sleep(0.6)                              # 让在途帧排空
            # 之后 1.5s 内不应再出现 time.now 的 data(status 心跳帧会被忽略)
            drained = True
            end = time.time() + 1.5
            while time.time() < end:
                try:
                    m = json.loads(ws.recv(timeout=2))
                except Exception:
                    break
                if m.get("type") == "data" and m.get("topic") == "time.now":
                    drained = False
                    break
            assert drained
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)


def test_provider_error_broadcasts_status():
    hub = Hub([BoomProvider()], Config.default(), token="secret")
    server, thread, port = start_in_thread(hub, "127.0.0.1", 0)
    try:
        with connect(f"ws://127.0.0.1:{port}") as ws:
            _hello(ws)
            # poll 抛异常后 server 立即广播 status:provider=error、topic.last_error 有值
            status = _recv_until(
                ws,
                lambda m: m.get("type") == "status"
                and any(p["id"] == "boom" and p["status"] == "error"
                        for p in m["status"]["providers"]),
                timeout=4,
            )["status"]
            boom = next(p for p in status["providers"] if p["id"] == "boom")
            assert boom["topics"][0]["last_error"] is not None
    finally:
        server.stop_threadsafe(); thread.join(timeout=5)
```

> 用 `ws.recv(timeout=2)`(websockets 16 sync API 支持 `timeout` 形参)。所有断言按"读到匹配帧为止",因此与 status 心跳帧交错无关。

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_core_integration.py -v`
Expected: FAIL（`No module named 'core.server'`）

- [ ] **Step 3: 写 `core/server.py`**

```python
import asyncio
import json
import threading
import time

import websockets

from core.hub import Conn, Hub


class CoreServer:
    def __init__(self, hub: Hub, host: str = "127.0.0.1", port: int = 0,
                 heartbeat: float = 2.0, notices=None):
        self._hub = hub
        self._host = host
        self._port = port
        self._heartbeat = heartbeat             # status 心跳广播周期(秒);<=0 关闭
        self._notices = notices or []           # 启动告警(如 config_reset),进入 status.core.notices
        self._hb_task = None
        self._actual_port = None
        self._conns: dict = {}                  # ws -> Conn
        self._tasks: dict = {}                  # topic -> asyncio.Task
        self._loop = None
        self._server = None
        self._started_at = time.time()
        self._stop_event = None

    def actual_port(self) -> int:
        return self._actual_port

    async def serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        try:                                              # 端口回退:占用→交给 OS 选端口
            server = await websockets.serve(self._handler, self._host, self._port)
        except OSError:
            server = await websockets.serve(self._handler, self._host, 0)
        try:
            self._server = server
            self._actual_port = server.sockets[0].getsockname()[1]
            for topic in self._hub.topics():
                if self._hub.is_active(topic):
                    self._start_topic(topic)
            if self._heartbeat > 0:
                self._hb_task = self._loop.create_task(self._heartbeat_loop())
            await self._stop_event.wait()
        finally:
            if self._hb_task:
                self._hb_task.cancel()
            for t in list(self._tasks.values()):
                t.cancel()
            server.close()
            await server.wait_closed()

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(self._heartbeat)
                await self._broadcast_status()
        except asyncio.CancelledError:
            return

    def _start_topic(self, topic: str):
        if topic in self._tasks:
            self._tasks[topic].cancel()
        self._tasks[topic] = self._loop.create_task(self._poll_loop(topic))

    async def _poll_loop(self, topic: str, immediate: bool = False):
        try:
            if not immediate:
                await asyncio.sleep(self._hub.interval(topic))
            while True:
                try:
                    value = self._hub.poll(topic)
                    self._hub.record(topic, value, ts=time.time())
                    await self._push(topic, value)
                except Exception as exc:                 # provider 采集异常:记错,不杀循环
                    self._hub.record(topic, None, ts=time.time(), error=str(exc))
                    await self._broadcast_status()       # 立即让面板看到错误态,不等心跳
                await asyncio.sleep(self._hub.interval(topic))
        except asyncio.CancelledError:
            return

    async def _push(self, topic: str, value):
        frame = json.dumps({"type": "data", "topic": topic, "data": value, "ts": time.time()})
        for ws, conn in list(self._conns.items()):
            if conn.authed and topic in conn.subscriptions:
                try:
                    await ws.send(frame)
                except Exception:
                    pass

    def _full_status(self, notices=None) -> dict:
        # core 实时段由 server 组装(port/clients/uptime/version);providers 数组来自 hub
        import core
        return {
            "core": {
                "port": self._actual_port,
                "clients": sum(1 for c in self._conns.values() if c.authed),
                "uptime": time.time() - self._started_at,
                "version": core.__version__,
                "notices": notices if notices is not None else self._notices,
            },
            "providers": self._hub.providers_snapshot(),
        }

    async def _broadcast_status(self):
        frame = json.dumps({"type": "status", "status": self._full_status()})
        for ws, conn in list(self._conns.items()):
            if conn.authed:
                try:
                    await ws.send(frame)
                except Exception:
                    pass

    def _apply_effects(self, reply):
        # 由 _handler 在收到 reply 后调用(同一事件循环内)
        for topic in reply.reset_timer:
            # 立即 poll 一次并以新周期重启
            if topic in self._tasks:
                self._tasks[topic].cancel()
            if self._hub.is_active(topic):
                self._tasks[topic] = self._loop.create_task(self._poll_loop(topic, immediate=True))
        # set_provider 改变 enabled:同步启停该 provider 所有 topic
        for topic in self._hub.topics():
            active = self._hub.is_active(topic)
            running = topic in self._tasks and not self._tasks[topic].done()
            if active and not running:
                self._start_topic(topic)
            if not active and running:
                self._tasks[topic].cancel()

    async def _handler(self, ws):
        conn = Conn()
        self._conns[ws] = conn
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"type": "error", "code": "bad_request",
                                              "message": "invalid json"}))
                    continue
                reply = self._hub.handle(conn, msg)
                for out in reply.direct:
                    await ws.send(json.dumps(out))
                if reply.status_request_id is not None:
                    await ws.send(json.dumps({"type": "status", "id": reply.status_request_id,
                                              "status": self._full_status()}))
                if reply.broadcast_status or reply.reset_timer:
                    self._apply_effects(reply)
                if reply.broadcast_status:
                    await self._broadcast_status()
                if reply.shutdown:
                    self._stop_event.set()
                    break
                if reply.close:
                    break
        except websockets.ConnectionClosed:
            pass
        finally:
            self._conns.pop(ws, None)

    async def stop(self) -> None:
        if self._stop_event:
            self._stop_event.set()

    def stop_threadsafe(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(lambda: self._stop_event.set())


def start_in_thread(hub: Hub, host: str = "127.0.0.1", port: int = 0, heartbeat: float = 2.0):
    server = CoreServer(hub, host, port, heartbeat=heartbeat)
    ready = threading.Event()

    def run():
        async def main():
            ready_task = asyncio.create_task(server.serve())
            # 等 actual_port 就绪后通知
            while server.actual_port() is None:
                await asyncio.sleep(0.01)
            ready.set()
            await ready_task
        asyncio.run(main())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    ready.wait(timeout=5)
    return server, thread, server.actual_port()
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_core_integration.py -v`
Expected: PASS（5 passed;若个别用例因时序偶发,重跑确认稳定）

- [ ] **Step 5: 提交**

```bash
git add core/server.py tests/test_core_integration.py
git commit -m "feat(core): asyncio 传输 + 调度循环 + 立即重采/启停"
```

---

### Task 8: 底座入口 __main__ —— 实例锁 / 启动 / 优雅停止

**Files:**
- Create: `core/__main__.py`
- Test: `tests/test_main_cli.py`

**Interfaces:**
- Consumes: `acquire_instance_lock`、`generate_token`、`write_runtime`/`read_runtime`/`remove_runtime`、`default_state_dir`、`load_config`、`default_config_path`、`Hub`、`CoreServer`、provider 类、`core.__version__`
- Produces:
  - `def build_hub(config, token, on_change=None) -> Hub`(组装 system+time provider,转发 `on_change`)
  - `def main(argv=None) -> int`:① 取实例锁,失败→打印已有端口、返回 3;② 删除残留 runtime;③ 加载配置(保留 `notices`);④ 生成 token、`build_hub(on_change=保存 config.toml)`、起 `CoreServer(port=config.port, notices=notices)`;⑤ 写 runtime(pid/port/token/started_at/version);⑥ 注册 SIGTERM/SIGINT → 优雅停;⑦ 退出时 `remove_runtime`。返回 0
  - 模块可执行:`python -m core` 调 `main()`

- [ ] **Step 1: 写失败测试 `tests/test_main_cli.py`**

```python
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
```

> 注:测试用 `python -m core` 起进程;`cmdline_is_core` 已识别该入口(T4),故面板的 `SIGTERM` 兜底对这种方式启动的底座同样有效。

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_main_cli.py -v`
Expected: FAIL（`No module named core.__main__` 或无 main）

- [ ] **Step 3: 写 `core/__main__.py`**

```python
import asyncio
import os
import signal
import sys
import threading
import time

from core import __version__
from core.config import default_config_path, load_config, save_config
from core.hub import Hub
from core.providers.system import SystemProvider
from core.providers.time import TimeProvider
from core.server import CoreServer
from core.state import (
    acquire_instance_lock,
    default_state_dir,
    generate_token,
    read_runtime,
    remove_runtime,
    write_runtime,
)


def build_hub(config, token: str, on_change=None) -> Hub:
    return Hub([SystemProvider(), TimeProvider()], config, token, on_change=on_change)


def main(argv=None) -> int:
    state_dir = default_state_dir()
    lock_path = state_dir / "core.lock"
    runtime_path = state_dir / "core.json"

    lock = acquire_instance_lock(lock_path)
    if lock is None:
        existing = read_runtime(runtime_path)
        port = existing.get("port") if existing else "?"
        print(f"managewidgets-core 已在运行(port={port}),不启动第二个实例", file=sys.stderr)
        return 3

    remove_runtime(runtime_path)                          # 拿到锁 = 无有效实例,残留一律丢弃
    config_path = default_config_path()
    config, notices = load_config(config_path)            # 保留 notices(如 config_reset)
    token = generate_token()
    # provider/interval 改动 → 写回 config.toml(spec:运行中改动持久化)
    hub = build_hub(config, token, on_change=lambda cfg: save_config(cfg, config_path))
    server = CoreServer(hub, host="127.0.0.1", port=config.port, notices=notices)

    started = time.time()

    def run_server():
        async def main_coro():
            serve_task = asyncio.create_task(server.serve())
            while server.actual_port() is None:
                await asyncio.sleep(0.01)
            write_runtime(runtime_path, pid=os.getpid(),
                          port=server.actual_port(), token=token,
                          started_at=started, version=__version__)
            await serve_task
        asyncio.run(main_coro())

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    stop = threading.Event()

    def _graceful(signum, frame):
        server.stop_threadsafe()
        stop.set()

    signal.signal(signal.SIGTERM, _graceful)
    signal.signal(signal.SIGINT, _graceful)

    try:
        while t.is_alive() and not stop.is_set():
            t.join(timeout=0.2)
    finally:
        server.stop_threadsafe()
        t.join(timeout=5)
        remove_runtime(runtime_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> 端口回退已在 Task 7 的 `serve()` 内实现(占用→`0` 交给 OS),`__main__` 只需把 `config.port` 作首选传入,无需再改 `server.py`。

- [ ] **Step 4: 运行确认通过(含回归)**

Run: `.venv/bin/python -m pytest tests/test_main_cli.py tests/test_core_integration.py -v`
Expected: PASS（main_cli 5 passed,且回归 integration 仍全过）

- [ ] **Step 5: 提交**

```bash
git add core/__main__.py tests/test_main_cli.py
git commit -m "feat(core): 底座入口 实例锁/runtime/优雅停止/配置持久化/notice"
```

---

### Task 9: 面板侧 —— 端口/token 发现 + WS 客户端(线程内 asyncio)

**Files:**
- Create: `manager/__init__.py`, `manager/discovery.py`, `manager/ws_client.py`
- Test: `tests/test_discovery.py`, `tests/test_ws_client.py`

**Interfaces:**
- Produces:
  - `manager/discovery.py`:`discover(runtime_path: Path, config_path: Path) -> tuple[str, int, str | None]` 返回 `(host, port, token)`;优先 runtime(`core.json` 的 port+token),否则回退 config 默认端口(token=None);两者皆缺时回退 `("127.0.0.1", DEFAULT_PORT, None)`
  - `manager/ws_client.py`:`class CoreClient`
    - `__init__(self, host, port, token, on_event, on_state)`:`on_event(dict)`/`on_state(str)` 由调用方负责切回 GTK 主线程
    - `start()`:起后台线程跑 asyncio loop,连后先发 `hello`+token,再回放调用方设定的订阅;断线指数退避重连(0.5→1→2→…→最多 10s),**退避用可唤醒的 `asyncio.Event` 等待而非裸 `sleep`,以便 `stop()` 立即打断**
    - `send(msg: dict, on_reply=None)`:线程安全;**消息入待发队列,未连上/重连中不丢,连上(hello ok)后统一 flush**
    - `subscribe(topics: list[str])`:更新 `self._subs`(订阅事实来源);**已连则立即补订新 topic,未连则由连接成功路径按 `_subs` 统一发一次**(避免重复 subscribe);每次(重)连都按 `_subs` 重订阅
    - `is_connected() -> bool`:是否已鉴权连上(供面板"停止底座"决定走 WS shutdown 还是 SIGTERM 兜底)
    - `stop()`:置 `_stop`、`call_soon_threadsafe` **唤醒退避 `_wake` 并关连接**、`join` 线程(不留悬挂 daemon,即便正处于重连退避)
    - 回包关联:带 `id` 的请求,其 `ok`/`error` 响应据 `id` 回调 `on_reply`

- [ ] **Step 1: 写失败测试 `tests/test_discovery.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_discovery.py -v`
Expected: FAIL（`No module named 'manager.discovery'`）

- [ ] **Step 3: 写 `manager/__init__.py`(空)与 `manager/discovery.py`**

```python
from pathlib import Path

from core.config import DEFAULT_PORT, load_config
from core.state import read_runtime


def discover(runtime_path: Path, config_path: Path) -> tuple[str, int, str | None]:
    rt = read_runtime(runtime_path)
    if rt and rt.get("port"):
        return "127.0.0.1", int(rt["port"]), rt.get("token")
    cfg, _ = load_config(config_path)
    return "127.0.0.1", int(cfg.port), None
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_discovery.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 写失败测试 `tests/test_ws_client.py`(对真 core 端到端)**

```python
import threading
import time

from core.config import Config
from core.hub import Hub
from core.providers.system import SystemProvider
from core.providers.time import TimeProvider
from core.server import start_in_thread
from manager.ws_client import CoreClient


def _hub():
    return Hub([SystemProvider(), TimeProvider()], Config.default(), token="secret")


def test_client_connects_subscribes_and_receives():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    events = []
    lock = threading.Lock()

    def on_event(msg):
        with lock:
            events.append(msg)

    client = CoreClient("127.0.0.1", port, "secret", on_event=on_event, on_state=lambda s: None)
    client.start()
    client.subscribe(["time.now"])
    try:
        deadline = time.time() + 4
        got = False
        while time.time() < deadline:
            with lock:
                got = any(e.get("type") == "data" and e.get("topic") == "time.now" for e in events)
            if got:
                break
            time.sleep(0.1)
        assert got
    finally:
        client.stop()
        server.stop_threadsafe(); thread.join(timeout=5)


def test_send_before_connect_is_queued_and_delivered():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    events = []
    lock = threading.Lock()

    def on_event(m):
        with lock:
            events.append(m)

    client = CoreClient("127.0.0.1", port, "secret", on_event=on_event, on_state=lambda s: None)
    client.start()
    client.send({"id": "ls", "action": "list_providers"})   # 紧接 start,此刻多半还没连上
    try:
        deadline = time.time() + 4
        got = False
        while time.time() < deadline:
            with lock:
                got = any(m.get("type") == "status" and m.get("id") == "ls" for m in events)
            if got:
                break
            time.sleep(0.1)
        assert got                                          # 未连上时入队,连上后送达,不丢
    finally:
        client.stop()
        server.stop_threadsafe(); thread.join(timeout=5)


def test_subscribe_after_connected_takes_effect():
    # 显式覆盖 subscribe() 的"已连接 → 立即补订"分支
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    events = []
    lock = threading.Lock()

    def on_event(m):
        with lock:
            events.append(m)

    client = CoreClient("127.0.0.1", port, "secret", on_event=on_event, on_state=lambda s: None)
    client.start()                                       # 注意:连接前不订阅任何 topic
    try:
        deadline = time.time() + 4
        while time.time() < deadline and not client.is_connected():
            time.sleep(0.05)
        assert client.is_connected()                     # 已连接
        client.subscribe(["system.cpu"])                 # 连接后才订阅 → 走即时补订分支
        got = False
        deadline = time.time() + 4
        while time.time() < deadline:
            with lock:
                got = any(m.get("type") == "data" and m.get("topic") == "system.cpu" for m in events)
            if got:
                break
            time.sleep(0.1)
        assert got                                        # 补订生效,收到 system.cpu 数据
    finally:
        client.stop()
        server.stop_threadsafe(); thread.join(timeout=5)


def test_stop_interrupts_reconnect_backoff():
    import socket as _socket
    # 动态取一个空闲端口再关闭,确保无人监听(比硬编码 127.0.0.1:1 更稳)
    _s = _socket.socket()
    _s.bind(("127.0.0.1", 0))
    dead_port = _s.getsockname()[1]
    _s.close()
    # 连这个没人监听的端口 → client 进入重连退避;stop() 必须能立刻唤醒并让线程退出
    client = CoreClient("127.0.0.1", dead_port, "secret", on_event=lambda m: None, on_state=lambda s: None)
    client.start()
    time.sleep(0.4)                                       # 让它至少进入一次退避等待
    t0 = time.time()
    client.stop()                                         # 内部 join(timeout=5)
    assert client._thread is not None
    assert not client._thread.is_alive()                 # 线程已退出,无悬挂 daemon
    assert time.time() - t0 < 3                           # 远小于 backoff 上限,证明是被唤醒而非等满


def test_client_rejected_on_bad_token_then_state_reports():
    server, thread, port = start_in_thread(_hub(), "127.0.0.1", 0)
    states = []
    client = CoreClient("127.0.0.1", port, "WRONG", on_event=lambda m: None,
                        on_state=lambda s: states.append(s))
    client.start()
    try:
        deadline = time.time() + 4
        while time.time() < deadline and "disconnected" not in states:
            time.sleep(0.1)
        assert "disconnected" in states or "error" in states
    finally:
        client.stop()
        server.stop_threadsafe(); thread.join(timeout=5)
```

- [ ] **Step 6: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_ws_client.py -v`
Expected: FAIL（`No module named 'manager.ws_client'`）

- [ ] **Step 7: 写 `manager/ws_client.py`**

```python
import asyncio
import json
import threading

import websockets


class CoreClient:
    def __init__(self, host, port, token, on_event, on_state):
        self._host = host
        self._port = port
        self._token = token
        self._on_event = on_event                         # 调用方负责切回 GTK 主线程
        self._on_state = on_state
        self._loop = None
        self._thread = None
        self._ws = None
        self._stop = False
        self._wake = None                                 # asyncio.Event,用于打断重连退避(stop 时唤醒)
        self._connected = False                           # 是否已鉴权连上(供面板停止决策)
        self._subs = set()
        self._pending = {}                                # id -> on_reply
        self._outbox = []                                 # 待发送队列(未连上时暂存,连上后 flush)
        self._outlock = threading.Lock()

    def is_connected(self) -> bool:
        return self._connected

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def subscribe(self, topics):
        self._subs.update(topics)                         # _subs 是订阅的事实来源
        if self._connected:                               # 已连:立即补订新 topic
            self.send({"action": "subscribe", "topics": list(topics)})
        # 未连:连接成功时由 _main 统一按 _subs 发送一次,避免重复 subscribe

    def send(self, msg, on_reply=None):
        # 入队而非直发:未连上/重连中也不丢,连上(hello ok)后统一 flush
        if on_reply and msg.get("id"):
            self._pending[msg["id"]] = on_reply
        with self._outlock:
            self._outbox.append(msg)
        if self._loop:
            self._loop.call_soon_threadsafe(lambda: self._loop.create_task(self._flush()))

    async def _flush(self):
        if self._ws is None or not self._connected:
            return
        with self._outlock:
            pending, self._outbox = self._outbox, []
        for i, m in enumerate(pending):
            try:
                await self._ws.send(json.dumps(m))
            except Exception:
                with self._outlock:                       # 失败:当前 m + 剩余未发的整体放回队首(保序)
                    self._outbox[:0] = pending[i:]
                break

    def _run(self):
        asyncio.run(self._main())

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        backoff = 0.5
        while not self._stop:
            try:
                async with websockets.connect(f"ws://{self._host}:{self._port}") as ws:
                    self._ws = ws
                    await ws.send(json.dumps({"id": "hello", "action": "hello", "token": self._token}))
                    ack = json.loads(await ws.recv())
                    if ack.get("type") != "ok":
                        self._on_state("error")
                        self._ws = None
                        await ws.close()
                        # 鉴权失败不无限重连
                        self._on_state("disconnected")
                        return
                    self._connected = True
                    self._on_state("connected")
                    backoff = 0.5
                    if self._subs:                        # 每次(重)连重订阅 + flush 暂存的控制消息
                        with self._outlock:
                            self._outbox.insert(0, {"action": "subscribe", "topics": list(self._subs)})
                    await self._flush()
                    async for raw in ws:
                        msg = json.loads(raw)
                        rid = msg.get("id")
                        if rid in self._pending and msg.get("type") in ("ok", "error"):
                            cb = self._pending.pop(rid)
                            cb(msg)
                        else:
                            self._on_event(msg)
            except Exception:
                self._on_state("disconnected")
            finally:
                self._ws = None
                self._connected = False
            if self._stop:
                break
            try:                                          # 可被 stop() 唤醒的退避等待(替代裸 sleep)
                await asyncio.wait_for(self._wake.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
            backoff = min(backoff * 2, 10)

    def stop(self):
        self._stop = True
        if self._loop:
            def _wake_and_close():
                if self._wake is not None:               # 唤醒退避中的 sleep,立即退出循环
                    self._wake.set()
                if self._ws is not None:
                    self._loop.create_task(self._ws.close())
            try:
                self._loop.call_soon_threadsafe(_wake_and_close)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)
```

- [ ] **Step 8: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_ws_client.py tests/test_discovery.py -v`
Expected: PASS（8 passed）

- [ ] **Step 9: 提交**

```bash
git add manager/__init__.py manager/discovery.py manager/ws_client.py tests/test_discovery.py tests/test_ws_client.py
git commit -m "feat(manager): 端口/token 发现 + 线程内 asyncio WS 客户端"
```

---

### Task 10: 管理面板 GTK3 —— 三页 + 接线 + 冒烟

**Files:**
- Create: `manager/app.py`, `manager/pages/__init__.py`, `manager/pages/overview.py`, `manager/pages/datasources.py`, `manager/pages/widgets_placeholder.py`
- Test: `tests/test_manager_smoke.py`

**Interfaces:**
- Consumes: `CoreClient`、`discover`、`default_state_dir`、`default_config_path`、GTK 3.0
- Produces:
  - `manager/app.py`:`class ManagerApp`(`Gtk.Application` 子类);`def main() -> int`
    - 构造主窗口 + `Gtk.Notebook` 三页;启动时 `discover` → `CoreClient`,所有 `on_event`/`on_state` 回调用 `GLib.idle_add` 切回主线程更新对应页;窗口 `destroy` 时 `client.stop()`
    - **`_start_core`**:`Popen([sys.executable,"-m","core"])` 后用 `GLib.timeout_add` 轮询 runtime 文件出现,出现即 `_reconnect()`(`client.stop()` → `_connect_client()` 重新 discover 拿新 token 再连)——保证一键启动后真正接上
    - **`_stop_core`**:`client.is_connected()` → 发 WS `shutdown`;否则读 runtime、`pid_is_core` 校验后 `os.kill(pid, SIGTERM)` 兜底(spec §3.7)
  - `pages/overview.py`:`class OverviewPage(Gtk.Box)`:显示端口/客户端数/运行时长/连接状态;"启动底座""停止底座"按钮(回调到 app 的 `_start_core`/`_stop_core`);`update(status_dict)`;`set_connection(state)`;渲染 `core.notices`
  - `pages/datasources.py`:`class DataSourcesPage(Gtk.Box)`:按 provider 分组,组标题带启用开关(`set_provider`),topic 行显示实时值 + 间隔 `Gtk.SpinButton`(`set_interval`);`update(status_dict)`、`apply_data(topic, value)`
  - `pages/widgets_placeholder.py`:`class WidgetsPlaceholderPage(Gtk.Box)`:静态空状态文案

- [ ] **Step 1: 写冒烟测试 `tests/test_manager_smoke.py`**

```python
import os

import pytest

pytest.importorskip("gi")
gi = __import__("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk    # noqa: E402

# 无显示环境(CI)跳过:GTK 需要 X/Wayland
HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
pytestmark = pytest.mark.skipif(not HAS_DISPLAY, reason="需要图形显示")


def test_pages_construct():
    from manager.pages.overview import OverviewPage
    from manager.pages.datasources import DataSourcesPage
    from manager.pages.widgets_placeholder import WidgetsPlaceholderPage

    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None)
    ds = DataSourcesPage(on_set_provider=lambda p, e: None, on_set_interval=lambda t, i: None)
    wp = WidgetsPlaceholderPage()
    assert isinstance(ov, Gtk.Box) and isinstance(ds, Gtk.Box) and isinstance(wp, Gtk.Box)


def test_datasources_update_renders_topics():
    from manager.pages.datasources import DataSourcesPage
    ds = DataSourcesPage(on_set_provider=lambda p, e: None, on_set_interval=lambda t, i: None)
    snap = {
        "core": {"clients": 1, "uptime": 1.0, "version": "0.1.0", "notices": []},
        "providers": [{"id": "system", "enabled": True, "status": "running", "topics": [
            {"topic": "system.cpu", "interval": 1.0, "last_value": {"percent": 5.0},
             "last_ts": 1.0, "last_error": None}]}],
    }
    ds.update(snap)                                       # 不抛即通过
    assert ds.has_topic_row("system.cpu")
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_manager_smoke.py -v`
Expected: FAIL（无 `manager.pages.*`）或 SKIP(无显示)。若 SKIP,在有图形会话的终端跑同一命令应 FAIL。

- [ ] **Step 3: 写 `manager/pages/__init__.py`(空)与三个页面**

`manager/pages/widgets_placeholder.py`:
```python
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class WidgetsPlaceholderPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_border_width(24)
        title = Gtk.Label(label="小组件渲染功能开发中")
        title.get_style_context().add_class("dim-label")
        body = Gtk.Label(label="后续将支持:贴桌面、Web 小组件(HTML/CSS/JS)、订阅底座数据。")
        body.set_line_wrap(True)
        self.pack_start(title, False, False, 0)
        self.pack_start(body, False, False, 0)
```

`manager/pages/overview.py`:
```python
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class OverviewPage(Gtk.Box):
    def __init__(self, on_start, on_stop):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_border_width(20)
        self._conn = Gtk.Label(label="未连接", xalign=0)
        self._info = Gtk.Label(label="端口:- | 客户端:- | 运行时长:-", xalign=0)
        self._notices = Gtk.Label(label="", xalign=0)
        self._notices.get_style_context().add_class("error")
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        start_btn = Gtk.Button(label="启动底座")
        stop_btn = Gtk.Button(label="停止底座")
        start_btn.connect("clicked", lambda *_: on_start())
        stop_btn.connect("clicked", lambda *_: on_stop())
        btns.pack_start(start_btn, False, False, 0)
        btns.pack_start(stop_btn, False, False, 0)
        for w in (self._conn, self._info, self._notices, btns):
            self.pack_start(w, False, False, 0)

    def set_connection(self, state):
        self._conn.set_text({"connected": "已连接", "disconnected": "未连接",
                             "error": "鉴权失败"}.get(state, state))

    def update(self, status):
        core = status.get("core", {})
        self._info.set_text(
            f"端口:{core.get('port', '-')} | 客户端:{core.get('clients', '-')} "
            f"| 运行时长:{core.get('uptime', 0):.0f}s")
        notices = core.get("notices", [])
        self._notices.set_text("；".join(n.get("message", "") for n in notices))
```

`manager/pages/datasources.py`:
```python
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class DataSourcesPage(Gtk.Box):
    def __init__(self, on_set_provider, on_set_interval):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_border_width(16)
        self._on_set_provider = on_set_provider
        self._on_set_interval = on_set_interval
        self._rows = {}                                   # topic -> {"value": Label, "spin": SpinButton}
        self._groups = {}                                 # provider -> Gtk.Box
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.pack_start(self._container, True, True, 0)

    def has_topic_row(self, topic):
        return topic in self._rows

    def _ensure_group(self, pid, enabled):
        if pid in self._groups:
            return self._groups[pid]
        frame = Gtk.Frame(label=pid)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(8)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sw = Gtk.Switch()
        sw.set_active(enabled)
        sw.connect("notify::active", lambda s, _p: self._on_set_provider(pid, s.get_active()))
        header.pack_start(Gtk.Label(label="启用", xalign=0), False, False, 0)
        header.pack_start(sw, False, False, 0)
        box.pack_start(header, False, False, 0)
        frame.add(box)
        self._container.pack_start(frame, False, False, 0)
        self._groups[pid] = box
        return box

    def _ensure_row(self, box, topic, interval):
        if topic in self._rows:
            return
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name = Gtk.Label(label=topic, xalign=0)
        value = Gtk.Label(label="-", xalign=0)
        spin = Gtk.SpinButton.new_with_range(0.5, 3600, 0.5)
        spin.set_value(interval)
        spin.connect("value-changed", lambda s: self._on_set_interval(topic, s.get_value()))
        row.pack_start(name, True, True, 0)
        row.pack_start(value, False, False, 0)
        row.pack_start(spin, False, False, 0)
        box.pack_start(row, False, False, 0)
        self._rows[topic] = {"value": value, "spin": spin}
        row.show_all()

    def update(self, status):
        for prov in status.get("providers", []):
            box = self._ensure_group(prov["id"], prov["enabled"])
            for t in prov["topics"]:
                self._ensure_row(box, t["topic"], t["interval"])
                if t["last_value"] is not None:
                    self.apply_data(t["topic"], t["last_value"])

    def apply_data(self, topic, value):
        if topic in self._rows:
            self._rows[topic]["value"].set_text(str(value))
```

`manager/app.py`:
```python
import os
import signal
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from core.config import default_config_path
from core.state import default_state_dir, pid_is_core, read_runtime
from manager.discovery import discover
from manager.pages.datasources import DataSourcesPage
from manager.pages.overview import OverviewPage
from manager.pages.widgets_placeholder import WidgetsPlaceholderPage
from manager.ws_client import CoreClient


class ManagerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.managewidgets.Manager")
        self._client = None

    def do_activate(self):
        win = Gtk.ApplicationWindow(application=self, title="小组件管理器")
        win.set_default_size(560, 460)
        nb = Gtk.Notebook()
        self._overview = OverviewPage(on_start=self._start_core, on_stop=self._stop_core)
        self._datasources = DataSourcesPage(on_set_provider=self._set_provider,
                                            on_set_interval=self._set_interval)
        nb.append_page(self._overview, Gtk.Label(label="概览"))
        nb.append_page(self._datasources, Gtk.Label(label="数据源"))
        nb.append_page(WidgetsPlaceholderPage(), Gtk.Label(label="小组件"))
        win.add(nb)
        win.connect("destroy", lambda *_: self._shutdown_client())
        win.show_all()
        self._connect_client()

    def _runtime_path(self):
        return default_state_dir() / "core.json"

    def _connect_client(self):
        host, port, token = discover(self._runtime_path(), default_config_path())
        self._client = CoreClient(host, port, token,
                                  on_event=lambda m: GLib.idle_add(self._on_event, m),
                                  on_state=lambda s: GLib.idle_add(self._overview.set_connection, s))
        self._client.start()
        self._client.subscribe(["system.cpu", "system.mem", "time.now"])
        self._client.send({"id": "ls", "action": "list_providers"})

    def _on_event(self, msg):
        if msg.get("type") == "data":
            self._datasources.apply_data(msg["topic"], msg["data"])
        elif msg.get("type") == "status":
            self._overview.update(msg["status"])
            self._datasources.update(msg["status"])
        return False

    def _start_core(self):
        # 拉起底座子进程后,轮询 runtime 文件出现 → 用新 token 重建客户端真正接上
        subprocess.Popen([sys.executable, "-m", "core"])
        self._start_polls = 0
        GLib.timeout_add(500, self._reconnect_when_ready)

    def _reconnect_when_ready(self):
        self._start_polls += 1
        if self._runtime_path().exists():
            self._reconnect()
            return False                                  # 停止轮询
        return self._start_polls < 20                     # 最多 ~10s

    def _reconnect(self):
        if self._client:
            self._client.stop()
        self._connect_client()                            # 重新 discover(拿到新 token)再连

    def _stop_core(self):
        # 首选 WS shutdown(与谁拉起无关);WS 不可用→校验可信 pid 后 SIGTERM 兜底(spec §3.7)
        if self._client and self._client.is_connected():
            self._client.send({"action": "shutdown"})
            return
        rt = read_runtime(self._runtime_path())
        if rt and rt.get("pid") and pid_is_core(rt["pid"]):
            try:
                os.kill(rt["pid"], signal.SIGTERM)
            except OSError:
                pass

    def _set_provider(self, pid, enabled):
        if self._client:
            self._client.send({"action": "set_provider", "provider": pid, "enabled": enabled})

    def _set_interval(self, topic, interval):
        if self._client:
            self._client.send({"action": "set_interval", "topic": topic, "interval": interval})

    def _shutdown_client(self):
        if self._client:
            self._client.stop()


def main(argv=None) -> int:
    app = ManagerApp()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行确认通过(有图形会话)**

Run: `.venv/bin/python -m pytest tests/test_manager_smoke.py -v`
Expected: PASS（2 passed;若当前会话无 `DISPLAY` 则 SKIP——在本机 Deepin 图形终端里跑应 PASS）

- [ ] **Step 5: 端到端手动验证(对照 DoD)**

```bash
# 终端 A:起底座
.venv/bin/python -m core
# 终端 B:起面板
.venv/bin/python -m manager
```
逐项对照 DoD 确认:
- 数据源页 CPU/内存/时间实时跳动;概览页客户端数/运行时长随心跳刷新。
- 改 `system.cpu` 间隔 → 推送频率变化;**停掉底座再 `cat ~/.config/managewidgets/config.toml` 应见 `intervals`/`providers_enabled` 已持久化**。
- 关 system 开关其 topic 停更而 time 不受影响。
- 关面板重开能自动重连;`core.json` 权限为 `600`。
- **不开终端 A**,只在面板点"启动底座" → 概览页应在 ~1s 内变"已连接"、数据开始跳(一键启动闭环)。
- 点"停止底座"(无论底座是面板还是手动起的)→ 底座退出、`core.json` 消失;面板转"未连接"。

- [ ] **Step 6: 提交**

```bash
git add manager/app.py manager/pages tests/test_manager_smoke.py
git commit -m "feat(manager): GTK3 三页面板 + 接线 + 冒烟测试"
```

---

### Task 11: 全量回归 + autostart + README

**Files:**
- Create: `core/autostart.py`, `README.md`
- Modify: `manager/pages/overview.py`(加自启开关), `manager/app.py`(接自启)
- Test: `tests/test_autostart.py`

**Interfaces:**
- Produces:
  - `core/autostart.py`:`autostart_path() -> Path`(`~/.config/autostart/managewidgets-core.desktop`);`enable_autostart(exec_cmd: str) -> None`(写 `.desktop`);`disable_autostart() -> None`(删除);`is_autostart_enabled() -> bool`
  - overview 页加"开机自启"`Gtk.Switch`,回调进出 autostart

- [ ] **Step 1: 写失败测试 `tests/test_autostart.py`**

```python
from core import autostart


def test_enable_disable_autostart(tmp_path, monkeypatch):
    target = tmp_path / "autostart" / "managewidgets-core.desktop"
    monkeypatch.setattr(autostart, "autostart_path", lambda: target)
    assert autostart.is_autostart_enabled() is False
    autostart.enable_autostart("/usr/bin/managewidgets-core")
    assert target.exists()
    assert "managewidgets-core" in target.read_text()
    assert autostart.is_autostart_enabled() is True
    autostart.disable_autostart()
    assert autostart.is_autostart_enabled() is False
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_autostart.py -v`
Expected: FAIL（`No module named 'core.autostart'`）

- [ ] **Step 3: 写 `core/autostart.py`**

```python
from pathlib import Path

_DESKTOP = """[Desktop Entry]
Type=Application
Name=ManageWidgets Core
Exec={exec_cmd}
X-GNOME-Autostart-enabled=true
"""


def autostart_path() -> Path:
    return Path.home() / ".config" / "autostart" / "managewidgets-core.desktop"


def enable_autostart(exec_cmd: str) -> None:
    p = autostart_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_DESKTOP.format(exec_cmd=exec_cmd))


def disable_autostart() -> None:
    p = autostart_path()
    if p.exists():
        p.unlink()


def is_autostart_enabled() -> bool:
    return autostart_path().exists()
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_autostart.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: 接入面板自启开关**

在 `manager/pages/overview.py` 的 `__init__` 参数加 `on_autostart`,并在按钮区后追加:
```python
        self._autostart = Gtk.Switch()
        from core.autostart import is_autostart_enabled
        self._autostart.set_active(is_autostart_enabled())
        self._autostart.connect("notify::active", lambda s, _p: on_autostart(s.get_active()))
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.pack_start(Gtk.Label(label="开机自启", xalign=0), False, False, 0)
        row.pack_start(self._autostart, False, False, 0)
        self.pack_start(row, False, False, 0)
```
在 `manager/app.py` 构造 `OverviewPage` 处加 `on_autostart=self._toggle_autostart`,并加方法:
```python
    def _toggle_autostart(self, enabled):
        from core.autostart import disable_autostart, enable_autostart
        if enabled:
            enable_autostart(f"{sys.executable} -m core")
        else:
            disable_autostart()
```

- [ ] **Step 6: 写 `README.md`**(安装/运行/测试说明)

```markdown
# managewidgets

桌面小组件管理器(第一版:数据底座 + 管理面板)。X11 优先,GTK3。

## 系统依赖(PyGObject 无法用 pip 装,需系统包)
    # Debian/Deepin 系:
    sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1

## 安装(其余依赖装进 venv)
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install psutil websockets tomli-w pytest

## 运行
    .venv/bin/python -m core       # 底座
    .venv/bin/python -m manager    # 面板

## 测试
    .venv/bin/python -m pytest -v
```

- [ ] **Step 7: 全量回归**

Run: `.venv/bin/python -m pytest -v`
Expected: PASS（除无显示时 `test_manager_smoke` SKIP 外全过)

- [ ] **Step 8: 提交**

```bash
git add core/autostart.py manager/pages/overview.py manager/app.py tests/test_autostart.py README.md
git commit -m "feat: autostart 开关 + README + 全量回归"
```

---

## 自检(写完计划后对照 spec)

- **覆盖**:provider 框架/system/time(T1-2)、配置+损坏回退(T3)、runtime+token+flock+cmdline 识别三入口(T4)、协议+鉴权+校验+**配置持久化 on_change**(T5-6)、传输+调度+立即重采+**端口回退集成进 serve**+**心跳**(T7)、入口+实例锁+优雅停+**配置写回**+**config_reset notice**(T8)、发现+WS 客户端+重连+回包关联+**is_connected**(T9)、GTK3 三页+按 provider 分组+notices+**一键启动重连/SIGTERM 兜底停止**(T10)、autostart(T11)。spec §3-§9 各节均有对应 task。
- **DoD 对齐**:§9 的 11 条验收分散在 T7(数据实时/改间隔/停 provider)、T8(runtime/token/0600/二实例/SIGTERM/**config_reset notice**/**改动持久化**)、T9-T10(自动重连/**一键启动闭环**/**WS+SIGTERM 停止**)、手动 E2E(T10 Step5,逐项)。**配置持久化、config_reset notice、启动/停止闭环**均有自动化或显式手动验证,不留到实现时临场补。
- **类型一致**:`Hub.handle` 返回 `Reply`(含 `status_request_id`);`Conn` 字段 `authed/subscriptions`;`providers` 数组由 `Hub.providers_snapshot()` 产出,`core` 实时段(`port/clients/uptime/version/notices`)由 `CoreServer._full_status()` 组装,二者拼成完整 `status` 后被 datasources/overview 消费,字段名(`core.port`、`core.notices`、`providers[].topics[].last_value`)一致。`list_providers` 与心跳/`broadcast_status` 走同一 `_full_status`。
