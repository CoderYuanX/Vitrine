"""
Offscreen screenshot tool for Manager.qml and other QML files.

Usage:
    python tools/shoot.py [qml_path] [output_png_path]

Defaults:
    qml_path:       ui/Manager.qml
    output_png_path: docs/design-specs/shots/task7-shell.png
"""
import sys
from pathlib import Path

# Allow running from project root or tools/ directory
_here = Path(__file__).resolve().parent
_root = _here.parent
sys.path.insert(0, str(_root / "src"))
sys.path.insert(0, str(_here))

from PySide6.QtWidgets import QApplication  # QApplication (not QGuiApplication) so QtQuick.Controls-backed types also work
from PySide6 import QtQuick  # MUST import before loading so root is typed QQuickWindow
from PySide6.QtGui import QSurfaceFormat, QFont
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QTimer, QUrl

from preview_manager import MockCatalog

# Parse arguments
qml_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _root / "ui" / "Manager.qml"
out_path  = Path(sys.argv[2]) if len(sys.argv) > 2 else _root / "docs" / "design-specs" / "shots" / "task7-shell.png"

# Make output dir
out_path.parent.mkdir(parents=True, exist_ok=True)

_fmt = QSurfaceFormat.defaultFormat()
_fmt.setAlphaBufferSize(8)
QSurfaceFormat.setDefaultFormat(_fmt)
app = QApplication(sys.argv[:1])
_font = QFont()
_font.setFamilies(["PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC"])
app.setFont(_font)
eng = QQmlApplicationEngine()
mock = MockCatalog()
eng.rootContext().setContextProperty("catalog", mock)

warnings = []
eng.warnings.connect(lambda ws: warnings.extend(str(w.toString()) for w in ws))
eng.load(QUrl.fromLocalFile(str(qml_path.resolve())))

roots = eng.rootObjects()
assert roots, f"Failed to load QML: {qml_path}"
win = roots[0]

def grab():
    res = win.contentItem().grabToImage()
    def done():
        img = res.image()
        ok = (not img.isNull()) and img.save(str(out_path))
        print("SHOT", "OK" if ok else "FAIL", img.width(), "x", img.height())
        print("QML WARNINGS:", warnings if warnings else "none")
        app.quit()
    res.ready.connect(done)

QTimer.singleShot(900, grab)
QTimer.singleShot(8000, lambda: (print("TIMEOUT"), app.quit()))
sys.exit(app.exec())
