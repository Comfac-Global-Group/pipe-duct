# REPOANALYSIS.md — AI Repository Map
**Comfac MEP Workbench**

This document is optimized for AI agents. It provides a structural overview, module relationships, data flows, and entry points so that an agent can navigate and modify the codebase efficiently.

---

## 1. Repository Identity

| Property | Value |
|----------|-------|
| **Name** | Comfac MEP Workbench |
| **Origin** | Fork of Dodo (oddtopus/dodo) + Comfac MEP Tools |
| **Remote** | `https://github.com/Comfac-Global-Group/pipe-duct` |
| **License** | LGPLv3 |
| **Language** | Python 3 |
| **Domain** | FreeCAD workbench for procedural MEP infrastructure |

---

## 2. Directory Tree (Simplified)

```
pipe-duct/
├── InitGui.py              # UNIFIED ENTRY POINT — registers Dodo + Comfac toolbars
├── Init.py                 # Module init (boilerplate)
├── package.xml             # FreeCAD Addon Manager metadata
├── README.md               # Human-facing project overview
├── AGENTS.md               # AI coding constitution
├── LICENSE                 # LGPLv3
├── compat.py               # PySide6/Qt6 → PySide2 → PySide fallback shim (Comfac + general)
├── dodo_compat.py          # Dodo legacy Qt4-style re-export shim (bare widget names)
│
# === DODO LEGACY (Root Level) ===
├── pFeatures.py            # Pipe FeaturePython classes (Pipe, Elbow, Reduct, Cap, Flange, etc.)
├── fFeatures.py            # Frame FeaturePython classes + dialogs
├── pForms.py               # Pipe UI dialogs and commands
├── fForms.py               # Frame UI dialogs and commands
├── pCmd.py                 # Pipe utility functions (readTable, portsPos, moveToPyLi, etc.)
├── fCmd.py                 # Frame utility functions
├── uCmd.py                 # General utility commands
├── CFrame.py               # Frame command registrations
├── CPipe.py                # Pipe command registrations
├── CUtils.py               # General utility commands
├── dodoPM.py               # Pie-menu style quick access UI
├── dodoDialogs.py          # Shared dialog utilities
├── anyShapez.py            # Generic shape insertion
├── pObservers.py           # Pipe document observers
├── fObservers.py           # Frame document observers
│
├── tablez/                 # CSV data tables (Dodo legacy)
├── shapez/                 # STEP part libraries (valves)
├── iconz/                  # SVG icons (Dodo legacy)
├── dialogz/                # Qt .ui files (Dodo legacy)
│
# === COMFAC MEP (mep/ package) ===
├── mep/
│   ├── Init.py             # Comfac module init (boilerplate)
│   ├── InitGui.py          # REFERENCE ONLY — NOT AUTO-EXECUTED (workbench reg kept for reference)
│   ├── ComfacUtils.py      # SHARED ENGINE: PreviewManager, sweep_sketch_wires, fuse_shapes, get_icon_path
│   ├── opencode.json       # (unknown metadata)
│   │
│   ├── data/               # JSON standards
│   │   ├── PipeData.json
│   │   ├── PipeColors.json
│   │   ├── ASHRAE_SMACNA_Rectangular.json
│   │   ├── FlexibleMetalConduitData.json
│   │   ├── PipeBushingData.json
│   │   ├── PipeCouplingData.json
│   │   ├── PipeFlexConduitData.json
│   │   └── PipeLocknutData.json
│   │
│   ├── Ducts/
│   │   ├── CreateNetworkDuct.py          # Smart folder + live observer + task panel
│   │   ├── CreateSolidDuct.py            # Solid duct generation
│   │   ├── CreateNetworkDuctInsulation.py
│   │   ├── CreateDuctFittings.py         # Auto-fitting generation
│   │   ├── CreateDuctHangers.py
│   │   ├── CreateDuctScrews.py
│   │   ├── CreateDuctFastener.py
│   │   ├── DuctLibrary.py                # Parametric fitting library UI (1400+ lines)
│   │   └── DuctGeometryUtils.py          # CORE ENGINE: build_straight_duct, build_elbow, build_tee, etc.
│   │
│   ├── Pipes/
│   │   ├── CreateNetworkPipe.py          # Sketch-driven pipe network + live observer
│   │   ├── CreateSolidPipeNetwork.py
│   │   ├── CreateNetworkPipeInsulation.py
│   │   ├── CreateNetworkPipeFittings.py  # Fitting generation for networks
│   │   ├── PipeRouter.py                 # INTERACTIVE 3D HUD ROUTER (~1000 lines)
│   │   ├── CreateDetailedFMC.py
│   │   ├── CreateDetailedLFMC.py
│   │   ├── CreatePipeHanger.py
│   │   ├── CreatePipeSaddle.py
│   │   ├── CreatePipeLibraries.py
│   │   ├── CreatePipeLocknut.py
│   │   └── CreateFlexConduit.py
│   │
│   ├── Cables/
│   │   ├── CreateDetailedCableTray.py
│   │   ├── CreateCableLadderFittings.py
│   │   ├── CreateFiberTray.py
│   │   └── CreateWireGutter.py
│   │
│   ├── Sheets/
│   │   ├── CreateCorrugatedSheet.py
│   │   └── CreatePerforatedSheet.py
│   │
│   ├── misc_tools/
│   │   ├── BillOfMaterials.py            # BOM dashboard + CSV export
│   │   ├── CreateNewSketch.py
│   │   ├── CreateNewPartBody.py
│   │   ├── CreateTransitionReducer.py
│   │   ├── ImportFile.py
│   │   ├── MergeHollowNetworks.py
│   │   └── StepImporter.py
│   │
│   ├── Resources/icons/      # 40+ SVG icons for Comfac tools
│   └── Agents/               # AI-specific domain guides
│       ├── AGENTS.md
│       ├── duct-agent.md
│       └── pipe-agent.md
│
└── docs/
    ├── FRD.md                # Feature Requirements Document
    ├── QA.md                 # Quality Assurance Guide
    ├── REPOANALYSIS.md       # This file
    └── TECH_DEBT.md          # Technical Debt Audit
```

