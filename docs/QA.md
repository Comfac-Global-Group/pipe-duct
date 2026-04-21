# Quality Assurance Guide
**Comfac MEP Workbench**

---

## 1. Purpose

This document defines testing procedures, coding standards, and quality gates for the Comfac MEP Workbench. All contributors should follow this guide before submitting changes.

---

## 2. Manual Test Matrix

### 2.1 Smoke Tests (Run before every commit)

| Test | Steps | Expected Result |
|------|-------|-----------------|
| ST-01 | Install workbench in fresh FreeCAD profile | Workbench appears in dropdown, no import errors |
| ST-02 | Switch to Comfac MEP Workbench | All toolbars load: Utils, frameTools, pipeTools, MEP Draft, MEP Pipes, MEP Ducts, MEP Sheets, MEP Cables, MEP Utils |
| ST-03 | Click each toolbar button | Buttons are enabled; task panels open without traceback |
| ST-04 | Hover over buttons | Tooltips display correctly |

### 2.2 Pipe Network Tests

| Test | Steps | Expected Result |
|------|-------|-----------------|
| PN-01 | Sketch single straight line → Generate Pipe Network | Hollow pipe generated, color applied |
| PN-02 | Sketch 90° elbow → Generate | Sphere at intersection, smooth outer shell |
| PN-03 | Sketch 45° branch → Generate | Tee fitting auto-generated at junction |
| PN-04 | Sketch curve → Generate | Error dialog: "Pipes require sharp corners" |
| PN-05 | Sketch segment < OD/2 → Generate | Error dialog: "Segment too short" |
| PN-06 | Sketch invalid angle (e.g., 30°) → Generate | Error dialog: "Invalid angle" |
| PN-07 | Change sketch after generation | Network auto-rebuilds (live observer) |
| PN-08 | Select multiple sketches → Generate | Single network spanning all sketches |
| PN-09 | Generate with PVC type → select blue | Pipe colored blue; property stored |
| PN-10 | Generate → click Add Fittings | Caps/tees appear at open ends |

### 2.3 Duct Network Tests

| Test | Steps | Expected Result |
|------|-------|-----------------|
| DN-01 | Sketch single line → Generate Smart Duct | Hollow rectangular duct generated |
| DN-02 | Select Circular profile → Generate | Cylindrical duct, height = width |
| DN-03 | Select Rounded Rectangular → set radius | Duct with rounded corners |
| DN-04 | Sketch segment < 250mm at junction | Error dialog before generation |
| DN-05 | Change sketch after generation | Duct auto-rebuilds within ~1 second |
| DN-06 | Change folder properties (width, height) | Duct auto-rebuilds |
| DN-07 | Mitered corner type → 90° sketch | Boolean bisected elbow, no sweep squash |
| DN-08 | Rounded corner type → 90° sketch | Filleted wire path with arc segments |
| DN-09 | Open DuctLibrary → select Elbow → place | Elbow aligns to selected edge |
| DN-10 | Open DuctLibrary → select Tee → place | Tee aligns to trunk/branch directions |

### 2.4 Pipe Router Tests

| Test | Steps | Expected Result |
|------|-------|-----------------|
| PR-01 | Click Smart Pipe Router → left-click in 3D view | Node placed, ghost cylinder appears |
| PR-02 | Move mouse | Live preview cylinder follows with dynamic color |
| PR-03 | Press ` (backtick) twice | Axis lock cycles; HUD mode label updates |
| PR-04 | Press Enter → type "500" → Enter | Segment of 500mm placed |
| PR-05 | Press U | Last segment undone |
| PR-06 | Click near existing pipe vertex | Magnetic snap snaps to vertex |
| PR-07 | Right-click to finish | Pipe network generated with selected specs |
| PR-08 | Press ESC | All ghosts removed, route cancelled |

### 2.5 Frame Tests (Legacy Dodo)

| Test | Steps | Expected Result |
|------|-------|-----------------|
| FT-01 | Insert standard IPE section | 2D profile appears in XY plane |
| FT-02 | Draw path → FrameLine Manager → select profile + path | Frame generated along path |
| FT-03 | Select beam → extend to intersection | Beam extends until it hits target |
| FT-04 | Select two beams → rotJoin | Mitered joint created at intersection |

### 2.6 BOM Tests

| Test | Steps | Expected Result |
|------|-------|-----------------|
| BOM-01 | Create pipe + duct + wall → Open BOM | All items listed with correct categories |
| BOM-02 | Click Export to CSV | CSV file saved with correct headers |
| BOM-03 | Open CSV in spreadsheet app | Data readable, units correct |

---

## 3. Coding Standards Checklist

Before submitting code, verify:

- [ ] **No hardcoded dimensions** — all standards live in `mep/data/*.json` or `tablez/*.csv`
- [ ] **MVC separation** — geometry logic is separate from UI logic
- [ ] **Transaction safety** — all doc modifications wrapped in `openTransaction`/`commitTransaction`/`abortTransaction`
- [ ] **Property checks** — use `hasattr` before accessing custom properties
- [ ] **Anti-gimbal-lock** — coordinate systems handle parallel vectors gracefully
- [ ] **Preview cleanup** — `PreviewManager.clear()` called on accept/reject
- [ ] **Error handling** — user-facing errors use `QtWidgets.QMessageBox`, not silent failures
- [ ] **PySide compatibility** — fallback chain for PySide6/PySide2/PySide
- [ ] **Icon paths** — use `ComfacUtils.get_icon_path()` or dynamic path resolution
- [ ] **No Python 2 code** — remove `sys.version_info[0] < 3` checks and `print` statements without parentheses

---

## 4. PR Checklist

- [ ] All smoke tests pass
- [ ] Relevant manual tests pass (mark which ones)
- [ ] Coding standards checklist completed
- [ ] Documentation updated (FRD, README, AGENTS if applicable)
- [ ] No new hardcoded tolerances (or added to `ComfacUtils.TOLERANCE` constant)
- [ ] JSON data files validated (run through `json.load`)
- [ ] No broken imports in `InitGui.py`
- [ ] Icons provided for new tools (SVG preferred)

---

## 5. Known Limitations

These are accepted limitations, not bugs:

1. **Dodo pipeTools and Comfac MEP Pipes are separate pipelines** — You cannot convert a Dodo `Pipe` object into a Comfac network pipe or vice versa.
2. **Two data formats coexist** — Dodo uses CSV; Comfac uses JSON. Unification is on the roadmap.
3. **No IFC export** — BIM integration requires native FreeCAD BIM workbench or external converter.
4. **No unit tests** — All testing is currently manual. Unit test framework is planned.
5. **FreeCAD 1.0/Qt6 not fully validated** — Primary target is FreeCAD 0.21 / Qt5.

---

## 6. Release Criteria

A new version may be released when:

- All smoke tests pass on FreeCAD 0.21.2 and FreeCAD 1.0 (if available)
- Manual test matrix passes for the affected tool groups
- No new `Critical` or `High` technical debt introduced
- `package.xml` version incremented
- `CHANGELOG.md` updated (if it exists)
