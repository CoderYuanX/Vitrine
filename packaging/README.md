# 打包为 .deb

Deepin 源里没有 PySide6(只有 PySide2/Qt5),所以无法直接 `Depends: python3-pyside6`。
提供两种打包模式:

| 模式 | deb 大小 | 安装 | 说明 |
| --- | --- | --- | --- |
| **thin(瘦包,推荐)** | ~26KB | 安装时联网 `pip` 拉依赖到 `/opt/vitrine/venv`(~50–80MB) | deb 极小;安装需联网 |
| bundled(自包含) | ~52MB | 离线即装即用 | deb 内已带含 PySide6 的 venv;无网环境用这个 |

两者都把应用装进 `/opt/vitrine`,运行依赖都是 `PySide6-Essentials`(不含 WebEngine 等重模块)。

## 构建

```bash
packaging/build-deb.sh --thin           # 瘦包 → dist/vitrine_0.1.0-thin_amd64.deb
packaging/build-deb.sh                   # 自包含 → dist/vitrine_0.1.0_amd64.deb
packaging/build-deb.sh --thin 0.2.0      # 指定版本
```

产物在 `dist/`(已被 git 忽略)。构建机需要:`python3`、`pip`、`dpkg-deb`;
bundled 模式构建时会联网下载 `PySide6-Essentials`(~150–200MB)。

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

> thin 包里 `venv/` 由安装时的 postinst 调用 `setup-venv.sh` 生成;若安装时无网络,
> 包仍会装上,但运行 `vitrine` 会提示「请联网执行 `sudo /opt/vitrine/setup-venv.sh`」。
> 卸载(prerm)时会删除该 venv。

## 说明 / 限制

- venv 在运行时按解释器实际位置推断 `prefix`,故安装到固定路径 `/opt/vitrine` 即可正确加载。
- venv 的 `bin/python` 指向系统 `python3`,因此 `Depends: python3 (>= 3.12)`;
  目标机 Python 次版本需与构建机一致(Deepin 25 = 3.12)。跨发行版分发建议改用
  PyInstaller 冻结或 dh-virtualenv。
- 仅打包 `PySide6-Essentials`(覆盖本应用用到的 Quick/Controls/Effects/Layouts/Widgets);
  若后续用到 WebEngine/Charts 等,需改装完整 `PySide6`。
