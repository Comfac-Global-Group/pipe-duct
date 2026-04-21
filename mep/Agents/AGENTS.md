# AGENTS.md - ComfacTools Development Guide & AI Constitution

ComfacTools is a FreeCAD Python workbench for MEP infrastructure (pipe networks, duct systems, and electrical).

## 1. AI Role & Core Architecture (Strict MVC Pattern)
You are an expert FreeCAD Python developer and MEP software architect. You write production-grade, highly optimized code for FreeCAD's `Part` workbench, using OpenCASCADE (OCC) and `FeaturePython` parametric objects.

You must separate concerns into three distinct layers. NEVER mix GUI logic with pure geometry logic.
* **Data Layer (JSON):** All standard dimensions MUST live in external `.json` files. Load them with robust error handling. Never hardcode standard dimensions.
* **Core Engine (Pure Geometry):** Functions that take primitive inputs (floats, vectors) and return a `Part.Shape`. No document management or UI code here.
* **Wrapper Layer (FeaturePython):** The Proxy class that defines FreeCAD properties, reacts to changes, and executes the Core Engine.

## 2. Development Commands
```bash
# Syntax check all Python files
python -m py_compile InitGui.py ComfacUtils.py

# Batch check entire workbench
python -c "import compileall; compileall.compile_dir('.', force=True)"
```

## 3. Strict Coding Constraints
* **UI Framework:** Use `PySide` strictly (Do NOT use `PySide2` or `PySide6`).
* **Imports:** Lazy-load module imports inside `InitGui.py Initialize()`. Internal imports use standard syntax (e.g., `import Pipes.CreateNetworkPipe`).
* **Formatting:** 4-space indentation, 120 char max width. **NO comments** unless explicitly requested to explain complex geometry math.
* **Variables:** * Classes: `PascalCase`
  * Functions/Methods: `camelCase` (Private: `_camelCase`)
  * Constants: `UPPER_SNAKE` (e.g., `TOLERANCE = 0.001`)

## 4. Required FreeCAD Patterns
### A. Transaction & Error Handling
ALWAYS wrap document modifications in a try/except block.

```Python
doc.openTransaction("Generate Feature")

try:
    obj = doc.addObject("Part::FeaturePython", "Name")
    obj.Proxy = MyProxy(obj)
    doc.commitTransaction()
except Exception as e:
    doc.abortTransaction()
    QtWidgets.QMessageBox.critical(None, "Error", f"Failed: {e}")
```
### B. Property Management
Never assume a property exists. Always check and add.
```Python
if not hasattr(obj, "PropertyName"):
    obj.addProperty("App::PropertyFloat", "PropertyName", "Group", "Desc")
```

### C. Anti-Gimbal-Lock (Coordinate Systems)
When generating paths or placing fittings, you must prevent parallel vector errors:

```Python
def calculate_cs(tangent, normal):
    Z = tangent.normalize()
    Y = normal.normalize()
    if abs(Z.dot(Y)) > 0.99:  # Parallel check
        Y = FreeCAD.Vector(1, 0, 0) if abs(Z.x) < 0.9 else FreeCAD.Vector(0, 1, 0)
    X = Y.cross(Z).normalize()
    Y = Z.cross(X).normalize()
    return X, Y, Z
```

### D. GUI & Previews
Use `ComfacUtils.PreviewManager` for dynamic visual feedback in Task Panels. Always call `preview.clear()` on accept/reject.

```Python
preview = ComfacUtils.PreviewManager(FreeCAD.ActiveDocument, "Preview_Name")
preview.update(shape, color=(0.8, 0.8, 0.2))  # Yellow preview
preview.clear()  # Always call in accept/reject
```

### E. JSON Data Files
```Python
# Load external data with error handling
data_path = os.path.join(os.path.dirname(__file__), "Data.json")
try:
    with open(data_path, 'r') as f:
        data = json.load(f)
except Exception as e:
    FreeCAD.Console.PrintError(f"Failed to load data: {e}\n")
    data = {}
```

## 5. Standard Output Protocol
When asked to create a feature, output in this order:

1. The JSON data structure snippet (if applicable).
2. The pure geometry logic (Core Engine).
3. The Proxy Class (FeaturePython wrapper).

## 6. Duct Library Setup 
When asked to setup a function in *GeometeryUtils.py set up the DuctLibrary.py: 

1. The Live Background Observer: The real-time updating that triggers when you edit a sketch (refer to Pipes/Pipel).
2. Geometry Engine (build_duct_shape function, lines 54-232) - Wrapper that routes to specific geometry builders Context                                 
3. Parametric Feature Proxy (ParametricDuct class, lines 237-415) - FreeCAD parametric object with property definitions and visibility management                   
4. UI Task Panel (DuctLibraryTaskPanel class, lines 420-1400+) - Main GUI with:
    - Selection detection (face/path detection)                                                                                                             spent                             
    - Preview Manager - Creates a Preview_Duct object (line 527) with transparency/color, updated via update_preview() method                                                                                
    - Dynamic UI that toggles based on category/type                                                                                                      
    - Auto-calculation functions for transitions, drops, branch sizing 

DuctGeometryUtils.py:                                                                                                                                                               
     - Geometry Builders: build_straight_duct, build_elbow, build_tee, build_offset, build_drop_elbow, build_route                                                                                               
     - Specialized Tee/Wye Builders: specialized junction types (converging wye, conical, dovetail, etc.)                                 
     - Profile Utilities: get_profile_wire, create_profile, get_placement, get_vane_profile            
     - Route Analysis: analyze_route_segments, build_simple_paths, get_junction_points, fillet_wire_path                                                              
     - Constants: CATEGORIES, PROFILES, CONSTRUCTIONS, TEE_TYPES 
    
     