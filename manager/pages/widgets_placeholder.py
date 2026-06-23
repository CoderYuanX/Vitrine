import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class WidgetsPlaceholderPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_border_width(24)
        title = Gtk.Label(label="小组件渲染功能开发中")
        title.get_style_context().add_class("dim-label")
        body = Gtk.Label(label="后续将支持:贴桌面、Web 小组件(HTML/CSS/JS)、订阅底座数据。")
        body.set_line_wrap(True)
        self.pack_start(title, False, False, 0)
        self.pack_start(body, False, False, 0)
