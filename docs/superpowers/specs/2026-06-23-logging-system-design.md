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

1. **`TimedRotatingFileHandler`**:`when="midnight"`、`backupCount=retention_days`(默认 7)、`encoding="utf-8"`、`delay=False`(setup 后随即写启动行,文件即建,便于立刻收紧权限)、`utc=False`(桌面应用用本地时间,排障对得上系统时钟)。每天切一份,超过保留份数的旧文件由 handler 自动删除。
2. **启动清理**:`setup_logging` 启动时只扫**本系统已知前缀**的文件 —— `core.log*` 与 `manager.log*`(常量列表,非 `*.log*`,避免误删目录内其它文件),删除 **mtime 早于 `now - retention_days` 天**者。兜住「进程久不写 / 已退出」导致 handler 不触发删除的漏网文件,以及两端互相遗留的旧文件。轮转产生的 `core.log.2026-06-16` 等后缀文件也被该前缀匹配清理;**实现与测试都不假设具体后缀格式**,只按前缀 + mtime 判定。**单个文件 `unlink` 失败(权限 / 占用 / 竞态)不得阻断启动**(回应评审 3-4):捕获异常后继续清理其余文件;**失败信息收集进 `cleanup_warnings` 列表延后落盘**(回应评审 5-1)—— 清理此时 handler 尚未挂好,不能即时 `logger.warning`,否则丢失。
3. **保留天数可配**:默认 7,环境变量 `MANAGEWIDGETS_LOG_RETENTION_DAYS` 覆盖(非整数 / ≤0 等非法值回退默认 7)。

> 说明:即便 handler 在某些进程生命周期下不切分,启动清理也保证目录内不会留下 > N 天的日志。

## 统一入口

新增 `core/logs.py`(`core` 是 `manager` 的共同依赖,放这里两端都能 import):

```python
def setup_logging(component, *, log_dir=None, level=None, retention_days=None) -> Path:
    """配置该 component 的包级 logger,返回主日志文件路径。

    - component: "core" / "manager",决定文件名 {component}.log 与挂载的包 logger
    - log_dir:   默认 default_state_dir()/"logs";测试注入 tmp
    - level:     文件级别;默认取 env MANAGEWIDGETS_LOG_LEVEL,缺省 INFO
    - retention_days: 默认取 env MANAGEWIDGETS_LOG_RETENTION_DAYS,缺省 7
    """
```

**挂到包 logger 而非根 logger**(回应评审 1):handler 挂在 `logging.getLogger(component)`(即 `"core"` / `"manager"`)上,而非根 logger。这样:
- `core.*` 的记录只进 `core.log`、`manager.*` 只进 `manager.log` —— **同进程内先后 `setup_logging("core")` 再 `setup_logging("manager")` 也天然互不串台**,无需靠 handler 标记区分组件。
- 每个组件 logger 上的幂等更简单:重入时先移除该 logger 上带标记 `_managewidgets=True` 的旧 handler 再挂。
- 取舍:第三方库(`websockets`/`asyncio`,日志名不在 `core.*`/`manager.*` 下)不会被捕获到文件。可接受 —— 连接/poll 等要紧事件本系统代码已自行记录;若日后需要,再单独把指定第三方 logger 纳入。
- **`getLogger(component).propagate = False`**(回应评审 2-1):不能依赖「根无 handler」—— pytest 的 `caplog`、用户 shell、外层包装器都可能给根挂 handler,届时 `propagate=True` 会让同一条记录冒泡到根被**重复输出 / 二次格式化**。关掉传播,组件日志完全由本系统 handler 掌控。(未 `setup_logging` 就独立调用 `core.config.load_config()` 的场景不受影响:那时没动过 `core` logger 的 propagate,仍走默认传播 / lastResort。)

