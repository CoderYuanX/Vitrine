import json
from pathlib import Path


GALLERY_ORDER = {
    "clock": 0,
    "weather": 1,
    "calendar": 2,
    "system": 3,
    "note": 4,
    "launcher": 5,
}


class WidgetRegistry:
    """扫描 widgets/ 目录,发现所有组件类型(每个目录一个 widget.json)。"""

    def __init__(self, widgets_dir):
        self.widgets_dir = Path(widgets_dir)

    def discover(self):
        """返回 [{'id','name','qml','dir','default_size'}]。

        排序规则:先按 GALLERY_ORDER 中的固定槽位排序;不在 GALLERY_ORDER
        中的 id(如未来/第三方组件)统一落到末尾(槽位 = len(GALLERY_ORDER)),
        其内部再按 id 字典序排列。
        """
        found = []
        if not self.widgets_dir.is_dir():
            return found
        for sub in sorted(self.widgets_dir.iterdir()):
            meta = sub / "widget.json"
            if not meta.is_file():
                continue
            try:
                data = json.loads(meta.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            wid = data.get("id")
            if not wid:
                continue
            qml = data.get("qml", sub.name + ".qml")
            found.append({
                "id": wid,
                "name": data.get("name", wid),
                "qml": str(sub / qml),
                "dir": str(sub),
                "default_size": data.get("defaultSize", [320, 210]),
                "category": data.get("category", wid),
                "implemented": bool(data.get("implemented", True)),
            })
        found.sort(key=lambda w: (GALLERY_ORDER.get(w["id"], len(GALLERY_ORDER)), w["id"]))
        return found