---

## 3. Import Resolution

### 3.1 Path Injection (Root InitGui.py)
**Critical:** The root `InitGui.py` executes:
```python
_mep_path = os.path.join(os.path.dirname(__file__), 'mep')
if _mep_path not in sys.path:
    sys.path.insert(0, _mep_path)
```

This means:
- `import ComfacUtils` resolves to `mep/ComfacUtils.py`
- `import Pipes.CreateNetworkPipe` resolves to `mep/Pipes/CreateNetworkPipe.py`
- `import Ducts.DuctGeometryUtils` resolves to `mep/Ducts/DuctGeometryUtils.py`

**Dodo modules** are at root and use root-level imports:
- `import pFeatures`, `import fFeatures`, `import pCmd`, `import fCmd`

### 3.2 PySide Compatibility Imports

All modules now import through the compatibility layer:

**Comfac modules** use:
```python
from compat import QtWidgets, QtCore, QtGui
```

**Dodo modules** use (preserves Qt4 star-import behavior):
```python
from dodo_compat import *   # re-exports QDialog, QLabel, QLineEdit, etc.
```

Both `compat.py` and `dodo_compat.py` live at the repository root so they are on `sys.path` for both Dodo and Comfac modules.

The shim handles three tiers:
- **Tier 1:** FreeCAD 1.0+ → Qt6 → `PySide6`
- **Tier 2:** FreeCAD 0.21 → Qt5 → `PySide2`
- **Tier 3:** Legacy Qt4 → `PySide` (QtGui re-exports as QtWidgets)

---

## 4. Module Relationships

### 4.1 Comfac MEP Dependency Graph

```
InitGui.py (root)
  └── sys.path inserts mep/
      └── imports trigger command registration

ComfacUtils.py
  ├── Used by: ALL Comfac modules
  ├── Provides: get_icon_path(), PreviewManager, sweep_sketch_wires(), fuse_shapes(), calculate_orientation()

Pipes/CreateNetworkPipe.py
  ├── Imports: ComfacUtils, Pipes.CreateNetworkPipeFittings
  ├── Uses: NetworkGeometryEngine, NetworkLiveObserver, PipeTaskPanel
  └── Registers: CreateNetworkPipe command

Pipes/PipeRouter.py
  ├── Imports: ComfacUtils, Pipes.CreateNetworkPipeFittings
  ├── Uses: PipeRouterTaskPanel, RouterHUDWidget, RouterKeyFilter
  └── Registers: PipeRouter command

Ducts/CreateNetworkDuct.py
  ├── Imports: Ducts.DuctGeometryUtils, ComfacUtils
  ├── Uses: DuctGeom, DuctLiveObserver, DuctTaskPanel
  └── Registers: CreateNetworkDuct command

Ducts/DuctLibrary.py
  ├── Imports: Ducts.DuctGeometryUtils
  ├── Uses: ParametricDuct (FeaturePython proxy), DuctLibraryTaskPanel
  └── Registers: DuctLibrary command

Ducts/DuctGeometryUtils.py
  ├── Used by: CreateNetworkDuct.py, DuctLibrary.py
  └── Provides: build_straight_duct(), build_elbow(), build_tee(), build_offset(), etc.

misc_tools/BillOfMaterials.py
  ├── Reads: All document objects with custom properties
  └── Registers: BillOfMaterials command
```

### 4.2 Dodo Dependency Graph

