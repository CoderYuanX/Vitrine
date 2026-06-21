"""
Headless smoke test: tray <-> CatalogBridge state sync.
Run with:
  QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software timeout 25 python tools/smoke_tray_sync.py
"""
import sys
import os
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat
import signal

fmt = QSurfaceFormat.defaultFormat()
fmt.setAlphaBufferSize(8)
QSurfaceFormat.setDefaultFormat(fmt)

app = QApplication(sys.argv)
signal.signal(signal.SIGINT, signal.SIG_DFL)
app.setApplicationName("deepin-widgets-smoke")
app.setQuitOnLastWindowClosed(False)

from manager.registry import WidgetRegistry
from manager.config_store import ConfigStore
from manager.layout_bridge import LayoutBridge
from manager.runtime import WidgetRuntime
from manager.catalog_bridge import CatalogBridge
from manager.tray import build_tray

PROJECT_ROOT = Path(__file__).resolve().parents[1]

registry = WidgetRegistry(PROJECT_ROOT / "widgets")
config = ConfigStore()
layout_bridge = LayoutBridge(config)
widgets = registry.discover()
runtime = WidgetRuntime(app, widgets, config, layout_bridge)

catalog = CatalogBridge(runtime, widgets, quit_fn=app.quit)

# Minimal host object
class Host:
    pass

host = Host()
host.app = app
host.widgets = widgets
host.runtime = runtime
host.catalog = catalog
host.open_manager = lambda: None

runtime.bootstrap({"clock"})
build_tray(host)

# 1. After bootstrap, clock should be shown and tray action checked
assert runtime.is_shown("clock"), "Expected clock to be shown after bootstrap"
assert host._toggle_actions["clock"].isChecked(), "Expected tray action for clock to be checked"

# 2. catalog.toggle OFF -> runtime and tray both reflect False
catalog.toggle("clock", False)
assert not runtime.is_shown("clock"), "Expected clock hidden after catalog.toggle(False)"
assert not host._toggle_actions["clock"].isChecked(), "Expected tray action unchecked after catalog.toggle(False)"

# 3. catalog.toggle ON -> both reflect True
catalog.toggle("clock", True)
assert runtime.is_shown("clock"), "Expected clock shown after catalog.toggle(True)"
assert host._toggle_actions["clock"].isChecked(), "Expected tray action checked after catalog.toggle(True)"

# 4. hideAll -> tray action unchecked
catalog.hideAll()
assert not runtime.is_shown("clock"), "Expected clock hidden after hideAll"
assert not host._toggle_actions["clock"].isChecked(), "Expected tray action unchecked after hideAll"

print("SYNC OK")
sys.exit(0)
