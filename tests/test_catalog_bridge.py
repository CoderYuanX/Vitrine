from manager.catalog_bridge import CatalogBridge


class FakeRuntime:
    def __init__(self, shown=()):
        self._shown = set(shown)
        self.calls = []
    def is_shown(self, wid):
        return wid in self._shown
    def set_enabled(self, wid, on):
        self.calls.append((wid, on))
        if on: self._shown.add(wid)
        else: self._shown.discard(wid)


WIDGETS = [
    {"id": "clock", "name": "时钟", "category": "clock", "implemented": True, "qml": "/x/Clock.qml", "dir": "/x"},
    {"id": "weather", "name": "天气", "category": "weather", "implemented": False, "qml": "", "dir": "/y"},
    {"id": "launcher", "name": "快捷启动", "category": "launcher", "implemented": False, "qml": "", "dir": "/z"},
]


def test_default_category_all_shows_everything():
    b = CatalogBridge(FakeRuntime(shown=["clock"]), WIDGETS)
    ids = [w["id"] for w in b._visible()]
    assert ids == ["clock", "weather", "launcher"]


def test_category_filters():
    b = CatalogBridge(FakeRuntime(), WIDGETS)
    b.setCategory("weather")
    assert [w["id"] for w in b._visible()] == ["weather"]


def test_launcher_only_in_all():
    b = CatalogBridge(FakeRuntime(), WIDGETS)
    b.setCategory("clock")
    assert "launcher" not in [w["id"] for w in b._visible()]


def test_enabled_reflects_runtime():
    b = CatalogBridge(FakeRuntime(shown=["clock"]), WIDGETS)
    clock = next(w for w in b._visible() if w["id"] == "clock")
    assert clock["enabled"] is True


def test_categories_list():
    b = CatalogBridge(FakeRuntime(), WIDGETS)
    keys = [c["key"] for c in b.categories]
    assert keys == ["all", "clock", "weather", "calendar", "system", "note"]


def test_toggle_calls_runtime_and_updates():
    rt = FakeRuntime()
    b = CatalogBridge(rt, WIDGETS)
    b.toggle("clock", True)
    assert rt.calls == [("clock", True)]
    clock = next(w for w in b._visible() if w["id"] == "clock")
    assert clock["enabled"] is True


def test_toggle_off():
    rt = FakeRuntime(shown=["clock"])
    b = CatalogBridge(rt, WIDGETS)
    b.toggle("clock", False)
    assert rt.calls == [("clock", False)]