```
InitGui.py (root)
  ├── CUtils → uCmd, dodoDialogs
  ├── CFrame → fFeatures, fForms, fCmd
  ├── CPipe → pFeatures, pForms, pCmd
  └── dodoPM → quick menu UI

pFeatures.py
  ├── Base class: pypeType
  └── Derived: Pipe, Elbow, Reduct, Cap, Flange, Ubolt, Valve

pCmd.py
  ├── Uses: pFeatures, fCmd
  └── Provides: readTable(), portsPos(), portsDir(), moveToPyLi()

fFeatures.py
  ├── Uses: ArchProfile, Arch.Structure
  └── Provides: FrameBranch, frameLineForm dialog
```

---

## 5. Data Flow

### 5.1 Pipe Network Generation

```
User selects sketch(es)
  → CreateNetworkPipe command
    → PipeTaskPanel opens
      → User selects Pipe Type + Size (or custom OD/thk)
      → Live preview via PreviewManager
      → On OK:
        → NetworkGeometryEngine.build_geometry()
          → Validates angles (45°, 90°, 180°)
          → Validates segment lengths
          → Sweeps OD profile along edges
          → Sweeps ID profile along edges
          → Adds spheres at intersections
          → Boolean cut: outer.cut(inner)
        → Creates smart folder (App::DocumentObjectGroup)
        → Attaches live observer properties
        → Auto-generates fittings via PipeFittingTaskPanel
```

### 5.2 Duct Network Generation

```
User selects sketch
  → CreateNetworkDuct command
    → DuctTaskPanel opens
      → User selects profile type, dimensions, thickness
      → Live preview via PreviewManager
      → On OK:
        → DuctGeom.build_geometry()
          → For Circular: cylinder-based geometry
          → For Rectangular/Rounded:
            → get_junction_points() → build_simple_paths()
            → fillet_wire_path() (if rounded corners)
            → create_profile() at start point
            → makePipeShell() along wire
            → Boolean cut for hollow
        → Creates smart folder with live properties
        → DuctLiveObserver watches sketch/folder changes
```

### 5.3 Live Observer Pattern

```
Document observer (global singleton)
  → slotChangedObject(obj, prop)
    → If sketch Shape/Placement changed:
      → Find owning smart folder
      → Add to pending_rebuilds set
      → Start debounce timer (500ms)
    → If folder properties changed:
      → Add to pending_rebuilds set
      → Start debounce timer
  → Timer fires → process_rebuilds()
    → For each pending folder:
      → Read latest properties
      → Call geometry engine
      → Replace old geometry
      → Recompute document
```

---

## 6. Key Entry Points for AI Modification

| If you want to... | Go to... |
|-------------------|----------|
| Add a new pipe standard | `mep/data/PipeData.json` + `Pipes/CreateNetworkPipe.py` (dropdown population) |
| Add a new duct fitting type | `Ducts/DuctGeometryUtils.py` (geometry builder) + `Ducts/DuctLibrary.py` (UI) |
| Change the sweep engine | `mep/ComfacUtils.py` → `sweep_sketch_wires()` |
| Change live preview behavior | `mep/ComfacUtils.py` → `PreviewManager` class |
| Change pipe validation rules | `Pipes/CreateNetworkPipe.py` → `NetworkGeometryEngine` |
| Change duct validation rules | `Ducts/CreateNetworkDuct.py` → `DuctGeom` |
| Add a new toolbar | Root `InitGui.py` → `Initialize()` |
| Add a new icon | `mep/Resources/icons/` (Comfac) or `iconz/` (Dodo) |
| Change color defaults | `mep/data/PipeColors.json` |
| Fix PySide compatibility | `compat.py`, `dodo_compat.py` (already fixed — see `TECH_DEBT.md` CD-01) |
| Change BOM behavior | `mep/misc_tools/BillOfMaterials.py` → `generate_bom()` |

---

## 7. Conventions That Matter

### 7.1 Command Registration
FreeCAD commands are registered at module import time:
```python
FreeCADGui.addCommand('CommandName', CommandClass())
```
This happens in almost every `Create*.py` module. If you rename a command string, you **must** update the toolbar list in `InitGui.py`.

### 7.2 FeaturePython Proxy Pattern
```python
class MyProxy:
    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty("App::PropertyLength", "MyDim", "Group", "Description")
    def execute(self, fp):
        fp.Shape = buildGeometry(fp.MyDim)
```

### 7.3 Task Panel Pattern
```python
class MyTaskPanel:
    def __init__(self):
        self.form = QtWidgets.QWidget()
        # ... build UI ...
    def accept(self):
        # generate final geometry
        return True
    def reject(self):
        # cleanup previews
        return True
```

---

## 8. Testing a Change

After modifying any geometry engine:
1. Restart FreeCAD (workbenches are cached)
2. Run smoke test ST-01 and ST-02
3. Run the relevant manual tests from `docs/QA.md`
4. Check FreeCAD Report View for Python errors

**PySide compatibility quick-check (no FreeCAD needed):**
```bash
cd /path/to/pipe-duct
python3 -m py_compile compat.py dodo_compat.py
find mep -name '*.py' -exec python3 -m py_compile {} \;
```

No automated test suite exists yet. All validation is manual. See `TECH_DEBT.md` HD-01.