行为:
- **校验 `component`**(回应评审 3-5):仅接受 `"core"` / `"manager"`,其余直接 `ValueError`,杜绝意外用任意值生成任意文件名日志(也与启动清理的固定前缀保持一致)。
- 在 `log_dir` 下建目录;**无论目录是否已存在,都 `chmod(0o700)`**(回应评审 2-2)—— `mkdir(exist_ok=True)` 不会收紧已存在的宽权限目录,必须显式 chmod。随后执行**启动清理**(删 > retention_days 的旧日志),把删除失败信息收进 `cleanup_warnings`(**暂不落盘**,handler 尚未挂好)。
- 解析级别:`level` 入参 > env `MANAGEWIDGETS_LOG_LEVEL` > 缺省 INFO。接受**大小写不敏感**的名称 `DEBUG/INFO/WARNING/ERROR/CRITICAL`,以及**仅限标准数值** `10/20/30/40/50`(及其字符串形式)(回应评审 4-3:不接受 `1`/`999` 等任意整数,否则 handler 行为令人困惑);其余一律视为非法,**回退 INFO**。该回退路径对 `level` 入参与 env 两条来源都生效(回应评审 4-2)。解析函数返回 `(numeric_level, warning_or_None)`;**该回退 WARNING 必须在 handler 挂好之后**用组件 logger 发出(回应评审 2-4),否则会丢失或只进 lastResort。
- 把组件 logger 级别设为解析出的数值级别,使记录能下发到 handler;各 handler 再按自身级别过滤。
- 给该 **组件 logger** 挂两个 handler:
  - `TimedRotatingFileHandler` → `{component}.log`,级别 = 解析级别。
  - `StreamHandler(sys.stderr)`,级别 = `max(numeric_level, logging.WARNING)` —— 终端只显示要紧的,不被 INFO 刷屏;若 env 把级别调到 ERROR,则 stderr 同步收紧到 ERROR。
- **文件权限 `0o600`**(回应评审 2):日志含 pid/port/路径/堆栈等本地诊断信息,与 `core.json` 的 0600 一致。做法:子类化 `TimedRotatingFileHandler` 并**重写 `_open()`**,内部仍调内置 `open(self.baseFilename, self.mode, encoding=self.encoding, opener=lambda path, flags: os.open(path, flags, 0o600))` —— `open` 的 `opener` 回调收 `(path, flags)`、用 `os.open` 以 0o600 创建并返回 fd(**不是**把整个 `_open` 换成 `os.open`,它需返回 stream 而非 fd)。如此**初始与轮转新建**的文件都是 0600。
- **幂等**:重入时先移除组件 logger 上带 `_managewidgets=True` 标记的旧 handler 再挂。保障测试与潜在多次调用安全。
- **handler 挂好后,先补发所有延后的 WARNING,再写启动行**(回应评审 5-1 / 4-1):
  - 先用组件 logger 发出 `cleanup_warnings` 里的每条清理失败 WARNING、以及级别回退 WARNING(若有)——它们都产生于 handler 安装之前,此刻才能落盘。
  - 再发启动行 `logger.info("logging initialized: component=… level=… retention=…d file=<path>")`(均为非敏感字段)。注意它是 **INFO,受当前级别约束**(回应评审 4-1):默认 INFO 时落盘,若级别被调到 WARNING+ 则不写——这是正常 logger 语义,**不**为它破例(用 `logger.log(level,…)` 在 ERROR 下写"logging initialized"会很怪)。因此「确定可读内容」不依赖它:测试 1 自己写一条 INFO 再读。
  - 回退 WARNING 文本须含**原始非法值、来源(env / argument)、最终级别 INFO**(回应评审 5-2),如 `invalid log level from env: 'bogus'; using INFO` —— 测试据此精确断言,而非模糊查 WARNING。
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

**敏感信息禁止落盘**(回应评审 6):**永不记录** token、完整 runtime payload、完整 WebSocket `hello` 握手消息。鉴权/连接相关只记录非敏感字段 —— `port`/`pid`/`version`、请求的 `action`/`id`、鉴权结果(成功/失败,不含 token 值)。新增埋点须自查这一条。

**日志不得成为恢复路径的新失败点**(回应评审次要项):`core/config.load_config` 等可能在 `setup_logging` 之前被独立调用(如单测直接调)。日志一律用模块级 `getLogger(__name__)` —— 未配置 handler 时 Python 的 lastResort 会把 WARNING+ 安全输出到 stderr,`logging` 调用本身不抛异常,故配置损坏的恢复分支加日志不会引入新失败。

> 「小组件报错」:真桌面浮窗组件尚未实现,当前最接近的「组件报错」是数据源 provider 的采集失败,已纳入(ERROR + 堆栈)。组件落地后沿用同一套 `getLogger(__name__)` 即可,无需改日志系统。

## 测试

