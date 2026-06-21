import threading

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer

from .weather_provider import FALLBACK, WeatherProvider


class WeatherBridge(QObject):
    """QML 共享天气桥。所有小组件复用同一个实例。"""

    changed = Signal()
    settingsChanged = Signal()
    _loaded = Signal(dict)

    def __init__(self, config=None, provider=None, refresh_minutes=30):
        super().__init__()
        self._config = config
        self._provider = provider or WeatherProvider(settings=self._prefs)
        self._data = dict(FALLBACK)
        self._loading = False
        self._loaded.connect(self._apply)
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, refresh_minutes) * 60 * 1000)
        self._timer.timeout.connect(self.refresh)

    @Slot()
    def start(self):
        if not self._timer.isActive():
            self._timer.start()
        self.refresh()

    @Slot()
    def refresh(self):
        if self._loading:
            return
        self._loading = True

        def run():
            try:
                data = self._provider.current()
            finally:
                self._loading = False
            self._loaded.emit(data)

        threading.Thread(target=run, daemon=True).start()

    @Slot(dict)
    def _apply(self, data):
        self._data.update(data)
        self.changed.emit()

    # ---- 设置(自动定位 / 手填城市)----
    def _prefs(self):
        if self._config is None:
            return {"autoLocate": True, "city": ""}
        return self._config.get_weather()

    @Slot(bool)
    def setAutoLocate(self, on):
        if self._config is not None:
            self._config.set_weather(auto_locate=bool(on))
        self.settingsChanged.emit()
        self.refresh()

    @Slot(str)
    def setCity(self, city):
        if self._config is not None:
            self._config.set_weather(city=(city or "").strip())
        self.settingsChanged.emit()
        self.refresh()

    autoLocate = Property(bool, lambda self: self._prefs()["autoLocate"], notify=settingsChanged)
    manualCity = Property(str, lambda self: self._prefs()["city"], notify=settingsChanged)

    city = Property(str, lambda self: self._data["city"], notify=changed)
    cityFull = Property(str, lambda self: self._data["cityFull"], notify=changed)
    temp = Property(str, lambda self: self._data["temp"], notify=changed)
    desc = Property(str, lambda self: self._data["desc"], notify=changed)
    hi = Property(str, lambda self: self._data["hi"], notify=changed)
    lo = Property(str, lambda self: self._data["lo"], notify=changed)
    humidity = Property(str, lambda self: self._data["humidity"], notify=changed)
