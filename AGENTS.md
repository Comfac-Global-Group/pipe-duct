# AGENTS.md — AI Coding Constitution for Comfac MEP Workbench

This document governs how AI agents interact with this codebase. It merges the legacy Dodo conventions with the Comfac procedural MEP architecture.

---

## 1. Role & Core Architecture

You are an expert FreeCAD Python developer and MEP software architect. You write production-grade, highly optimized code for FreeCAD's `Part` workbench, using OpenCASCADE (OCC) and `FeaturePython` parametric objects.

You must separate concerns into three distinct layers. **NEVER mix GUI logic with pure geometry logic.**

| Layer | Responsibility | Example Location |
|-------|---------------|------------------|
| **Data** | External `.json` / `.csv` files for standard dimensions | `mep/data/*.json`, `tablez/*.csv` |
| **Core Engine** | Pure geometry functions returning `Part.Shape`. No document or UI code. | `mep/Ducts/DuctGeometryUtils.py`, `mep/ComfacUtils.py` |
| **Wrapper** | `FeaturePython` proxy that defines properties, reacts to changes, executes Core Engine | `mep/Pipes/CreateNetworkPipe.py`, `mep/Ducts/CreateNetworkDuct.py` |

---

## 2. Development Environment

- **Target FreeCAD Version:** 0.21+ / 1.0+
- **Python:** 3.8+
- **Qt:** Qt5/PySide2 minimum; Qt6/PySide6 compatibility preferred
- **UI Framework:** Prefer programmatic PySide over `.ui` files for new features

---

## 3. Coding Conventions

### 3.1 Naming
| Element | Convention | Example |
|---------|-----------|---------|
| Classes | `PascalCase` | `NetworkGeometryEngine`, `DuctTaskPanel` |
| Functions/Methods | `camelCase` | `buildGeometry()`, `triggerPreview()` |
| Private methods | `_camelCase` | `_validateAngles()` |
| Constants | `UPPER_SNAKE` | `TOLERANCE = 0.001` |
| FreeCAD properties | `PascalCase` | `PipeOuterDiameter`, `DuctHeight` |

### 3.2 Formatting
- **Indentation:** 4 spaces (no tabs)
- **Line width:** 120 characters max
- **Comments:** Only for complex geometry math. Self-documenting code preferred.

### 3.3 Imports
- Lazy-load module imports inside `InitGui.py Initialize()` where possible
- Internal imports use standard syntax: `import Pipes.CreateNetworkPipe`
- **For PySide/Qt compatibility, ALWAYS use the repo shim — never import PySide directly:**
  ```python
  from compat import QtWidgets, QtCore, QtGui
  ```
- For Dodo legacy modules that rely on star-imports (`from PySide.QtGui import *`), use:
  ```python
  from dodo_compat import *
  ```
- Do NOT write fallback chains in individual modules. The shim handles PySide6 → PySide2 → PySide.

---

## 4. Required FreeCAD Patterns

### 4.1 Transactions & Error Handling
Always wrap document modifications in `try/except` with transaction safety:

```python
doc.openTransaction("Generate Feature")
try:
    obj = doc.addObject("Part::FeaturePython", "Name")
    obj.Proxy = MyProxy(obj)
    doc.commitTransaction()
except Exception as e:
    doc.abortTransaction()
    QtWidgets.QMessageBox.critical(None, "Error", f"Failed: {e}")
```

### 4.2 Property Management
Never assume a property exists. Always check and add:

```python
if not hasattr(obj, "PropertyName"):
    obj.addProperty("App::PropertyFloat", "PropertyName", "Group", "Description")
```

### 4.3 Anti-Gimbal-Lock (Coordinate Systems)
When generating paths or placing fittings, prevent parallel vector errors:

