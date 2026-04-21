# Feature Requirements Document (FRD)
**Comfac MEP Workbench v2.0.0**

---

## 1. Purpose

This document defines the functional requirements for every tool group in the Comfac MEP Workbench. It serves as the canonical reference for developers, testers, and AI contributors when implementing or modifying features.

---

## 2. Tool Groups

### 2.1 Utils (Legacy Dodo)

| ID | Tool | Function | Input | Output |
|----|------|----------|-------|--------|
| U-01 | selectSolids | Select all solid bodies in the document | — | Selection set |
| U-02 | queryModel | Query properties of selected objects | Selection | Property dump |
| U-03 | moveWorkPlane | Move the working plane | Point/vector | Updated WP |
| U-04 | offsetWorkPlane | Offset the working plane by distance | Distance | Updated WP |
| U-05 | rotateWorkPlane | Rotate the working plane | Angle | Updated WP |
| U-06 | hackedL | Create a constrained line | Two points | Sketch line |
| U-07 | moveHandle | Move objects by handle | Selection + vector | Transformed objects |
| U-08 | dpCalc | Diameter/pressure calculator | Flow rate, velocity | Recommended DN |

---

### 2.2 Frame Tools (Legacy Dodo)

| ID | Tool | Function | Input | Output |
|----|------|----------|-------|--------|
| F-01 | frameIt | Create a frame line from a path | Path + profile | FrameLine object |
| F-02 | FrameBranchManager | Manage frame branches | Selection | Branch object |
| F-03 | insertSection | Insert standard steel section | Section type | 2D profile |
| F-04 | spinSect | Rotate a section | Selection + angle | Rotated profile |
| F-05 | reverseBeam | Reverse beam direction | Selection | Flipped beam |
| F-06 | shiftBeam | Shift beam laterally | Selection + distance | Moved beam |
| F-07 | pivotBeam | Pivot beam around axis | Selection + angle | Rotated beam |
| F-08 | levelBeam | Level beam to reference | Selection + target | Leveled beam |
| F-09 | alignEdge | Align beam edge | Two edges | Aligned beams |
| F-10 | rotJoin | Rotate-join two beams | Two beams | Mitered joint |
| F-11 | alignFlange | Align beam flanges | Two beams | Aligned flanges |
| F-12 | stretchBeam | Stretch beam length | Selection + delta | Lengthened beam |
| F-13 | extend | Extend beam to intersection | Two beams | Trimmed/extended |
| F-14 | adjustFrameAngle | Adjust frame angle | Selection + angle | Adjusted frame |
| F-15 | insertPath | Insert beam along path | Path + profile | Multi-beam frame |

**Data Requirements:**
- Standard sections from `tablez/Section_HEA.csv`, `Section_IPE.csv`, `Section_UPN.csv`, `Section_RH.csv`, `Section_REBARS.csv`

---

### 2.3 Pipe Tools (Legacy Dodo)

| ID | Tool | Function | Input | Output |
|----|------|----------|-------|--------|
| P-01 | insertPipe | Insert a single pipe | DN, OD, thk, length | Pipe feature |
| P-02 | insertElbow | Insert elbow fitting | DN, angle, radius | Elbow feature |
| P-03 | insertReduct | Insert reducer | Two DNs | Reducer feature |
| P-04 | insertCap | Insert end cap | DN | Cap feature |
| P-05 | insertValve | Insert valve | DN, type | Valve feature (+ STEP if available) |
| P-06 | insertFlange | Insert flange | DN, rating | Flange feature |
| P-07 | insertUbolt | Insert U-bolt clamp | DN | Clamp feature |
| P-08 | insertPypeLine | Create a pipeline group | Selection | PypeLine group |
| P-09 | insertBranch | Create a branch | Selection | Branch group |
| P-10 | insertTank | Insert cylindrical tank | Diameter, height | Tank feature |
| P-11 | insertRoute | Route pipes along edges | Edges | Routed pipes |
| P-12 | breakPipe | Break pipe at point | Selection | Two pipes |
| P-13 | mateEdges | Mate two edges | Two edges | Aligned objects |
| P-14 | flat | Flatten selection | Selection | Aligned to WP |
| P-15 | extend2intersection | Extend to intersection | Two pipes | Extended pipes |
| P-16 | extend1intersection | Extend one to intersection | Pipe + target | Extended pipe |
| P-17 | makeHeader | Create pipe header | Multiple pipes | Header assembly |
| P-18 | laydown | Lay pipe down to WP | Selection | Reoriented pipe |
| P-19 | raiseup | Raise pipe from WP | Selection | Reoriented pipe |
| P-20 | attach2tube | Attach to tube | Selection | Constrained placement |
| P-21 | point2point | Place point-to-point | Two points | Pipe between |
| P-22 | insertAnyz | Insert any-shape part | STEP file | Imported shape |