新增 `tests/test_logs.py`(纯逻辑,不依赖 GTK,不碰真实 home —— 全部 `log_dir=tmp_path` 注入)。**测试隔离**(回应评审 3-2):用一个 fixture 在每个用例前后,对 `core` / `manager` logger **移除本系统 handler 并把 `propagate` 还原为 `True`、level 还原**,避免 `propagate=False` 等改动串扰后续用例(也含本套件外的用例):

1. `setup_logging`(默认级别)在指定 `log_dir` 建出 `{component}.log`,**测试自己**用组件 logger 写一条 INFO 后**读文件**确认含该行(不依赖启动行,因其受级别约束)。
2. 级别:`level="WARNING"`(或 env)时 INFO 不落、WARNING 落。
3. 幂等:连续调用两次,组件 logger 上本系统 handler 数不翻倍。
4. **同进程隔离**(回应评审 1-1):同一进程先 `setup_logging("core", log_dir=tmp)` 再 `setup_logging("manager", log_dir=tmp)`,分别用 `core.x` / `manager.x` logger 各写一条,断言**各自只进各自文件、不串台**。
5. **权限精确断言**(回应评审 2-2/2-3):预先 `mkdir(log_dir, 0o755)` 再 setup,断言目录 `stat().st_mode & 0o777 == 0o700`(证明对已存在目录也会收紧);断言 `{component}.log` 的 `st_mode & 0o777 == 0o600`(精确,不只是非 world-readable)。
6. **轮转后权限**(回应评审 2-6):setup 后从 `getLogger(component).handlers` 取出本系统 file handler,调用 `doRollover()` 并再写一条,断言新建的 `{component}.log` 仍是 `0o600` —— 守住自定义 `_open` 确实覆盖轮转路径。
7. **启动清理 + 不误删 + 清两端遗留**(回应评审 2-5):造 `core.log.old`(mtime 8 天前)、近期 `core.log`、过期 `manager.log.old`(mtime 8 天前)、以及非本系统文件 `other.log.old` / `notes.txt`。`setup_logging("core", retention_days=7)` 后:过期的 `core.log.old` **与** `manager.log.old` 都被删(证明两端遗留旧文件都清),近期文件保留,`other.log.old` / `notes.txt` **不动**(证明只认 `core.log*`/`manager.log*` 前缀)。
8. `retention_days` 经 env `MANAGEWIDGETS_LOG_RETENTION_DAYS` 可覆盖;非整数 / ≤0 回退默认 7。
9. **级别非法回退已落盘**(回应评审 2-4/5/5-2):`MANAGEWIDGETS_LOG_LEVEL="bogus"` → 实际级别为 INFO,且**读 `{component}.log`** 确认回退 WARNING 已写入,文本含原始值 `bogus`、来源 `env`、`INFO`(精确断言而非模糊查 WARNING,证明 warning 在 handler 挂好后才发)。
10. **回退覆盖入参路径与越界整数**(回应评审 4-2/4-3):`setup_logging(component, level="bogus")` 也回退 INFO(与 env 路径独立);`level="999"` / `level=999`(非标准数值)同样回退 INFO,而 `level="30"` / `level=30` 正常解析为 WARNING。
11. **非法 component 抛错且不建文件**(回应评审 6):`setup_logging("bad/name", log_dir=tmp_path)` 抛 `ValueError`,且 `log_dir` 下不产生任何日志文件(校验先于建目录/挂 handler)。

埋点侧(回应评审 7,证明落盘链路完整而非仅 logger 被调用):在 `tests/test_core_integration.py` 先 `setup_logging("core", log_dir=tmp_path)`,跑 `BoomProvider` 触发 poll 异常,**读 `core.log`** 断言含 provider 名 / topic / 异常文本(`boom`)。

## 影响面与兼容

- 新增文件:`core/logs.py`、`tests/test_logs.py`。
- 改动:`core/__main__`、`core/config`、`core/server`、`manager/app`、`manager/supervisor`、`manager/ws_client` 增加日志调用并替换 `print(stderr)`。
- 无新依赖、无配置文件格式变更、无网络协议变更。
- README:`项目结构` 增 `core/logs.py`;新增「日志」小节说明位置 / 级别 / 保留策略 / 环境变量,并给排障命令示例:`tail -f ~/.local/state/managewidgets/logs/manager.log`(及 `core.log`)。
