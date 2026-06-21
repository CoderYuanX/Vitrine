from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, Qt


def _default_icon():
    icon = QIcon.fromTheme("preferences-desktop-display")
    if not icon.isNull():
        return icon
    pm = QPixmap(64, 64)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#FF7A6B"))
    p.drawRoundedRect(10, 10, 44, 44, 12, 12)
    p.end()
    return QIcon(pm)


def build_tray(host):
    tray = QSystemTrayIcon(_default_icon(), host.app)
    tray.setToolTip("桌面小组件")
    menu = QMenu()
    host._toggle_actions = {}
    for w in host.widgets:
        act = QAction(w["name"], menu)
        act.setCheckable(True)
        act.setEnabled(w.get("implemented", True))
        act.setChecked(host.runtime.is_shown(w["id"]))
        act.toggled.connect((lambda wid: (lambda checked: host.runtime.set_enabled(wid, checked)))(w["id"]))
        menu.addAction(act)
        host._toggle_actions[w["id"]] = act
    if not host.widgets:
        empty = QAction("（未发现组件）", menu)
        empty.setEnabled(False)
        menu.addAction(empty)
    menu.addSeparator()
    panel = QAction("打开管理面板", menu)
    panel.triggered.connect(host.open_manager)
    menu.addAction(panel)
    quit_act = QAction("退出", menu)
    quit_act.triggered.connect(host.app.quit)
    menu.addAction(quit_act)
    tray.setContextMenu(menu)
    tray.show()
    host._tray_menu = menu
    return tray
