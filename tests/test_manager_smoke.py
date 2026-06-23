import os
from pathlib import Path

import pytest

pytest.importorskip("gi")
gi = __import__("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk    # noqa: E402

# 无显示环境(CI)跳过:GTK 需要 X/Wayland
HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
pytestmark = pytest.mark.skipif(not HAS_DISPLAY, reason="需要图形显示")


def test_pages_construct():
    from manager.pages.overview import OverviewPage
    from manager.pages.datasources import DataSourcesPage
    from manager.pages.widgets import WidgetsPage

    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None, on_autostart=lambda enabled: None)
    ds = DataSourcesPage(on_set_provider=lambda p, e: None, on_set_interval=lambda t, i: None)
    wp = WidgetsPage()
    assert isinstance(ov, Gtk.Box) and isinstance(ds, Gtk.Box) and isinstance(wp, Gtk.Box)


def test_datasources_update_renders_topics():
    from manager.pages.datasources import DataSourcesPage
    ds = DataSourcesPage(on_set_provider=lambda p, e: None, on_set_interval=lambda t, i: None)
    snap = {
        "core": {"clients": 1, "uptime": 1.0, "version": "0.1.0", "notices": []},
        "providers": [{"id": "system", "enabled": True, "status": "running", "topics": [
            {"topic": "system.cpu", "interval": 1.0, "last_value": {"percent": 5.0},
             "last_ts": 1.0, "last_error": None}]}],
    }
    ds.update(snap)                                       # 不抛即通过
    assert ds.has_topic_row("system.cpu")


def test_datasources_group_visible_after_update():
    # 回归:动态新增的 provider 组 frame 必须 show_all,否则数据源页一片空白
    # (窗口 show_all 早于数据到达,后加的子树默认不可见)。
    from manager.pages.datasources import DataSourcesPage
    ds = DataSourcesPage(on_set_provider=lambda p, e: None, on_set_interval=lambda t, i: None)
    ds.update({"providers": [{"id": "system", "enabled": True, "status": "running",
        "topics": [{"topic": "system.cpu", "interval": 1.0, "last_value": {"percent": 5.0},
                    "last_ts": 1.0, "last_error": None}]}]})
    assert ds._switches["system"]["switch"].get_visible() is True   # 启用开关可见
    assert ds._groups["system"].get_visible() is True               # 组容器可见
    assert ds._rows["system.cpu"]["stepper"].get_visible() is True  # 间隔步进器可见


def test_datasources_syncs_state_without_feedback_loop():
    # 别的客户端改了 provider/间隔后,下一帧 status 必须把开关与 SpinButton 同步到新状态,
    # 且程序化同步不得回环触发 set_provider/set_interval。
    from manager.pages.datasources import DataSourcesPage
    prov_calls, iv_calls = [], []
    ds = DataSourcesPage(on_set_provider=lambda p, e: prov_calls.append((p, e)),
                         on_set_interval=lambda t, i: iv_calls.append((t, i)))

    def snap(enabled, interval):
        return {"core": {}, "providers": [{"id": "system", "enabled": enabled, "status": "running",
                "topics": [{"topic": "system.cpu", "interval": interval, "last_value": None,
                            "last_ts": None, "last_error": None}]}]}

    ds.update(snap(True, 1.0))
    sw = ds._switches["system"]["switch"]
    stepper = ds._rows["system.cpu"]["stepper"]
    assert sw.get_active() is True and stepper.get_value() == 1.0

    ds.update(snap(False, 5.0))                           # provider 关掉、间隔改成 5s
    assert sw.get_active() is False                       # 开关已同步
    assert stepper.get_value() == 5.0                     # 间隔已同步
    assert prov_calls == [] and iv_calls == []            # 程序化同步未回环触发控制命令


