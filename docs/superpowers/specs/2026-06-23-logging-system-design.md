# 落盘日志系统 + 7 天自动清理 — 设计

- 日期:2026-06-23
- 状态:已确认,待实现
- 相关:[CoreSupervisor 抽取](./2026-06-23-tray-resident-manager-design.md) 之后;日志是后续「桌面浮窗组件」的排障地基

## 目标

给 `deskwidgets` 加一套**落盘日志系统**,把当前散落、瞬时的错误输出(`print(stderr)`、被吞掉的异常、一次性弹窗)统一收编成**可回看、可 grep、带堆栈**的日志文件,主要服务于**人/AI 排查报错**。日志按时间轮转并自动清理,不会无限增长。

非目标(本期不做):
- 面板内「日志」查看页(已确认只落盘;真组件落地后可另起一期接入 UI)。
- 第三方日志库 / 结构化(JSON)日志 / 远程上报。
- 真桌面浮窗组件本身(本期只铺日志地基)。

## 现状

错误目前只瞬时存在,无任何持久记录:

- **core**:provider poll 失败经 `hub.record(..., error=...)` 仅保留**每个 topic 的最新一条** `last_error`,随 `status` 广播;配置损坏经 `notices` 一次性带出。历史不留。
- **manager**:`_show_error` 弹一次性对话框;若干 `print(..., file=sys.stderr)`(托盘降级 + 全栈、启动底座失败、控制失败提示)。关掉即丢。

## 选型

使用 **Python 标准库 `logging`**,不引第三方依赖(与项目「能不加依赖就不加」的取向一致)。

每个模块取 `logger = logging.getLogger(__name__)`,日志名天然携带来源:`core.server`、`core.providers.system`、`manager.supervisor`、`manager.ws_client` 等 —— 排查时一眼知道哪报的。

## 落盘位置

复用现有状态目录约定(`core.state.default_state_dir()`,即 `~/.local/state/managewidgets/`):

```
~/.local/state/managewidgets/logs/
  ├─ core.log       # 底座进程
  └─ manager.log    # 面板进程
```

两进程**分文件**,避免并发抢写(与 `config.toml` / `manager.toml` 分文件同一思路)。

## 格式(AI 友好)

人读文本,字段固定、可 grep,异常自动附完整 traceback:

```
2026-06-23 17:30:01,234 [WARNING] core.providers.system: poll system.cpu 失败
Traceback (most recent call last):
  ...
RuntimeError: ...
```

`Formatter`:`"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`。错误用 `logger.exception(...)` 或 `logger.error(..., exc_info=True)` 带堆栈。

## 轮转与清理(三重保险,确保不无限增长)

1. **`TimedRotatingFileHandler`**:`when="midnight"`、`backupCount=retention_days`(默认 7)。每天切一份,超过保留份数的旧文件由 handler 自动删除。
2. **启动清理**:`setup_logging` 启动时扫一遍 logs 目录,删除 **mtime 早于 `now - retention_days` 天**的 `*.log*` 文件。兜住「进程久不写 / 已退出」导致 handler 不触发删除的漏网文件,以及两端互相遗留的旧文件。
3. **保留天数可配**:默认 7,环境变量 `MANAGEWIDGETS_LOG_RETENTION_DAYS` 覆盖(非法值回退默认)。

> 说明:即便 handler 在某些进程生命周期下不切分,启动清理也保证目录内不会留下 > N 天的日志。

## 统一入口

新增 `core/logs.py`(`core` 是 `manager` 的共同依赖,放这里两端都能 import):

```python
def setup_logging(component, *, log_dir=None, level=None, retention_days=None) -> Path:
    """配置根 logger,返回主日志文件路径。

    - component: "core" / "manager",决定文件名 {component}.log
    - log_dir:   默认 default_state_dir()/"logs";测试注入 tmp
    - level:     文件级别;默认取 env MANAGEWIDGETS_LOG_LEVEL,缺省 INFO
    - retention_days: 默认取 env MANAGEWIDGETS_LOG_RETENTION_DAYS,缺省 7
    """
```

