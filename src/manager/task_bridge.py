from PySide6.QtCore import QObject, Signal, Slot

from .event_store import CAT_COLORS
from .task_store import TaskStore


class TaskBridge(QObject):
    """QML 与 TaskStore 之间的桥(注入为 context property `tasks`)。变更后发 changed。"""

    changed = Signal()

    def __init__(self, store=None):
        super().__init__()
        self._s = store or TaskStore()

    def _deco(self, t):
        t = dict(t)
        t["color"] = CAT_COLORS.get(t["cat"], CAT_COLORS["work"])
        return t

    @Slot(str, result="QVariantList")
    def today(self, today_iso):
        return [self._deco(t) for t in self._s.today(today_iso)]

    @Slot(str, result="QVariantList")
    def week(self, today_iso):
        return [self._deco(t) for t in self._s.week(today_iso)]

    @Slot(str)
    def toggle(self, tid):
        self._s.toggle(tid)
        self.changed.emit()

    @Slot(str, str, str)
    def add(self, text, cat, due):
        text = (text or "").strip()
        if not text:
            return
        try:
            self._s.add(text, cat=cat or "work", due=due)
        except ValueError:
            return
        self.changed.emit()

    @Slot(str)
    def remove(self, tid):
        self._s.remove(tid)
        self.changed.emit()

    @Slot(str, result=int)
    def doneThisWeek(self, today_iso):
        return self._s.done_in_week(today_iso)

    @Slot(str, result=int)
    def activeThisWeek(self, today_iso):
        return self._s.active_in_week(today_iso)

    @Slot(str, result=int)
    def totalThisWeek(self, today_iso):
        return self._s.done_in_week(today_iso) + self._s.active_in_week(today_iso)

    @Slot(str, result=str)
    def catColor(self, cat):
        return CAT_COLORS.get(cat, CAT_COLORS["work"])
