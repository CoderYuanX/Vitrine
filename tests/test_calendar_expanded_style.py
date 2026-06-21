from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / "widgets" / "Calendar" / name).read_text(encoding="utf-8")


def test_dashboard_uses_light_container_not_dark_glass():
    qml = _read("Dashboard.qml")

    assert "Qt.rgba(16/255, 22/255, 46/255, 0.5)" not in qml
    assert 'color: "#fbfcfe"' in qml


def test_dashboard_close_button_stays_inside_window_bounds():
    qml = _read("Dashboard.qml")

    assert "x: parent.width + 10" not in qml
    assert "anchors.right: parent.right" in qml


def test_weather_card_receives_live_date_from_calendar_root():
    calendar = _read("Calendar.qml")
    dashboard = _read("Dashboard.qml")

    assert "fullDateLabel: root.dateLong" in calendar
    assert "dateText: root.fullDateLabel" in dashboard


def test_expanded_calendar_qml_avoids_emoji_icons():
    emoji_icons = ["📍", "💧", "📊", "⏱", "🌙"]
    for name in [
        "WeatherCard.qml",
        "ProductivityCard.qml",
        "UpcomingCard.qml",
        "LunarCard.qml",
    ]:
        qml = _read(name)
        assert not any(icon in qml for icon in emoji_icons), name


def test_dashboard_does_not_fade_or_stagger_during_window_resize():
    qml = _read("Dashboard.qml")

    assert "scale: 0.9" not in qml
    assert "popAnim" not in qml
    assert 'target: root; property: "opacity"' not in qml
    assert 'target: root; property: "scale"' not in qml


def test_dashboard_animation_keeps_panel_visible():
    qml = _read("Dashboard.qml")

    assert "visible: opacity > 0" in qml
    assert "NumberAnimation { target: fade" in qml
    assert "PauseAnimation" in qml
