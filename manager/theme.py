"""主题装载:把 Soft Admin Blue 设计 token 注入 GTK,并随包安装字体。

设计契约见 docs/design-specs/2026-06-23-widget-manager-ui.md。
- CSS(颜色/间距/圆角)经 Gtk.CssProvider 全局加载。
- 字体随包(manager/assets/fonts/*.ttf):首次运行若用户字体目录缺失则复制并刷新 fontconfig 缓存。
- TOKENS:供 Cairo 自绘组件(开关/进度条/折线/脉冲点)取用与 CSS 同源的色值。
"""
import os
import shutil
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

_ASSETS = Path(__file__).resolve().parent / "assets"
_CSS = _ASSETS / "style.css"
_FONTS = _ASSETS / "fonts"

# 与 style.css 同源的色值(Cairo 自绘用)。改色时两处一起改。
TOKENS = {
    "bg_app": "#EEF3F9", "bg_window": "#F8FAFD", "bg_panel": "#FFFFFF",
    "bg_panel_subtle": "#F6F8FC", "bg_sidebar": "#F7F9FD",
    "border_default": "#E3E8F0", "border_subtle": "#EDF1F6", "border_strong": "#D6DEE9",
    "text_primary": "#111827", "text_secondary": "#4B5563", "text_muted": "#7B8794",
    "text_disabled": "#AAB4C2",
    "brand_primary": "#2563EB", "brand_primary_soft": "#EAF2FF", "brand_primary_border": "#BBD4FF",
    "success_primary": "#16A34A", "success_text": "#15803D",
    "danger_primary": "#EF4444", "danger_text": "#DC2626",
    "warning_primary": "#F59E0B", "warning_text": "#B45309",
    "info_primary": "#3B82F6",
    "neutral_100": "#F3F4F6", "neutral_200": "#E5E7EB", "neutral_300": "#D1D5DB", "neutral_400": "#9CA3AF",
    "purple": "#8B5CF6",   # 内存可视化(原型 memColor 正常态)
    "white": "#FFFFFF",
}


def rgba(name, alpha=1.0):
    """token 名 → (r,g,b,a) 浮点元组,供 cairo set_source_rgba。"""
    h = TOKENS.get(name, name).lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (r, g, b, alpha)


def metric_color(percent, kind="cpu"):
    """进度阈值色(原型 JS):CPU >80 danger/>60 warning/否则 brand;MEM >85/>70/否则紫。"""
    if kind == "mem":
        if percent > 85:
            return "danger_primary"
        if percent > 70:
            return "warning_primary"
        return "purple"
    if percent > 80:
        return "danger_primary"
    if percent > 60:
        return "warning_primary"
    return "brand_primary"


def ensure_fonts():
    """随包字体安装:用户字体目录缺 Inter/JetBrains 时复制并刷新缓存。失败仅回退系统字体,不致命。"""
    try:
        dest = Path.home() / ".local" / "share" / "fonts" / "managewidgets"
        changed = False
        for ttf in _FONTS.glob("*.ttf"):
            target = dest / ttf.name
            if not target.exists():
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ttf, target)
                changed = True
        if changed and shutil.which("fc-cache"):
            subprocess.run(["fc-cache", "-f", str(dest)], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:  # noqa: BLE001 — 字体装不上只影响观感,不阻断启动
        print(f"[manager] 字体安装跳过: {exc}")


def _tune_font_rendering():
    """让文字渲染贴近浏览器(原型在 Chrome 渲染):灰度抗锯齿 + slight hinting。

    同字体同字号下,GTK 默认 hintmedium 会把思源黑体笔画抓得偏重;slight + 灰度更接近
    Chrome 的清淡观感。仅作用于本进程的 Gtk.Settings,不改用户桌面全局设置。
    """
    try:
        st = Gtk.Settings.get_default()
        if st is None:
            return
        st.set_property("gtk-xft-antialias", 1)
        st.set_property("gtk-xft-hinting", 1)
        st.set_property("gtk-xft-hintstyle", "hintslight")
        st.set_property("gtk-xft-rgba", "none")           # 灰度,无亚像素彩边
    except Exception as exc:  # noqa: BLE001 — 渲染微调失败不致命
        print(f"[manager] 字体渲染微调跳过: {exc}")


def apply(screen=None):
    """加载全局 CSS。幂等:重复调用只刷新同一 provider。"""
    ensure_fonts()
    screen = screen or Gdk.Screen.get_default()
    if screen is None:                                    # 无显示(测试/CI)→ 跳过
        return None
    _tune_font_rendering()
    provider = Gtk.CssProvider()
    provider.load_from_path(str(_CSS))
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    return provider
