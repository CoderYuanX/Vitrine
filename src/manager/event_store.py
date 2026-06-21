import json
import uuid
from datetime import date
from pathlib import Path


def _valid_date(s):
    try:
        date.fromisoformat(str(s))
        return True
    except ValueError:
        return False


def _norm_time(t):
    """规范化为 24h 'HH:MM';非法或空 → ''。"""
    t = str(t or "").strip()
    if not t:
        return ""
    parts = t.split(":")
    if len(parts) != 2:
        return ""
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return ""
    if 0 <= h <= 23 and 0 <= m <= 59:
        return f"{h:02d}:{m:02d}"
    return ""


# 分类色(与 widgets/Calendar/DemoData.js 的 CAT 保持一致)
CAT_COLORS = {
    "work": "#2f6bff",
    "personal": "#16a34a",
    "meeting": "#7c3aed",
    "important": "#d97706",
    "holiday": "#ec4899",
}
_DEFAULT_CAT = "work"


def _norm_cat(cat):
    return cat if cat in CAT_COLORS else _DEFAULT_CAT


class EventStore:
    """本地可编辑的日历事件库,持久化到 ~/.config/deepin-widgets/events.json。

    结构: {"events": [{"id","date":"YYYY-MM-DD","title","cat","time":"HH:MM"|""}]}
    对外的 month 参数沿用 QML/JS 习惯:0-11。
    """

    def __init__(self, path=None):
        self.path = Path(path) if path else (
            Path.home() / ".config" / "deepin-widgets" / "events.json")

    # ---- 持久化 ----
    def _load(self):
        if not self.path.exists():
            return {"events": []}
        try:
            d = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"events": []}
        if not isinstance(d, dict) or not isinstance(d.get("events"), list):
            return {"events": []}
        return d

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _all(self):
        out = []
        for e in self._load()["events"]:
            if not isinstance(e, dict) or "date" not in e:
                continue
            out.append({
                "id": str(e.get("id", "")),
                "date": str(e["date"]),
                "title": str(e.get("title", "")),
                "cat": _norm_cat(e.get("cat", _DEFAULT_CAT)),
                "time": str(e.get("time", "")),
            })
        return out

    @staticmethod
    def _sort_key(e):
        # 有时间的按时间升序在前,无时间的(空串)排到最后
        return (e["time"] == "", e["time"], e["title"])

    # ---- 写 ----
    def add(self, date_iso, title, cat=_DEFAULT_CAT, time=""):
        date_iso = str(date_iso)
        if not _valid_date(date_iso):
            raise ValueError(f"invalid date: {date_iso!r}")
        d = self._load()
        eid = uuid.uuid4().hex[:8]
        d["events"].append({
            "id": eid,
            "date": date_iso,
            "title": str(title),
            "cat": _norm_cat(cat),
            "time": _norm_time(time),
        })
        self._save(d)
        return eid

    def remove(self, eid):
        d = self._load()
        d["events"] = [e for e in d["events"] if str(e.get("id", "")) != str(eid)]
        self._save(d)

    # ---- 读 ----
    def for_month(self, year, month):
        prefix = f"{year:04d}-{month + 1:02d}-"
        return sorted(
            (e for e in self._all() if e["date"].startswith(prefix)),
            key=self._sort_key,
        )

    def for_day(self, year, month, day):
        target = f"{year:04d}-{month + 1:02d}-{day:02d}"
        return sorted(
            (e for e in self._all() if e["date"] == target),
            key=self._sort_key,
        )

    def dots(self, year, month):
        """返回 {日: 颜色}:该月每个有事件的日子映射到首个事件的分类色。"""
        out = {}
        for e in self.for_month(year, month):
            try:
                day = int(e["date"].split("-")[2])
            except (ValueError, IndexError):
                continue
            out.setdefault(day, CAT_COLORS[e["cat"]])
        return out

    def upcoming(self, from_date_iso, limit=5):
        """从 from_date_iso 的次日起(不含当天)按日期+时间升序的未来事件。"""
        items = [e for e in self._all() if e["date"] > str(from_date_iso)]
        items.sort(key=lambda e: (e["date"], e["time"] == "", e["time"]))
        return items[:limit]
