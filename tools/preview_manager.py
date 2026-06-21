import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtCore import QUrl, QObject, Signal, Property, Slot

ROOT = Path(__file__).resolve().parents[1]
FAKE = [
    {"id":"clock","name":"时钟","category":"clock","enabled":True,"implemented":True,
     "previewQml":str(ROOT/"widgets/Clock/Preview.qml")},
    {"id":"weather","name":"天气","category":"weather","enabled":False,"implemented":False,"previewQml":""},
    {"id":"calendar","name":"日历","category":"calendar","enabled":False,"implemented":False,"previewQml":""},
    {"id":"system","name":"系统状态","category":"system","enabled":False,"implemented":False,"previewQml":""},
    {"id":"note","name":"便签","category":"note","enabled":False,"implemented":False,"previewQml":""},
    {"id":"launcher","name":"快捷启动","category":"launcher","enabled":False,"implemented":False,"previewQml":""},
]
CATS = [{"key":k,"label":l} for k,l in
        [("all","全部"),("clock","时钟"),("weather","天气"),("calendar","日历"),("system","系统"),("note","便签")]]

class MockCatalog(QObject):
    changed = Signal()
    def __init__(self):
        super().__init__()
        self._a="all"
        self._widgets = [dict(w) for w in FAKE]
    @Slot(str)
    def setCategory(self,k): self._a=k; self.changed.emit()
    @Slot(str,bool)
    def toggle(self,i,o):
        for w in self._widgets:
            if w["id"] == i:
                w["enabled"] = o
                break
        self.changed.emit()
    @Slot()
    def showAll(self):
        for w in self._widgets:
            if w["implemented"]:
                w["enabled"] = True
        self.changed.emit()
    @Slot()
    def hideAll(self):
        for w in self._widgets:
            w["enabled"] = False
        self.changed.emit()
    @Slot()
    def quitApp(self): pass
    @Slot(bool)
    def setAutostart(self,o): pass
    def _vis(self):
        return [w for w in self._widgets if self._a=="all" or w["category"]==self._a]
    activeCategory = Property(str, lambda s: s._a, notify=changed)
    categories = Property("QVariantList", lambda s: CATS, constant=True)
    visibleWidgets = Property("QVariantList", lambda s: s._vis(), notify=changed)
    autostartEnabled = Property(bool, lambda s: False, notify=changed)

if __name__ == "__main__":
    fmt = QSurfaceFormat.defaultFormat(); fmt.setAlphaBufferSize(8); QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication(sys.argv)
    from PySide6.QtGui import QFont
    _font = QFont(); _font.setFamilies(["PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC"]); app.setFont(_font)
    from PySide6.QtQml import QQmlApplicationEngine
    eng = QQmlApplicationEngine()
    catalog = MockCatalog()
    eng.rootContext().setContextProperty("catalog", catalog)
    eng.load(QUrl.fromLocalFile(str(ROOT/"ui"/"Manager.qml")))
    sys.exit(app.exec())