行为:
- 在 `log_dir` 下建目录,先执行**启动清理**(删 > retention_days 的旧日志)。
- 根 logger 级别设为 `level`(默认 INFO),使记录能下发到 handler;各 handler 再按自身级别过滤。
- 给**根 logger** 挂两个 handler:
  - `TimedRotatingFileHandler` → `{component}.log`,级别 = `level`(默认 INFO)。
  - `StreamHandler(sys.stderr)`,级别 = `max(WARNING, level)` —— 终端只显示要紧的,不被 INFO 刷屏;若 env 把级别调到 ERROR,则 stderr 同步收紧到 ERROR。
- **幂等**:重复调用不重复挂 handler(给本模块挂的 handler 打标记属性 `_managewidgets=True`,再次调用时先移除带标记的旧 handler 再挂)。保障测试与潜在多次调用安全。
- 返回主日志文件 `Path`。

调用点:
- `core/__main__.py` 的 `main()` 开头:`setup_logging("core")`。
- `manager/app.py` 的 `main()` 开头:`setup_logging("manager")`。

## 埋点(把现有瞬时输出收编进日志)

| 模块 | 记录内容 | 级别 |
|---|---|---|
| `core/__main__` | 启动(port/pid/version)、单实例拒绝、关停 | INFO / WARNING |
| `core/config` | 配置损坏并重置(原 `notices` 同时落日志) | WARNING |
| `core/server` | 绑定端口成功 / 占用回退到随机端口、**provider poll 异常(带堆栈)**、客户端连接/断开 | INFO / WARNING / **ERROR** |
| `manager/ws_client` | 连接成功 / 断开 / 鉴权失败、重连退避 | INFO / WARNING |
| `manager/supervisor` | 拉起底座、Popen 失败(带堆栈)、就绪 / 超时放弃、**控制操作被服务端拒绝** | INFO / **ERROR** / WARNING |
| `manager/app` | 托盘不可用降级(替换原 `traceback.print_exc()`,带堆栈)、`_show_error` 同时落日志 | WARNING |

替换原则:现有 `print(..., file=sys.stderr)` 与 `traceback.print_exc()` 一律改为对应 logger 调用;被 `except` 吞掉但有价值的异常补 `logger.exception(...)`。**不改变控制流与既有行为**,仅增加日志旁路(如 provider poll 异常仍照旧记入 status 并广播)。

> 「小组件报错」:真桌面浮窗组件尚未实现,当前最接近的「组件报错」是数据源 provider 的采集失败,已纳入(ERROR + 堆栈)。组件落地后沿用同一套 `getLogger(__name__)` 即可,无需改日志系统。

## 测试

新增 `tests/test_logs.py`(纯逻辑,不依赖 GTK,不碰真实 home —— 全部 `log_dir=tmp_path` 注入):

1. `setup_logging` 在指定 `log_dir` 建出 `{component}.log`,写一条 INFO 后文件内含该行。
2. 级别:`level="WARNING"`(或 env)时 INFO 不落、WARNING 落。
3. 幂等:连续调用两次,根 logger 上本模块 handler 不翻倍。
4. **启动清理**:在 `log_dir` 造两个文件,一个 mtime 设为 8 天前、一个 1 天前;`setup_logging(retention_days=7)` 后旧的被删、新的保留。
5. `retention_days` 经 env `MANAGEWIDGETS_LOG_RETENTION_DAYS` 可覆盖;非法值回退默认 7。

埋点侧:在 `tests/test_core_integration.py` 用 `caplog`(或读 tmp 日志文件)断言 provider poll 抛错时有 `ERROR` 记录且含异常信息(复用现有 `BoomProvider`)。

## 影响面与兼容

- 新增文件:`core/logs.py`、`tests/test_logs.py`。
- 改动:`core/__main__`、`core/config`、`core/server`、`manager/app`、`manager/supervisor`、`manager/ws_client` 增加日志调用并替换 `print(stderr)`。
- 无新依赖、无配置文件格式变更、无网络协议变更。
- README:`项目结构` 增 `core/logs.py`;新增「日志」小节说明位置 / 级别 / 保留策略 / 环境变量。
