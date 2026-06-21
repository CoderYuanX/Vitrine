import json
from pathlib import Path


class WidgetRegistry:
    """扫描 widgets/ 目录,发现所有组件类型(每个目录一个 widget.json)。"""

    def __init__(self, widgets_dir):
        self.widgets_dir = Path(widgets_dir)

    def discover(self):
        """返回 [{'id','name','qml','dir','default_size'}],按 id 排序。"""
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
            })
        found.sort(key=lambda w: w["id"])
        return found
