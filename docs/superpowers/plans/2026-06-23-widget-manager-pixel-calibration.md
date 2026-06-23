# Widget Manager Pixel Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the GTK manager UI against `prototype/小组件管理器.html` screenshots without changing manager behavior or service contracts.

**Architecture:** Keep the existing GTK3 shell and page classes. Add small structural hooks and CSS classes where the current rendering differs from the prototype, then regenerate deterministic screenshots for overview, data sources, and widgets.

**Tech Stack:** Python 3.11+, GTK 3 via PyGObject, Cairo drawing widgets, pytest, existing `docs/screenshots/` assets.

## Global Constraints

- Do not restore the browser-only fake macOS window chrome; the GTK app uses the real system window.
- Preserve `OverviewPage`, `DataSourcesPage`, `WidgetsPage`, `MainShell`, and callback/data-flow signatures.
- Keep changes surgical and limited to UI structure, CSS, screenshot support, and smoke tests.
- Use the Soft Admin Blue tokens from `docs/design-specs/2026-06-23-widget-manager-ui.md`.

---

### Task 1: Lock the visible structure expected by the prototype

**Files:**
- Modify: `tests/test_manager_smoke.py`
- Modify: `manager/pages/overview.py`
- Modify: `manager/pages/widgets.py`
- Modify: `manager/pages/datasources.py`
- Modify: `manager/assets/style.css`

**Interfaces:**
- Consumes: existing page classes and their private widget attributes used by smoke tests.
- Produces: prototype-aligned classes `mw-icon-tile is-*`, `mw-empty-card`, and direct overview banner placement.

- [ ] **Step 1: Write failing smoke tests**

Add tests that assert:
- `OverviewPage._banner` is packed directly on the page and not wrapped in `.mw-card`.
- `OverviewPage._banner_tile` has `mw-icon-tile`.
- `WidgetsPage._empty_card` has both `mw-card` and `mw-empty-card`.
- data source provider tile has a semantic icon-tile class.

- [ ] **Step 2: Run smoke tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_manager_smoke.py -q`

Expected: at least one failure for missing `_empty_card`, `_banner_tile`, or icon-tile semantic classes.

- [ ] **Step 3: Implement minimal structure changes**

Change only the relevant page builders:
- In overview, pack `self._banner` directly, store `self._banner_tile`, and apply state classes to it.
- In widgets, wrap the empty state in `self._empty_card`.
- In data sources, store provider icon tile references and apply `is-brand`.
- In CSS, give icon tiles and empty cards the prototype backgrounds/padding.

- [ ] **Step 4: Run smoke tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_manager_smoke.py -q`

Expected: all manager smoke tests pass.

### Task 2: Regenerate calibrated screenshots

**Files:**
- Modify: `docs/screenshots/manager-overview.png`
- Modify: `docs/screenshots/manager-datasources.png`
- Modify: `docs/screenshots/manager-widgets.png`
- Optionally modify: `docs/design-specs/2026-06-23-widget-manager-ui.md`

**Interfaces:**
- Consumes: current offscreen GTK construction pattern from the design spec.
- Produces: screenshots reflecting fixed prototype states.

- [ ] **Step 1: Render fixed-state screenshots**

Use an offscreen GTK script with:
- window size `1040x680`
- status values `port=8765`, `clients=2`, `uptime=7200`
- notices containing `config_reset`
- providers `system` and `time` enabled
- CPU `37.2`, memory `58.4`, time ISO value

- [ ] **Step 2: Run full verification**

Run: `.venv/bin/python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 3: Review screenshot diffs**

Compare updated screenshots to the prototype PNGs generated from `prototype/小组件管理器.html`. Record any remaining GTK-only drift in the design spec if it is not worth fixing in this pass.
