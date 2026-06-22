import json
import uuid
from datetime import date, timedelta
from pathlib import Path

from .event_store import CAT_COLORS, _DEFAULT_CAT, _norm_cat, _valid_date  # noqa: F401

# 周几简称(Mon=0),供"本周X"标签
_WEEK_SHORT = ["一", "二", "三", "四", "五", "六", "日"]


def _week_bounds(today_iso):
    """返回 (week_start_iso, week_end_iso),周一~周日(含今天所在周)。"""
    d = date.fromisoformat(str(today_iso))
    start = d - timedelta(days=d.weekday())
    end = d + timedelta(days=6 - d.weekday())
    return start.isoformat(), end.isoformat()


class TaskStore:
    """本地可编辑任务库,持久化到 ~/.config/deepin-widgets/tasks.json。

    结构: {"tasks": [{"id","text","cat","due":"YYYY-MM-DD","done":bool}]}
    """

    def __init__(self, path=None):
        self.path = Path(path) if path else (
            Path.home() / ".config" / "deepin-widgets" / "tasks.json")

    # ---- 持久化 ----
    def _load(self):
        if not self.path.exists():
            return {"tasks": []}
        try:
            d = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"tasks": []}
        if not isinstance(d, dict) or not isinstance(d.get("tasks"), list):
            return {"tasks": []}
        return d

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _all(self):
        out = []
        for t in self._load()["tasks"]:
            if not isinstance(t, dict) or "due" not in t:
                continue
            out.append({
                "id": str(t.get("id", "")),
                "text": str(t.get("text", "")),
                "cat": _norm_cat(t.get("cat", _DEFAULT_CAT)),
                "due": str(t["due"]),
                "done": bool(t.get("done", False)),
            })
        return out

    # ---- 写 ----
    def add(self, text, cat=_DEFAULT_CAT, due=""):
        due = str(due)
        if not _valid_date(due):
            raise ValueError(f"invalid due: {due!r}")
        d = self._load()
        tid = uuid.uuid4().hex[:8]
        d["tasks"].append({
            "id": tid,
            "text": str(text),
            "cat": _norm_cat(cat),
            "due": due,
            "done": False,
        })
        self._save(d)
        return tid

    def toggle(self, tid):
        d = self._load()
        for t in d["tasks"]:
            if str(t.get("id", "")) == str(tid):
                t["done"] = not bool(t.get("done", False))
                break
        self._save(d)

    def remove(self, tid):
        d = self._load()
        d["tasks"] = [t for t in d["tasks"] if str(t.get("id", "")) != str(tid)]
        self._save(d)

    # ---- 读 ----
    def today(self, today_iso):
        items = [t for t in self._all() if t["due"] == str(today_iso)]
        items.sort(key=lambda t: (t["done"], t["text"]))
        return items

    def week(self, today_iso):
        _, end = _week_bounds(today_iso)
        items = [t for t in self._all() if str(today_iso) < t["due"] <= end]
        items.sort(key=lambda t: (t["due"], t["done"]))
        for t in items:
            wd = date.fromisoformat(t["due"]).weekday()
            t["label"] = "本周" + _WEEK_SHORT[wd]
        return items

    def done_in_week(self, today_iso):
        start, end = _week_bounds(today_iso)
        return sum(1 for t in self._all() if start <= t["due"] <= end and t["done"])

    def active_in_week(self, today_iso):
        start, end = _week_bounds(today_iso)
        return sum(1 for t in self._all() if start <= t["due"] <= end and not t["done"])
