# 打包为 .deb

自包含打包:把应用 + 一个含 `PySide6-Essentials` 的 Python 虚拟环境装进 `/opt/vitrine`,
装上即用,不依赖系统是否有 PySide6。

## 构建

```bash
packaging/build-deb.sh            # 默认版本 0.1.0
packaging/build-deb.sh 0.2.0      # 指定版本
```

产物:`dist/vitrine_<版本>_<架构>.deb`(`dist/` 已被 git 忽略)。

构建机需要:`python3`(venv 基座)、`pip`、`dpkg-deb`。首次会联网下载
`PySide6-Essentials`(~150–200MB)。

## 安装 / 卸载

```bash
sudo apt install ./dist/vitrine_0.1.0_amd64.deb     # 自动装系统依赖
# 或
sudo dpkg -i ./dist/vitrine_0.1.0_amd64.deb && sudo apt -f install

sudo apt remove vitrine
```

装好后:开始菜单/启动器搜索「Vitrine 桌面小组件」,或终端运行 `vitrine`。
应用常驻系统托盘,右键托盘图标 →「打开管理面板」。

## 包内容

| 路径 | 说明 |
| --- | --- |
| `/opt/vitrine/` | 应用源码(`main.py` / `src` / `ui` / `widgets`)+ `venv/` |
| `/usr/bin/vitrine` | 启动器(调用 `/opt/vitrine/venv/bin/python`) |
| `/usr/share/applications/vitrine.desktop` | 桌面入口 |
| `/usr/share/icons/hicolor/scalable/apps/vitrine.svg` | 应用图标 |

用户数据(组件开关 / 几何 / 日历事件)写在 `~/.config/deepin-widgets/`,卸载不影响。

## 说明 / 限制

- venv 在运行时按解释器实际位置推断 `prefix`,故安装到固定路径 `/opt/vitrine` 即可正确加载。
- venv 的 `bin/python` 指向系统 `python3`,因此 `Depends: python3 (>= 3.12)`;
  目标机 Python 次版本需与构建机一致(Deepin 25 = 3.12)。跨发行版分发建议改用
  PyInstaller 冻结或 dh-virtualenv。
- 仅打包 `PySide6-Essentials`(覆盖本应用用到的 Quick/Controls/Effects/Layouts/Widgets);
  若后续用到 WebEngine/Charts 等,需改装完整 `PySide6`。
