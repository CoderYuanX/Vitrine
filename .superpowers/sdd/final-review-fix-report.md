# Final Review Fix Report — Tray ↔ Manager UI State Desync

## Bug
Two surfaces toggled widget visibility independently:
- Tray called `host.runtime.set_enabled(wid, checked)` directly — no signal emitted → manager cards stayed stale.
- Manager UI emitted `CatalogBridge.changed` but tray `QAction.checked` was never refreshed.

## Fix applied to `src/manager/tray.py`

### Change 1: route tray toggle through `catalog.toggle`

**Old (line 30):**
```python
act.toggled.connect((lambda wid: (lambda checked: host.runtime.set_enabled(wid, checked)))(w["id"]))
```
**New:**
```python
act.toggled.connect((lambda wid: (lambda checked: host.catalog.toggle(wid, checked)))(w["id"]))
```

### Change 2: subscribe tray to `catalog.changed` for resync

Added after `tray.show()` / before `return tray`:
```python
def _resync():
    for wid, act in host._toggle_actions.items():
        act.blockSignals(True)
        act.setChecked(host.runtime.is_shown(wid))
        act.blockSignals(False)

host._tray_resync = _resync
host.catalog.changed.connect(_resync)
```

`blockSignals` prevents the resync from re-emitting `toggled` and causing infinite recursion.
`host._tray_resync` holds a reference to prevent GC.

## Verification

### pytest (23 unit tests)
```
23 passed in 0.07s
```

### Smoke test: `tools/smoke_tray_sync.py`
Script constructs ManagerApp-equivalent, bootstraps clock, builds tray, then:
1. Asserts clock tray action checked after bootstrap.
2. `catalog.toggle("clock", False)` → asserts `runtime.is_shown` False AND tray action unchecked.
3. `catalog.toggle("clock", True)` → asserts both True again.
4. `catalog.hideAll()` → asserts tray action unchecked.

Output:
```
qt.core.qobject.connect: No such signal QPlatformNativeInterface::systemTrayWindowChanged(QScreen*)  (benign)
SYNC OK
```

### QML render check
```
SHOT OK 1000 x 704
QML WARNINGS: none
```

## Result
CatalogBridge is now the single mutation/notify hub. No changes to `WidgetRuntime`, `FakeRuntime`, or any test file.
