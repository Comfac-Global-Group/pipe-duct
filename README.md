# Comfac MEP Workbench

**Procedural open-source MEP (Mechanical, Electrical, Plumbing) tools for FreeCAD.**

This workbench generates parametric 3D infrastructure for building design: pipe networks, HVAC duct systems, cable trays, sheet metal, and structural frames. It combines the legacy **Dodo** frame/pipeline tools with next-generation **Comfac** procedural generation engines.

![Workbench Icon](iconz/dodo.svg)

---

## Features

### Pipes
- **Sketch-driven pipe networks** — Draw a 2D sketch, generate an interconnected hollow pipe network automatically
- **Interactive 3D Router** — HUD-based viewport routing with magnetic snapping, axis locks, and real-time dimension input
- **Auto-fittings** — Caps, tees, and wyes generated at intersection points
- **Standards compliance** — ASME B36.10M pipe tables (Copper K/L/M, EMT, IMC, Rigid, PVC)
- **Live parametric updates** — Change the sketch, the network rebuilds automatically

### Ducts
- **HVAC ductwork** — Rectangular, rounded rectangular, and circular profiles
- **ASHRAE/SMACNA standards** — External JSON data for gauge thicknesses, pressure classes, and aspect ratio rules
- **Fitting library** — Elbows (smooth, segmented, mitered), tees, wyes (converging, conical, dovetail), reducers, offsets
- **Splitter vanes** — Auto-generated for segmented elbows
- **Live observer** — Parametric rebuild on sketch changes

### Cables
- Cable trays, cable ladders, fiber trays, wire gutters
- 2D offset geometry with dynamic elbow generation
- Wall/lip extrusion with parametric profiles

### Sheets
- Corrugated and perforated sheet metal
- Patterned extrusions based on parametric profiles

### Frames (Legacy Dodo)
- Structural frame/truss generation
- Standard section profiles (HEA, IPE, UPN, RHS, rebar)
- Beam operations: extend, stretch, shift, level, align, miter

### Utilities
- **Bill of Materials (BOM)** — Automatic material takeoffs with CSV export
- **Transition reducers** — Connect mismatched pipe/duct sizes
- **STEP import helper** — Batch import valve and equipment geometry

---

## Installation

### FreeCAD Addon Manager (Recommended)
1. Open FreeCAD
2. Go to **Tools → Addon Manager**
3. Search for **"Comfac MEP Workbench"**
4. Click **Install**
5. Restart FreeCAD
6. Select **"Comfac MEP Workbench"** from the workbench dropdown

### Manual Installation
```bash
# Clone into your FreeCAD Mod directory
cd ~/.FreeCAD/Mod  # or ~/Library/Preferences/FreeCAD/Mod on macOS
git clone https://github.com/Comfac-Global-Group/pipe-duct.git ComfacMEP
```
Restart FreeCAD.

---

## Quick Start

### Generate a Pipe Network
1. Switch to **Sketcher** workbench
2. Draw a path with straight lines (45° and 90° angles supported)
3. Switch to **Comfac MEP Workbench**
4. Select your sketch(es) in the tree
5. Click **MEP Pipes → Generate Pipe Network**
6. Choose pipe type and size from the task panel, or enter custom OD/thickness
7. Click **OK** — the network is generated, fittings are auto-placed

### Generate a Duct Network
1. Draw a single sketch path
2. Select the sketch
3. Click **MEP Ducts → Generate Smart Duct Network**
4. Choose profile (Rectangular / Rounded / Circular), dimensions, and thickness
5. Click **OK** — a live parametric folder is created; edit the sketch to update

### Use the 3D Pipe Router
1. Click **MEP Draft → Smart Pipe Router**
2. Left-click in the 3D view to place nodes
3. Use **`** (backtick) to cycle axis lock, **P** to cycle working plane
4. Type exact dimensions with **Enter**
5. Right-click to finish and generate the pipe

---

## Data Standards

Dimensional data lives in external files under `mep/data/`:

| File | Standard | Contents |
|------|----------|----------|
| `PipeData.json` | ASME / NEC | Pipe OD and wall thickness |
| `PipeColors.json` | — | Material color mappings |
| `ASHRAE_SMACNA_Rectangular.json` | ASHRAE + SMACNA | Duct sizes, gauge rules, pressure classes |
| `FlexibleMetalConduitData.json` | NEC | FMC/LFMC dimensions |
| `PipeLocknutData.json` | — | Locknut geometry |
| `PipeCouplingData.json` | — | Coupling dimensions |
| `PipeBushingData.json` | — | Bushing dimensions |

Legacy Dodo CSV tables remain in `tablez/` for backward compatibility.

---

## Architecture

The workbench follows a **strict MVC pattern**:

- **Data Layer** — External `.json` and `.csv` files for standard dimensions
- **Core Engine** — Pure geometry functions returning `Part.Shape` (no UI)
- **Wrapper Layer** — `FeaturePython` proxies + PySide task panels

Key shared components:
- `ComfacUtils.py` — Universal sweep engine, preview manager, shape fusion helpers
- `DuctGeometryUtils.py` — HVAC geometry builders (elbows, tees, wyes, transitions)
- `NetworkGeometryEngine` — Sketch-to-pipe boolean pipeline
- `PipeRouter.py` — Interactive 3D viewport router with magnetic snapping

---

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full development roadmap.

**Highlights:**
- **Now:** PySide6/Qt6 compatibility ✅, testing framework, standards expansion
- **Q2 2026:** IFC export, unified UI theme, performance optimization for large networks
- **Q3 2026:** Clash detection, automatic hanger/support placement, cloud-ready BOM
- **Q4 2026:** AR/VR preview, generative routing, community scene library

---

## Use Cases

See [`docs/USE_CASES.md`](docs/USE_CASES.md) for detailed scenarios:
- Commercial HVAC design
- Industrial electrical routing
- Plumbing & drainage
- Sci-fi / creative commons scene building
- MEP education & training

---

## Partner With Us

We actively seek collaborators. Whether you're a developer, tester, artist, educator, or standards expert, there's a way to contribute.

See [`docs/PARTNERS.md`](docs/PARTNERS.md) for:
- **Task cards** ready to pick up
- **Skill-matched roles** (testers, creatives, coders, writers)
- **Creative Commons scene submissions**
- **Standards contribution guidelines**

---

## Contributing

We welcome contributions, especially:
- Additional pipe/duct standards (ISO, JIS, etc.)
- New fitting types
- IFC export integration
- Unit tests
- Documentation translations
- Demo scenes and tutorials

Please read:
- `AGENTS.md` — AI coding constitution and conventions
- `docs/QA.md` — Quality assurance guidelines
- `docs/TECH_DEBT.md` — Known technical debt and roadmap
- `docs/ROADMAP.md` — Where the project is headed

---

## License

This project is licensed under the **GNU Lesser General Public License v3 (LGPLv3)**.

Original Dodo/Flamingo tools by Riccardo Treu (oddtopus).  
Comfac MEP extensions and procedural engines by Comfac Global Group.

---

## Links

- [FreeCAD Website](https://www.freecad.org/)
- [FreeCAD Wiki](https://wiki.freecad.org/)
- [Report Issues](https://github.com/Comfac-Global-Group/pipe-duct/issues)
