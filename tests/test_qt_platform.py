"""QT_QPA_PLATFORM 清洗:去掉 Deepin 注入的 dxcb(PySide6 不带该插件,会告警)。"""
from manager.app import _strip_dxcb


def test_dxcb_xcb_falls_back_to_xcb():
    assert _strip_dxcb("dxcb;xcb") == "xcb"


def test_dxcb_only_falls_back_to_xcb():
    assert _strip_dxcb("dxcb") == "xcb"


def test_dxcb_keeps_other_fallbacks():
    assert _strip_dxcb("dxcb;wayland") == "wayland"


def test_non_dxcb_unchanged():
    assert _strip_dxcb("xcb") == "xcb"
    assert _strip_dxcb("wayland;xcb") == "wayland;xcb"


def test_empty_unchanged():
    assert _strip_dxcb("") == ""
