from PySide6.QtCore import QObject, Slot


class LayoutBridge(QObject):
    """QML 与配置之间的桥:按组件 id 读/存几何(位置+缩放)。"""

    def __init__(self, config):
        super().__init__()
        self._c = config

    @Slot(str, result=str)
    def getState(self, widget_id):
        w = self._c.get_widget(widget_id)
        return f'{w["x"]},{w["y"]},{w["zoom"]}'

    @Slot(str, int, int, float)
    def saveState(self, widget_id, x, y, zoom):
        self._c.save_geometry(widget_id, x, y, zoom)
