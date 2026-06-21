import json
from pathlib import Path


class ConfigStore:
    """读写 ~/.config/deepin-widgets/config.json。

    结构: {"widgets": {"<id>": {"enabled":bool,"x":int,"y":int,"zoom":float}}}
    """

    def __init__(self, path=None):
        self.path = Path(path) if path else (
            Path.home() / ".config" / "deepin-widgets" / "config.json")

    def _load(self):
        if not self.path.exists():
            return {"widgets": {}}
        try:
            d = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"widgets": {}}
        if not isinstance(d, dict) or not isinstance(d.get("widgets"), dict):
            return {"widgets": {}}
        return d

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def get_widget(self, wid, default_pos=(80, 80), default_zoom=1.0,
                   default_enabled=False):
        w = self._load()["widgets"].get(wid, {})
        return {
            "enabled": bool(w.get("enabled", default_enabled)),
            "x": int(w.get("x", default_pos[0])),
            "y": int(w.get("y", default_pos[1])),
            "zoom": float(w.get("zoom", default_zoom)),
        }

    def is_enabled(self, wid, default=False):
        return self.get_widget(wid, default_enabled=default)["enabled"]

    def set_enabled(self, wid, enabled):
        d = self._load()
        d["widgets"].setdefault(wid, {})["enabled"] = bool(enabled)
        self._save(d)

    def save_geometry(self, wid, x, y, zoom):
        d = self._load()
        w = d["widgets"].setdefault(wid, {})
        w["x"], w["y"], w["zoom"] = int(x), int(y), round(float(zoom), 3)
        self._save(d)

    def get_weather(self):
        w = self._load().get("weather", {})
        if not isinstance(w, dict):
            w = {}
        return {
            "autoLocate": bool(w.get("autoLocate", True)),
            "city": str(w.get("city", "")),
        }

    def set_weather(self, auto_locate=None, city=None):
        d = self._load()
        w = d.setdefault("weather", {})
        if not isinstance(w, dict):
            w = d["weather"] = {}
        if auto_locate is not None:
            w["autoLocate"] = bool(auto_locate)
        if city is not None:
            w["city"] = str(city)
        self._save(d)
