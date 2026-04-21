# ComfacTools v1: Optimization and Bug Report

This report outlines potential bugs, performance bottlenecks, and architectural improvements for the ComfacTools FreeCAD Workbench.

---

## 1. Possible Bugs & Stability Issues

### 1.1 Fragile Icon Paths
**Issue:** Many scripts (e.g., `CreateNetworkPipe.py`, `CreateDuctFittings.py`) use relative paths for icons:  
`'Pixmap': '../Mod/ComfacTools/Resources/icons/Pipes_Network.svg'`
**Risk:** If the workbench folder is renamed (e.g., from `ComfacTools v1` to `ComfacTools`), all icons will fail to load.
**Recommendation:** Use `FreeCAD.getResourceDir()` or calculate the path relative to the current file using `os.path.dirname(__file__)`.

### 1.2 Object Naming Collisions
**Issue:** In `CreateNewPartBody.py`, the code hardcodes the name `'Body'`:
```python
App.activeDocument().addObject('PartDesign::Body','Body')
App.ActiveDocument.getObject('Body').Label = 'Body'
```
**Risk:** If a "Body" already exists, FreeCAD will name the new one "Body001", but `getObject('Body')` will return the *old* one.
**Recommendation:** Always use the object returned by `addObject()`:
```python
new_body = doc.addObject('PartDesign::Body', 'Body')
new_body.Label = 'My Custom Label'
```

### 1.3 Vector Math Singularity (Gimbal Lock)
**Issue:** Geometry creation scripts calculate a local coordinate system using:
`X_new = Y_new.cross(Z_new).normalize()`
**Risk:** If the sketch normal (`Y_new`) is parallel to the edge tangent (`Z_new`), the cross product results in a zero-length vector, causing the script to crash or produce invalid geometry.
**Recommendation:** Implement a robust "look-at" or "arbitrary axis" algorithm (already partially present in `CreateDuctFittings.py` but missing in others like `CreateWall.py`).

### 1.4 Hardcoded Pipe Data
**Issue:** Thousands of lines of pipe dimension data are hardcoded inside `CreateNetworkPipe.py`.
**Risk:** Updating standards or adding new sizes requires modifying the logic code, which is error-prone.
**Recommendation:** Move all dimensional data to an external `JSON` or `CSV` file.

---

## 2. Performance Optimizations

### 2.1 Startup Latency (Critical)
**Issue:** `InitGui.py` imports every single tool module at the top level.
**Impact:** FreeCAD must load and parse every script in the workbench during startup, even if the user never uses them.
**Optimization:** Use "Lazy Loading". Only import the modules inside the `Activated` method of each command class.

### 2.2 Inefficient Boolean Operations
**Issue:** Scripts typically fuse shapes in a loop:
```python
master_shape = shapes[0]
for shape in shapes[1:]:
    master_shape = master_shape.fuse(shape)
```
**Impact:** This is $O(n^2)$ complexity. For a network with 50 segments, this is extremely slow.
**Optimization:** Collect all shapes into a list and use a single compound fusion:
```python
compound = Part.makeCompound(shapes)
fused = compound.fuse() # Or use Part.BOPTools for more complex cases
```

### 2.3 Overuse of "Refine"
**Issue:** `obj.Refine = True` is forced on all generated geometry.
**Impact:** While it cleans up lines, "Refine" is very computationally expensive for complex networks and can sometimes cause the geometry engine to hang.
**Optimization:** Make "Refine" an optional checkbox in the Task Panel or only trigger it once on the final result.

---

## 3. Architectural Improvements

### 3.1 Code Duplication
**Observation:** `CreateNetworkPipe`, `CreateNetworkDuct`, and `CreateWall` share ~70% of their logic (TaskPanel setup, Sweep logic, PartDesign Body handling).
**Recommendation:** Create a `ComfacUtils.py` module to store shared functions like:
*   `get_active_body()`: Helper to find or create a PartDesign Body.
*   `safe_sweep()`: A robust wrapper for `makePipeShell`.
*   `add_custom_properties()`: Centralized logic for injecting "SketchName", "Width", etc.

### 3.2 Magic Numbers
**Observation:** Tolerances like `0.001` and `0.01` are scattered everywhere.
**Recommendation:** Define these as constants at the top of a utility file to ensure consistency across the workbench.

### 3.3 Undo/Redo Safety
**Observation:** Transactions are opened with `doc.openTransaction()`.
**Recommendation:** Ensure all transactions are wrapped in `try...except...finally` blocks to prevent the document from being left in an "Open Transaction" state if a script crashes, which can corrupt the undo stack.