def test_datasources_apply_data_skips_redundant_redraw():
    # status 心跳每 ~2s 携 last_value 重放,值未变时不应反复 set_text。
    # apply_data 以返回值表明是否真的更新了(供避免无谓重绘)。
    from manager.pages.datasources import DataSourcesPage
    ds = DataSourcesPage(on_set_provider=lambda p, e: None, on_set_interval=lambda t, i: None)
    ds.update({"providers": [{"id": "system", "enabled": True, "status": "running",
        "topics": [{"topic": "system.cpu", "interval": 1.0, "last_value": None,
                    "last_ts": None, "last_error": None}]}]})
    assert ds.apply_data("system.cpu", {"percent": 5.0}) is True   # 首次 → 更新
    assert ds.apply_data("system.cpu", {"percent": 5.0}) is False  # 同值 → 跳过
    assert ds.apply_data("system.cpu", {"percent": 6.0}) is True   # 变化 → 更新
    assert ds.apply_data("unknown.topic", 1) is False             # 无此行 → 不动作


def test_overview_autostart_sync_no_feedback_loop():
    from manager.pages.overview import OverviewPage
    calls = []
    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None,
                      on_autostart=lambda e: calls.append(e))
    ov.set_autostart_active(True)
    assert ov._autostart.get_active() is True
    assert calls == []                        # 程序化同步未回环触发 on_autostart


def test_overview_tray_close_toggle_invokes_callback():
    # 「托盘行为」是真开关:用户切换 → 回调(app 据此落盘 close_to_tray 偏好)。
    from manager.widgets.draw import PillSwitch
    from manager.pages.overview import OverviewPage
    calls = []
    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None,
                      on_autostart=lambda _e: None, on_tray_close=lambda v: calls.append(v))
    assert isinstance(ov._tray_close, PillSwitch)          # 是开关,不再是静态文字
    ov._tray_close.set_active(not ov._tray_close.get_active())
    assert calls and isinstance(calls[-1], bool)           # 用户切换触发了回调


def test_overview_tray_close_sync_no_feedback_loop():
    # 关窗对话框「记住我的选择」回写开关时,程序化同步不得回环触发 on_tray_close。
    from manager.pages.overview import OverviewPage
    calls = []
    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None,
                      on_autostart=lambda _e: None, on_tray_close=lambda v: calls.append(v))
    ov.set_tray_close_active(False)
    assert ov._tray_close.get_active() is False
    ov.set_tray_close_active(True)
    assert ov._tray_close.get_active() is True
    assert calls == []                        # 程序化同步未回环


def test_overview_tray_close_default_matches_close_behavior(monkeypatch):
    # 偏好未设(None)时,真实关窗走 decide_close→"ask"(弹询问),并非静默收托盘。
    # 故开关初始必须为「关」,否则新用户看到开关开着、点 × 却仍被询问,自相矛盾。
    import manager.settings as settings
    from manager.settings import decide_close
    from manager.pages.overview import OverviewPage
    monkeypatch.setattr(settings, "load_close_to_tray", lambda: None)
    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None,
                      on_autostart=lambda _e: None, on_tray_close=lambda _v: None)
    assert ov._tray_close.get_active() is False           # 开关初始为关
    assert decide_close(None) != "tray"                   # 与真实关窗行为(询问)一致


def test_overview_tray_close_disabled_without_tray():
    # 无托盘(降级)时,关窗只能退出,托盘开关应置灰。
    from manager.pages.overview import OverviewPage
    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None,
                      on_autostart=lambda _e: None, on_tray_close=lambda _v: None)
    ov.set_tray_available(False)
    assert ov._tray_close.get_switch_sensitive() is False
    ov.set_tray_available(True)
    assert ov._tray_close.get_switch_sensitive() is True


def _classes(widget):
    return set(widget.get_style_context().list_classes())


def test_overview_banner_matches_prototype_structure():
    # 原型中状态横幅本身就是彩色卡片,不再套一层白色 .mw-card。
    from manager.pages.overview import OverviewPage

    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None,
                      on_autostart=lambda _enabled: None)
    assert ov._banner.get_parent() is ov
    assert "mw-banner" in _classes(ov._banner)
    assert "mw-icon-tile" in _classes(ov._banner_tile)
    ov.set_connection("connected")
    assert "is-success" in _classes(ov._banner_tile)


