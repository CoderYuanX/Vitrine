from PySide6.QtCore import QObject, Signal, Slot

from .event_store import EventStore, CAT_COLORS


class EventBridge(QObject):
    """QML 与 EventStore 之间的桥:日历组件读/写本地事件。

    month 参数沿用 QML/JS 的 0-11。变更后发 changed,QML 据此刷新。
    """

    changed = Signal()

    def __init__(self, store=None):
        super().__init__()
        self._s = store or EventStore()

    @Slot(int, int, int, result="QVariantList")
    def dayEvents(self, year, month, day):
        return self._s.for_day(year, month, day)

    @Slot(int, int, int, result=str)
    def dotFor(self, year, month, day):
        return self._s.dots(year, month).get(day, "")

    @Slot(str, int, result="QVariantList")
    def upcoming(self, from_iso, limit):
        return self._s.upcoming(from_iso, limit)

    @Slot(str, result=str)
    def catColor(self, cat):
        return CAT_COLORS.get(cat, CAT_COLORS["work"])

    @Slot(str, str, str, str)
    def add(self, date_iso, title, cat, time):
        title = (title or "").strip()
        if not title:
            return
        try:
            self._s.add(date_iso, title, cat=cat or "work", time=time or "")
        except ValueError:
            return  # 非法日期不写入(UI 已收敛 selectedDay,这里是兜底)
        self.changed.emit()

    @Slot(str)
    def remove(self, eid):
        self._s.remove(eid)
        self.changed.emit()