**Data Requirements:**
- Pipe tables: `tablez/Pipe_SCH-STD.csv`, `Pipe_SCH-XXS.csv`
- Fitting tables: `tablez/Elbow_SCH-STD.csv`, `Cap_SCH-STD.csv`, `Flange_*.csv`, `Reduct_*.csv`
- Valve STEP libraries: `shapez/ballvalves/`, `butterflyvalves/`, `checkvalves/`

---

### 2.4 MEP Draft Tools (Comfac)

| ID | Tool | Function | Input | Output |
|----|------|----------|-------|--------|
| MD-01 | Custom_NewSketch | Create a new sketch on active plane | — | Sketch object |
| MD-02 | Custom_NewPartBody | Create a new PartDesign Body | — | Body object |
| MD-03 | PipeRouter | Interactive 3D pipe routing | Mouse clicks + HUD | Pipe network route |

**FR-MD-03 PipeRouter Detail:**
- **Left-click:** Place node / snap to existing geometry
- **Right-click:** Finish route and generate pipe
- **Backtick (`):** Cycle axis lock (Free → X → Y → Z)
- **P:** Cycle working plane (XY → XZ → YZ)
- **Enter:** Type exact length/angle
- **Tab:** Toggle length vs angle input
- **U:** Undo last point
- **B:** Lift pen (branching mode)
- **ESC:** Cancel route
- **Magnetic snap:** Auto-snap to existing pipe vertices and edges within 25mm

---

### 2.5 MEP Pipe Tools (Comfac)

| ID | Tool | Function | Input | Output |
|----|------|----------|-------|--------|
| MP-01 | CreateNetworkPipe | Generate hollow pipe network from sketches | Sketch(es) | Pipe_Network object + fittings |
| MP-02 | Create_Solid_Pipe | Generate solid pipe network (no hollow) | Sketch(es) | Solid pipe object |
| MP-03 | CreateNetworkPipeInsulation | Generate pipe insulation jacket | Pipe network | Insulation shell |
| MP-04 | CreateNetworkPipeFittings | Add caps/tees to pipe ends | Pipe network + selected points | Fitting objects |
| MP-05 | CreateFlexConduit | Generate flexible conduit | Path | Flexible tube |
| MP-06 | CreateDetailedFMC | Generate detailed flexible metal conduit | Path + standard | FMC object |
| MP-07 | CreateDetailedLFMC | Generate detailed liquid-tight FMC | Path + standard | LFMC object |
| MP-08 | CreatePipeHanger | Array pipe hangers along pipe | Pipe selection | Hanger array |
| MP-09 | CreatePipeSaddle | Array pipe saddles along pipe | Pipe selection | Saddle array |
| MP-10 | CreatePipeLibraries | Open pipe fitting library | — | Library dialog |
| MP-11 | CreatePipeLocknut | Generate pipe locknut | Pipe selection | Locknut object |

**FR-MP-01 CreateNetworkPipe Detail:**
- Validates sketch angles: only 45°, 90°, and 180° allowed
- Validates segment lengths: minimum OD/2
- Rejects curves (only straight lines)
- Auto-generates spheres at intersection points for smooth junctions
- Creates smart folder with live observer
- Auto-launches fitting generation after pipe creation
- Supports multiple sketches in one network

**Data Requirements:**
- `mep/data/PipeData.json` — ASME pipe dimensions
- `mep/data/PipeColors.json` — Material color mappings

---

### 2.6 MEP Duct Tools (Comfac)

| ID | Tool | Function | Input | Output |
|----|------|----------|-------|--------|
| MDU-01 | CreateNetworkDuct | Generate smart parametric duct network | Sketch | Duct folder + live observer |
| MDU-02 | Create_Solid_Duct | Generate solid duct (no hollow) | Sketch | Solid duct |
| MDU-03 | CreateNetworkDuctInsulation | Generate duct insulation | Duct network | Insulation shell |
| MDU-04 | CreateDuctFittings | Add fittings to duct ends | Duct network + points | Fitting objects |
| MDU-05 | CreateDuctHangers | Array universal hangers along duct | Duct selection | Hanger array |
| MDU-06 | CreateDuctFastener | Array duct fasteners | Duct selection | Fastener array |
| MDU-07 | CreateDuctScrews | Generate duct screws | Duct selection | Screw array |
| MDU-08 | DuctLibrary | Open parametric duct fitting library | — | Library dialog |

**FR-MDU-01 CreateNetworkDuct Detail:**
- Profiles: Rectangular, Rounded Rectangular, Circular
- Corner types: Rounded (fillet) or Mitered (boolean bisect)
- Alignment: Center, Inner, Outer
- Validates minimum segment length: 250mm for intersecting lines
- Auto-adjusts properties based on profile type (e.g., Circular forces height = width)
- Live observer rebuilds on sketch changes or folder property edits
- Progress dialog shown during rebuild

**FR-MDU-08 DuctLibrary Detail:**
- Categories: Straight, Transitions, Elbow, Tee, Offset
- Profiles: Rectangular, Rounded Rectangular, Circular
- Constructions: Smooth, Segmented, Mitered
- Tee types: Y-Branch, Straight Tee, Cross Tee, T Branch, Converging Wye, Conical Wye, Dovetail, Rectangular Angled Branch, etc.
- Supports splitter vanes for segmented elbows
- Roll angle support for 3D orientation
- Route-aware placement (aligns to selected edges/paths)

**Data Requirements:**
- `mep/data/ASHRAE_SMACNA_Rectangular.json` — Duct standards

---

### 2.7 MEP Sheet Tools (Comfac)

| ID | Tool | Function | Input | Output |
|----|------|----------|-------|--------|
| MS-01 | CreatePerforatedSheet | Generate perforated sheet metal | Dimensions + pattern | Perforated sheet |
| MS-02 | CreateCorrugatedSheet | Generate corrugated sheet metal | Dimensions + profile | Corrugated sheet |

---

### 2.8 MEP Cable Tools (Comfac)

| ID | Tool | Function | Input | Output |
|----|------|----------|-------|--------|
| MC-01 | CreateWireGutter | Generate wire gutter | Path + dimensions | Wire gutter |
| MC-02 | CreateCableLadderFittings | Generate cable ladder with fittings | Path + dimensions | Cable ladder assembly |
| MC-03 | CreateFiberTray | Generate fiber optic tray | Path + dimensions | Fiber tray |
| MC-04 | CreateDetailedCableTray | Generate organized cable tray | Path | Cable tray + fittings in folders |

---

### 2.9 MEP Extra Tools (Comfac)

| ID | Tool | Function | Input | Output |
|----|------|----------|-------|--------|
| MX-01 | Create_Transition | Create duct/pipe transition reducer | Two sizes + type | Reducer object |
| MX-02 | Merge_Networks | Boolean fuse hollow networks | Selection | Fused network |

---

### 2.10 MEP Utils (Comfac)

| ID | Tool | Function | Input | Output |
|----|------|----------|-------|--------|
| MU-01 | StepImporter | Import STEP files | File dialog | Imported shape |
| MU-02 | ImportFile | Generic file importer | File dialog | Imported object |
| MU-03 | BillOfMaterials | Generate project BOM | Document | Table + CSV export |

**FR-MU-03 BillOfMaterials Detail:**
- Auto-detects: Walls, Ducts, Pipes, Flex Conduits, Fasteners, Couplings, Insulation
- Calculates running lengths from sketches or edge heuristics
- Counts hardware by solids in compounds
- Exports to CSV with headers: Category, Description, Specifications, Qty/Length, Unit

---

## 3. Cross-Cutting Requirements

### 3.1 Standards Compliance
- Pipe data must conform to ASME B36.10M where applicable
- Duct data must conform to ASHRAE (internal clear dims) + SMACNA (shell thickness)
- Electrical conduit data must conform to NEC

### 3.2 Performance
- Live observers must debounce changes (500ms timer)
- Preview updates must not block the UI thread
- Boolean operations on networks >50 segments should use compound fusion, not iterative fuse

### 3.3 UX Requirements
- All generation tools must show a live preview before confirmation
- Invalid inputs must show blocking error dialogs with actionable fix instructions
- Task panels must use consistent layout (form layout with labeled rows)
- Colors must be material-aware (PVC blue/orange, copper, galvanized grey)

### 3.4 Data Persistence
- Standard dimensions must live in external files (JSON or CSV)
- User preferences (default pipe type, default duct gauge) should persist via FreeCAD preferences
- No hardcoded dimensions in geometry logic