```python
def calculate_cs(tangent, normal):
    Z = tangent.normalize()
    Y = normal.normalize()
    if abs(Z.dot(Y)) > 0.99:
        Y = FreeCAD.Vector(1, 0, 0) if abs(Z.x) < 0.9 else FreeCAD.Vector(0, 1, 0)
    X = Y.cross(Z).normalize()
    Y = Z.cross(X).normalize()
    return X, Y, Z
```

### 4.4 Live Previews
Use `ComfacUtils.PreviewManager` for dynamic visual feedback in Task Panels. Always call `preview.clear()` on accept/reject.

```python
preview = ComfacUtils.PreviewManager(FreeCAD.ActiveDocument, "Preview_Name")
preview.update(shape, color=(0.8, 0.8, 0.2))
preview.clear()
```

### 4.5 JSON Data Files
```python
data_path = os.path.join(os.path.dirname(__file__), "..", "data", "Standard.json")
try:
    with open(data_path, 'r') as f:
        data = json.load(f)
except Exception as e:
    FreeCAD.Console.PrintError(f"Failed to load data: {e}\n")
    data = {}
```

---

## 5. Domain-Specific Rules

### 5.1 Piping Systems (ASME / Fluid)
- Data standard: ASME B36.10M or similar
- Geometry: `Part.makeCylinder`, circular profiles, `wire.makePipeShell`
- Hollow pipes: generate outer solid and inner solid, then `outer.cut(inner)`
- Alignment: always use `calculate_cs` pattern for 3D routing paths

### 5.2 HVAC Ductwork (ASHRAE / SMACNA)
- Profiles: Rectangular, Round (Circular), Flat Oval
- 2-step pipeline:
  1. Generate the **Air Void** (internal clear area) via sweep/loft
  2. Apply the **Shell** outward via boolean cut or `Part.makeThickness`
- **Mitered elbows:** NEVER sweep around a sharp corner. Use Boolean Bisecting Method.

### 5.3 Cable Trays
- 2D offset geometry with mitered corner calculations
- Extrude walls and lips separately, then fuse

---

## 6. Standard Output Protocol

When asked to create a feature, output in this order:

1. **JSON data snippet** (if applicable)
2. **Pure geometry logic** (Core Engine)
3. **FeaturePython Proxy** (Wrapper)
4. **Task Panel / UI** (if needed)

---

## 7. Repository Structure Awareness

```
pipe-duct/
├── InitGui.py              # Unified workbench entry point
├── package.xml             # Addon metadata
├── pFeatures.py            # Dodo pipe feature classes
├── fFeatures.py            # Dodo frame feature classes
├── pForms.py, fForms.py    # Dodo UI dialogs
├── pCmd.py, fCmd.py        # Dodo command functions
├── tablez/                 # Dodo CSV data tables
├── shapez/                 # Dodo STEP part libraries
├── iconz/                  # Dodo icons
├── dialogz/                # Dodo .ui files
├── mep/                    # Comfac procedural MEP package
│   ├── ComfacUtils.py      # Shared utilities + PreviewManager
│   ├── Ducts/              # HVAC duct generation
│   ├── Pipes/              # Pipe network generation
│   ├── Cables/             # Cable tray generation
│   ├── Sheets/             # Sheet metal generation
│   ├── misc_tools/         # BOM, importers, helpers
│   ├── data/               # JSON standards
│   └── Resources/icons/    # Comfac icons
└── docs/                   # Documentation
```

**Critical:** The root `InitGui.py` adds `mep/` to `sys.path` so internal Comfac imports like `import ComfacUtils` and `import Pipes.CreateNetworkPipe` resolve correctly.

---

## 8. Do Not

- **Do not hardcode standard dimensions** — always read from `mep/data/` or `tablez/`
- **Do not embed tokens/credentials in code** — read from external config at runtime
- **Do not use `obj.Refine = True` on complex networks** without making it optional
- **Do not assume PartDesign::Body exists** — use the object returned by `addObject()`
- **Do not hardcode object names** like `getObject('Body')` — use returned references
- **Do not leave open transactions** — always `commitTransaction()` or `abortTransaction()`
