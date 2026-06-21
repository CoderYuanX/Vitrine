import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.preview_manager import MockCatalog


def test_mock_catalog_toggle_updates_visible_widget_enabled():
    catalog = MockCatalog()
    clock = next(w for w in catalog._vis() if w["id"] == "clock")
    assert clock["enabled"] is True

    catalog.toggle("clock", False)

    clock = next(w for w in catalog._vis() if w["id"] == "clock")
    assert clock["enabled"] is False