def test_widgets_empty_state_is_card_like_prototype():
    from manager.pages.widgets import WidgetsPage

    page = WidgetsPage()
    assert "mw-card" in _classes(page._empty_card)
    assert "mw-empty-card" in _classes(page._empty_card)
    assert "is-brand" in _classes(page._empty_tile)


def test_datasource_provider_icon_tile_has_brand_background():
    from manager.pages.datasources import DataSourcesPage

    ds = DataSourcesPage(on_set_provider=lambda _p, _e: None,
                         on_set_interval=lambda _t, _i: None)
    ds.update({"providers": [{"id": "system", "enabled": True, "status": "running",
        "topics": [{"topic": "system.cpu", "interval": 1.0, "last_value": None,
                    "last_ts": None, "last_error": None}]}]})
    assert "mw-icon-tile" in _classes(ds._sections["system"]["tile"])
    assert "is-brand" in _classes(ds._sections["system"]["tile"])


def test_sidebar_footer_uses_full_width_status_container():
    from manager.shell import Sidebar

    side = Sidebar(on_nav=lambda _key: None)
    assert "mw-sidebar-foot" in _classes(side._foot)
    assert side._foot.get_halign() == Gtk.Align.FILL
    assert side._foot.get_size_request()[1] == 52
    assert side._foot_row.get_valign() == Gtk.Align.CENTER


def test_overview_metric_grid_expands_like_prototype():
    # 指标卡:横向等分铺满;高度随内容自然撑开(原型紧凑卡),内边距走 CSS .mw-metric-card,
    # 不再固定卡高/子项高(此前固定 104 导致卡过高、内容上挤、底部留白)。
    from manager.pages.overview import OverviewPage

    ov = OverviewPage(on_start=lambda: None, on_stop=lambda: None,
                      on_autostart=lambda _enabled: None)
    assert ov._metric_grid.get_hexpand() is True
    assert ov._metric_grid.get_halign() == Gtk.Align.FILL
    for card in ov._metric_cards:
        assert card.get_hexpand() is True
        assert "mw-metric-card" in _classes(card)        # 内边距来自 CSS,非外部 margin
        assert card.get_size_request()[1] == -1          # 不固定卡高 → 随内容
        assert card.get_valign() == Gtk.Align.START       # 不被纵向拉伸
    for _label, value, foot in ov._metric_widgets.values():
        assert value.get_margin_top() == 6
        assert foot.get_margin_top() == 4


def test_theme_declares_chinese_font_fallback():
    css = Path("manager/assets/style.css").read_text(encoding="utf-8")
    assert "Source Han Sans SC" in css
    assert "Noto Sans CJK SC" in css


def test_theme_text_classes_have_explicit_prototype_font_tokens():
    css = Path("manager/assets/style.css").read_text(encoding="utf-8")

    def block(selector):
        start = css.index(selector)
        end = css.index("}", start)
        return css[start:end]

    expected = {
        ".mw-brand-name": ("font-family:", "font-size: 14px", "font-weight: 700"),
        ".mw-brand-sub": ("font-family:", "font-size: 11px", "font-weight: 400"),
        ".mw-nav-btn": ("font-family:", "font-size: 13px", "font-weight: 600"),
        ".mw-page-title": ("font-family:", "font-size: 18px", "font-weight: 700"),
        ".mw-page-sub": ("font-family:", "font-size: 12px", "font-weight: 400"),
        ".mw-metric-label": ("font-family:", "font-size: 12px", "font-weight: 400"),
        ".mw-metric-value": ("font-family:", "font-size: 22px", "font-weight: 700"),
        ".mw-metric-foot": ("font-family:", "font-size: 11px", "font-weight: 400"),
        ".mw-btn-primary": ("font-family:", "font-size: 14px", "font-weight: 600"),
        ".mw-btn-danger": ("font-family:", "font-size: 14px", "font-weight: 600"),
        ".mw-h-14-600": ("font-family:", "font-size: 14px", "font-weight: 600"),
        ".mw-sub-12": ("font-family:", "font-size: 12px", "font-weight: 400"),
    }
    for selector, tokens in expected.items():
        b = block(selector)
        for token in tokens:
            assert token in b
