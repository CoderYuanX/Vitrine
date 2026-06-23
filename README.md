# managewidgets

桌面小组件管理器(第一版:数据底座 + 管理面板)。X11 优先,GTK3。

## 系统依赖(PyGObject 无法用 pip 装,需系统包)
    # Debian/Deepin 系:
    sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 gir1.2-ayatanaappindicator3-0.1

## 安装(其余依赖装进 venv)
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install psutil websockets tomli-w pytest

## 运行
    .venv/bin/python -m core       # 底座
    .venv/bin/python -m manager    # 面板

## 测试
    .venv/bin/python -m pytest -v

## 托盘与常驻(系统托盘)

面板是常驻系统托盘应用(Deepin dock):

- **关窗行为**:首次点窗口 × 会询问「最小化到托盘 / 退出」,可勾"记住我的选择"
  (偏好存 `~/.config/managewidgets/manager.toml`,与 core 的 `config.toml` 分开)。
- **托盘菜单**:显示/隐藏面板、启动/停止底座、开机自启、退出。**退出只退面板,
  core 底座继续运行**(要停底座用菜单"停止底座")。图标随连接状态变绿/灰。
- **开机自启**:打开后登录即在托盘,并自动拉起底座、数据开始跳。自启的 `.desktop`
  **历史原因沿用文件名 `managewidgets-core.desktop`,实际自启的是 manager 面板
  (`Exec=… -m manager`)**。
- **缺托盘库时**:若系统未装 `gir1.2-ayatanaappindicator3-0.1`,面板仍可运行,
  只是没有托盘图标(降级为普通窗口,关窗即退出)。

## 已知问题与修复记录

下列问题在代码评审与真机 GUI 验证阶段发现,均已修复并合并到 `main`:

- **底座入口绑定失败被吞掉(已修复)**:`start_in_thread()` 在 `serve()` 绑定失败时只在后台线程 re-raise,调用方仍空等 5s 后拿到 `port=None`。现把异常带回主线程——就绪即返回,失败抛 `OSError`,未就绪抛 `TimeoutError`(回归:`tests/test_core_integration.py::test_start_in_thread_raises_when_unbindable`)。
- **数据源页整页空白(已修复)**:动态新增的 provider 组 `frame` 未调用 `show_all()`,而窗口的 `show_all()` 早于数据到达,后加的子树默认不可见。现 `_ensure_group` 加入容器后调用 `frame.show_all()`(回归:`tests/test_manager_smoke.py::test_datasources_group_visible_after_update`)。
- **数据源页开关/间隔不随 status 同步(已修复)**:启用开关与间隔 `SpinButton` 只在创建组/行时设置一次,别的客户端改了 provider/interval 后本页仍显示旧值。现每帧 status 经 `_sync_switch`/`_sync_interval` 回写,并 `handler_block` 屏蔽信号以免回环触发 `set_provider`/`set_interval`(回归:`tests/test_manager_smoke.py::test_datasources_syncs_state_without_feedback_loop`)。
- **测试命名残留(已修复)**:`test_set_interval_valid_repolls` 已不再检查 repoll(该字段在最终评审时删除),改名为 `test_set_interval_valid_resets_timer`。

当前仍存在、但无害:

- 运行 GTK 时控制台可能打印 `g_value_set_boxed` 断言与 `AT-SPI` 总线告警——均来自系统 PyGObject / 无障碍库,与本程序无关,不影响功能,测试也照常全过。
