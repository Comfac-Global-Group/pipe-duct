import FreeCAD as App
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui

try:
    import Ducts.DuctGeometryUtils as DuctGeometryUtils
    import ComfacUtils
except ImportError:
    pass

def get_invalid_short_edge(edges, min_length=250.0):
    """
    Checks if any edge is shorter than min_length AND connects to another edge
    (forming an Elbow, Tee, or Cross). Returns the short edge if invalid, else None.
    """
    for i, target_edge in enumerate(edges):
        if target_edge.Length <= min_length:
            connected = False
            for v in target_edge.Vertexes:
                for j, other_edge in enumerate(edges):
                    if i == j:
                        continue
                    for ov in other_edge.Vertexes:
                        if (v.Point - ov.Point).Length < 0.001:
                            connected = True
                            break
                    if connected:
                        break
                if connected:
                    break
            
            if connected:
                return target_edge
    return None


def add_duct_properties(obj, w, h, thick, radius, profile_type, corner_type, alignment, sketch_name):
    """Add duct properties directly to the generated object for external tool compatibility."""
    # Basic dimensions
    if not hasattr(obj, "DuctWidth"): 
        obj.addProperty("App::PropertyLength", "DuctWidth", "DuctData", "Width")
    obj.DuctWidth = w
    
    if not hasattr(obj, "DuctHeight"): 
        obj.addProperty("App::PropertyLength", "DuctHeight", "DuctData", "Height")
    obj.DuctHeight = h
    
    if not hasattr(obj, "DuctThickness"): 
        obj.addProperty("App::PropertyLength", "DuctThickness", "DuctData", "Wall Thickness")
    obj.DuctThickness = thick
    
    if not hasattr(obj, "DuctRadius"): 
        obj.addProperty("App::PropertyLength", "DuctRadius", "DuctData", "Profile Corner Radius")
    obj.DuctRadius = radius
    
    # Profile and corner types
    if not hasattr(obj, "DuctProfileType"):
        obj.addProperty("App::PropertyEnumeration", "DuctProfileType", "DuctData", "Profile Type")
        obj.DuctProfileType = ["Rectangular", "Rounded Rectangular", "Circular"]
    obj.DuctProfileType = profile_type
    
    if not hasattr(obj, "DuctCornerType"):
        obj.addProperty("App::PropertyEnumeration", "DuctCornerType", "DuctData", "Corner Type")
        obj.DuctCornerType = ["Rounded", "Mitered"]
    obj.DuctCornerType = corner_type
    
    if not hasattr(obj, "DuctAlignment"):
        obj.addProperty("App::PropertyEnumeration", "DuctAlignment", "DuctData", "Extrusion Alignment")
        obj.DuctAlignment = ["Center", "Inner", "Outer"]
    obj.DuctAlignment = alignment
    
    # Link to source sketch
    if not hasattr(obj, "SketchName"):
        obj.addProperty("App::PropertyString", "SketchName", "DuctData", "Source Sketch Name")
    obj.SketchName = sketch_name
    
    if not hasattr(obj, "LinkedDuctSketchName"):
        obj.addProperty("App::PropertyString", "LinkedDuctSketchName", "DuctData", "Linked Sketch Name")
    obj.LinkedDuctSketchName = sketch_name

# ==========================================
# GEOMETRY ENGINE (DUCTS)
# ==========================================
class DuctGeom:
    @staticmethod
    def build_geometry(sketch, out_w, out_h, thick, out_r, profile_type, corner_type, alignment):
        """PURE MATH: Generates the continuous duct boolean shape."""
        try:
            in_w = max(0.1, out_w - (2 * thick))
            in_h = max(0.1, out_h - (2 * thick))
            in_r = max(0.0, out_r - thick)

            sketch_normal = sketch.Placement.Rotation.multVec(App.Vector(0, 0, 1))
            calc_inner_rad = out_h * 0.5
            
            all_outer_shells = []
            all_inner_shells = []

            edges = [e for e in sketch.Shape.Edges if e.Length > 0.001]
            
            # For circular ducts, use cylinder-based geometry
            if profile_type == "Circular":
                return DuctGeom._build_circular_geometry(edges, out_w, in_w, sketch_normal)
            
            junctions = DuctGeometryUtils.get_junction_points(edges)
            simple_paths = DuctGeometryUtils.build_simple_paths(edges, junctions)

            offset_val = 0.0
            if alignment == "Inner": offset_val = -(out_w / 2.0)
            elif alignment == "Outer": offset_val = (out_w / 2.0)

            for path_edges in simple_paths:
                if corner_type == "Rounded":
                    process_edges = DuctGeometryUtils.fillet_wire_path(path_edges, sketch_normal, out_w, offset_val, calc_inner_rad)
                else:
                    process_edges = path_edges

                if not process_edges: continue
                
                process_wire = Part.Wire(process_edges)
                has_arcs = any(hasattr(e.Curve, 'TypeId') and 'GeomCircle' in e.Curve.TypeId for e in process_edges)
                t_mode = 2 if has_arcs else 1
                
                first_edge = process_wire.OrderedEdges[0]
                start_pt = first_edge.valueAt(first_edge.FirstParameter)
                tangent = first_edge.tangentAt(first_edge.FirstParameter).normalize()
                
                X_dir = sketch_normal.cross(tangent).normalize()
                shifted_start_pt = start_pt + (X_dir * offset_val)

                prof_out = DuctGeometryUtils.create_profile(out_w, out_h, out_r, shifted_start_pt, tangent, sketch_normal, profile_type)
                prof_in = DuctGeometryUtils.create_profile(in_w, in_h, in_r, shifted_start_pt, tangent, sketch_normal, profile_type)
                
                try:
                    sweep_out = process_wire.makePipeShell([prof_out], True, True, t_mode)
                    sweep_in = process_wire.makePipeShell([prof_in], True, True, t_mode)
                    if not sweep_out.isNull(): all_outer_shells.append(sweep_out)
                    if not sweep_in.isNull(): all_inner_shells.append(sweep_in)
                except: pass

            if not all_outer_shells: return None

            master_outer = DuctGeometryUtils.fuse_shapes(all_outer_shells)
            master_inner = DuctGeometryUtils.fuse_shapes(all_inner_shells)
                
            return master_outer.cut(master_inner).removeSplitter()
        except: 
            return None
    
    @staticmethod
    def _build_circular_geometry(edges, out_diameter, in_diameter, sketch_normal):
        """Build circular duct geometry using cylinders and spheres at junctions."""
        outer_radius = out_diameter / 2.0
        inner_radius = in_diameter / 2.0
        
        outer_shapes = []
        inner_shapes = []
        
        for edge in edges:
            start_pt = edge.valueAt(edge.FirstParameter)
            end_pt = edge.valueAt(edge.LastParameter)
            tangent = edge.tangentAt(edge.FirstParameter)
            length = edge.Length
            
            # Create outer cylinder (pipe)
            outer_cyl = DuctGeom._create_cylinder(outer_radius, length, start_pt, end_pt)
            if outer_cyl:
                outer_shapes.append(outer_cyl)
            
            # Create inner cylinder (subtractive)
            inner_cyl = DuctGeom._create_cylinder(inner_radius, length, start_pt, end_pt)
            if inner_cyl:
                inner_shapes.append(inner_cyl)
        
        # Add spheres at junctions for smooth outer shell
        endpoints = []
        for edge in edges:
            endpoints.append(edge.Vertexes[0].Point)
            endpoints.append(edge.Vertexes[-1].Point)
        
        intersection_points = []
        for pt in endpoints:
            count = sum(1 for p in endpoints if pt.isEqual(p, 0.001))
            if count > 1 and not any(pt.isEqual(ipt, 0.001) for ipt in intersection_points):
                intersection_points.append(pt)
        
        for pt in intersection_points:
            outer_shapes.append(Part.makeSphere(outer_radius, pt))
            inner_shapes.append(Part.makeSphere(inner_radius, pt))
        
        if not outer_shapes:
            return None
        
        master_outer = DuctGeometryUtils.fuse_shapes(outer_shapes)
        master_inner = DuctGeometryUtils.fuse_shapes(inner_shapes)
        
        if master_outer and master_inner:
            return master_outer.cut(master_inner).removeSplitter()
        return None
    
    @staticmethod
    def _create_cylinder(radius, length, start_pt, end_pt):
        """Create a cylinder aligned with the edge direction."""
        import math
        direction = (end_pt - start_pt).normalize()
        
        # Create cylinder (aligned with Z axis by default)
        cylinder = Part.makeCylinder(radius, length)
        
        # Calculate rotation to align with direction
        Z_axis = App.Vector(0, 0, 1)
        
        if abs(direction.dot(Z_axis)) > 0.999:
            # Already aligned with Z
            if direction.z < 0:
                # Opposite direction, rotate 180 around X
                cylinder.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
            placement = App.Placement(start_pt, App.Rotation())
        else:
            # Calculate rotation axis and angle
            rot_axis = Z_axis.cross(direction)
            rot_angle = math.degrees(Z_axis.getAngle(direction))
            placement = App.Placement(start_pt, App.Rotation(rot_axis, rot_angle))
        
        cylinder.Placement = placement
        return cylinder

# ==========================================
# LIVE BACKGROUND OBSERVER
# ==========================================
class DuctLiveObserver:
    def __init__(self):
        self.pending_rebuilds = set()
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.process_rebuilds)
        self.is_generating = False

    def trigger_rebuild_manually(self, group):
        self.pending_rebuilds.add(group)
        self.process_rebuilds()

    def slotChangedObject(self, obj, prop):
        if self.is_generating: return
        needs_rebuild = False
        
        if obj.isDerivedFrom("Sketcher::SketchObject") and prop in ["Shape", "Placement"]:
            if obj.Document:
                for doc_obj in obj.Document.Objects:
                    if doc_obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(doc_obj, "LinkedDuctSketchName"):
                        if doc_obj.LinkedDuctSketchName == obj.Name:
                            self.pending_rebuilds.add(doc_obj)
                            needs_rebuild = True

        if obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(obj, "LinkedDuctSketchName"):
            if prop in ["DuctWidth", "DuctHeight", "DuctThickness", "DuctRadius", "DuctProfileType", "DuctCornerType", "DuctAlignment"]:
                self.pending_rebuilds.add(obj)
                needs_rebuild = True
                
        if needs_rebuild:
            self.timer.start(500)

    def process_rebuilds(self):
        if FreeCADGui.ActiveDocument and FreeCADGui.ActiveDocument.getInEdit():
            self.timer.start(1000)
            return

        self.is_generating = True
        try:
            for group in list(self.pending_rebuilds):
                if group.Document: 
                    self.rebuild_folder(group)
        finally:
            self.pending_rebuilds.clear()
            self.is_generating = False

    def rebuild_folder(self, group):
        doc = group.Document
        sketch_name = getattr(group, "LinkedDuctSketchName", "")
        sketch = doc.getObject(sketch_name) if sketch_name else None
        if not sketch: return
        
        # Read parameters dynamically
        w_prop = getattr(group, "DuctWidth", 100.0)
        h_prop = getattr(group, "DuctHeight", 100.0)
        t_prop = getattr(group, "DuctThickness", 2.0)
        r_prop = getattr(group, "DuctRadius", 15.0)
        
        w = w_prop.Value if hasattr(w_prop, 'Value') else float(w_prop)
        h = h_prop.Value if hasattr(h_prop, 'Value') else float(h_prop)
        t = t_prop.Value if hasattr(t_prop, 'Value') else float(t_prop)
        r = r_prop.Value if hasattr(r_prop, 'Value') else float(r_prop)
        
        # Extract enum strings securely
        prof_type = group.getPropertyByName("DuctProfileType") if hasattr(group, "DuctProfileType") else "Rectangular"
        corn_type = group.getPropertyByName("DuctCornerType") if hasattr(group, "DuctCornerType") else "Rounded"
        align = group.getPropertyByName("DuctAlignment") if hasattr(group, "DuctAlignment") else "Center"
        
        # --- AUTO-ADJUST PROPERTIES BASED ON PROFILE TYPE ---
        if prof_type == "Rectangular":
            # Rectangular profile: no corner radius
            r = 0.0
        elif prof_type == "Circular":
            # Circular profile: depth = width (diameter), radius handled differently
            r = 0.0
            h = w  # Circular duct: height equals width
        elif prof_type == "Rounded Rectangular":
            # Rounded Rectangular: use the specified radius (already set from r_prop)
            pass  # r already has the value from r_prop
        
        # Ensure radius is valid for the dimensions
        if r > 0:
            r = min(r, (w/2.0) - 0.001, (h/2.0) - 0.001)

        # --- PROGRESS DIALOG TRIGGER ---
        progress = QtWidgets.QProgressDialog("Calculating Duct Geometry...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Generating 3D Models")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        # Start transaction for undo support
        doc.openTransaction("Rebuild Duct Network")

        try:
            edges = [e for e in sketch.Shape.Edges if e.Length > 0.001]
            invalid_edge = get_invalid_short_edge(edges, 250.0)
            if invalid_edge:
                raise ValueError(f"Sketch has a line of {invalid_edge.Length:.2f} mm. Intersecting lines must be > 250mm.")
            
            if t >= w/2.0 or t >= h/2.0:
                raise ValueError("Wall thickness is too large for current Width/Height.")

            final_shape = DuctGeom.build_geometry(sketch, w, h, t, r, prof_type, corn_type, align)
            
            if not final_shape:
                raise ValueError("Failed to process network. Check sketch for invalid continuous loops.")

            # Purge old geometry inside folder
            for child in group.Group:
                if child != sketch and child.Name.startswith("Generated_Duct_"):
                    doc.removeObject(child.Name)

            # Generate new Geometry inside folder
            obj = doc.addObject("Part::Feature", "Generated_Duct_Network")
            obj.Shape = final_shape
            if hasattr(obj, "ViewObject") and obj.ViewObject: 
                obj.ViewObject.ShapeColor = (0.7, 0.7, 0.7) # Industrial Grey color
            group.addObject(obj)
            
            # Store properties on the duct object itself (for external tools like MergeHollowNetworks)
            add_duct_properties(obj, w, h, t, r, prof_type, corn_type, align, sketch.Name)

            doc.recompute()
            doc.commitTransaction()
            
        except ValueError as ve:
            doc.abortTransaction()
            error_msg = str(ve)
            for child in group.Group:
                if child != sketch and child.Name.startswith("Generated_Duct_"):
                    doc.removeObject(child.Name)
            doc.recompute()
            App.Console.PrintError(f"\n[DUCT ROUTING ERROR] {error_msg}\n")
            QtWidgets.QMessageBox.critical(None, "Routing Error", error_msg)
            
        finally:
            progress.close()

# Register global observer
if not hasattr(App, "GlobalDuctObserver"):
    App.GlobalDuctObserver = DuctLiveObserver()
    App.addDocumentObserver(App.GlobalDuctObserver)

# ==========================================
# UI CONTROLLER
# ==========================================
class DuctTaskPanel:
    def __init__(self, sketch):
        self.sketch = sketch
        self.doc = App.ActiveDocument
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.preview = ComfacUtils.PreviewManager(self.doc, "NetworkDuct_Preview") if 'ComfacUtils' in globals() else None
        
        self.mode_label = QtWidgets.QLabel("<b>Live Folder Mode Active</b><br>Will automatically adapt to Sketch changes.")
        self.layout.addRow(self.mode_label)

        self.shape_combo = QtWidgets.QComboBox()
        self.shape_combo.addItems(["Rectangular", "Rounded Rectangular", "Circular"])
        
        self.corner_combo = QtWidgets.QComboBox()
        self.corner_combo.addItems(["Rounded", "Mitered"])
        
        self.align_combo = QtWidgets.QComboBox()
        self.align_combo.addItems(["Center", "Inner", "Outer"])
        
        self.w_input = QtWidgets.QDoubleSpinBox()
        self.w_input.setMinimum(100.0); self.w_input.setMaximum(5000.0)
        self.w_input.setSingleStep(50.0); self.w_input.setValue(100.0)
        self.w_input.setDecimals(2); self.w_input.setSuffix(" mm")
        
        self.h_input = QtWidgets.QDoubleSpinBox()
        self.h_input.setMinimum(100.0); self.h_input.setMaximum(5000.0)
        self.h_input.setSingleStep(50.0); self.h_input.setValue(100.0)
        self.h_input.setDecimals(2); self.h_input.setSuffix(" mm")
        
        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.1, 100.0)
        self.thick_input.setValue(2.0); self.thick_input.setSuffix(" mm")
        
        self.rad_input = QtWidgets.QDoubleSpinBox()
        self.rad_input.setRange(0.0, 1000.0)
        self.rad_input.setValue(15.0); self.rad_input.setSuffix(" mm")
        
        self.inner_rad_label = QtWidgets.QLabel()
        self.outer_rad_label = QtWidgets.QLabel()
        
        self.layout.addRow("Duct Profile Type:", self.shape_combo)
        self.layout.addRow("Corner Elbow Type:", self.corner_combo)
        self.layout.addRow("Extrusion Alignment:", self.align_combo)
        self.layout.addRow("Width (or Dia):", self.w_input)
        self.layout.addRow("Depth (Height):", self.h_input)
        self.layout.addRow("Wall Thickness:", self.thick_input)
        self.layout.addRow("Profile Corner Rad:", self.rad_input)
        self.layout.addRow("Calculated Inner Bend:", self.inner_rad_label)
        self.layout.addRow("Calculated Outer Bend:", self.outer_rad_label)

        self.h_input.valueChanged.connect(self.update_radii)
        self.shape_combo.currentTextChanged.connect(self.update_ui_state)
        self.w_input.valueChanged.connect(self.trigger_preview)
        self.h_input.valueChanged.connect(self.trigger_preview)
        self.thick_input.valueChanged.connect(self.trigger_preview)
        self.rad_input.valueChanged.connect(self.trigger_preview)
        self.shape_combo.currentIndexChanged.connect(self.trigger_preview)
        self.corner_combo.currentIndexChanged.connect(self.trigger_preview)
        self.align_combo.currentIndexChanged.connect(self.trigger_preview)

        self.update_radii()
        self.update_ui_state()
        self.trigger_preview()

    def update_radii(self):
        d = self.h_input.value()
        self.inner_rad_label.setText(f"<span style='color: gray; font-weight: bold;'>{d * 0.5:.2f} mm</span>")
        self.outer_rad_label.setText(f"<span style='color: gray; font-weight: bold;'>{d * 1.5:.2f} mm</span>")

    def update_ui_state(self):
        shape = self.shape_combo.currentText()
        if shape == "Rounded Rectangular":
            self.rad_input.setEnabled(True)
            self.h_input.setEnabled(True)
        elif shape == "Circular":
            self.rad_input.setEnabled(False)
            self.h_input.setEnabled(False)  # Height not used for circular
        else:  # Rectangular
            self.rad_input.setEnabled(False)
            self.h_input.setEnabled(True)

    def trigger_preview(self):
        if not self.preview: return
        
        edges = [e for e in self.sketch.Shape.Edges if e.Length > 0.001]
        if get_invalid_short_edge(edges, 250.0):
            self.preview.clear()
            return

        out_w = self.w_input.value()
        out_h = self.h_input.value()
        thick = self.thick_input.value()
        out_r = self.rad_input.value()
        profile_type = self.shape_combo.currentText()
        corner_type = self.corner_combo.currentText()
        alignment = self.align_combo.currentText()
        
        # Handle circular profile: height equals width
        if profile_type == "Circular":
            out_h = out_w
        
        if thick >= out_w/2.0 or thick >= out_h/2.0:
            self.preview.clear()
            return
            
        ghost_shape = DuctGeom.build_geometry(self.sketch, out_w, out_h, thick, out_r, profile_type, corner_type, alignment)
        if ghost_shape:
            self.preview.update(ghost_shape, color=(0.7, 0.7, 0.7))

    def accept(self):
        edges = [e for e in self.sketch.Shape.Edges if e.Length > 0.001]
        invalid_edge = get_invalid_short_edge(edges, 250.0)
        
        if invalid_edge:
            QtWidgets.QMessageBox.critical(
                None, 
                "Dimension Error", 
                f"Cannot generate duct!\n\nYour sketch contains a connected line that is {invalid_edge.Length:.2f} mm.\nLines forming elbows, tees, or crosses must be strictly longer than 250 mm to allow room for bends."
            )
            return False

        profile_type = self.shape_combo.currentText()
        corner_type = self.corner_combo.currentText()
        alignment = self.align_combo.currentText()

        out_w = self.w_input.value()
        out_h = self.h_input.value()
        thick = self.thick_input.value()
        out_r = self.rad_input.value()
        
        # --- AUTO-ADJUST PROPERTIES BASED ON PROFILE TYPE ---
        if profile_type == "Rectangular":
            out_r = 0.0  # Rectangular: no corner radius
        elif profile_type == "Circular":
            out_r = 0.0  # Circular: radius handled differently
            out_h = out_w  # Circular: depth = width (diameter)
        elif profile_type == "Rounded Rectangular":
            # Rounded Rectangular: use specified radius, but clamp to valid range
            out_r = min(out_r, (out_w/2.0) - 0.001, (out_h/2.0) - 0.001)

        if thick >= out_w/2.0 or thick >= out_h/2.0:
            QtWidgets.QMessageBox.critical(None, "Error", "Wall thickness is too large.")
            return False

        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()
        
        self.setup_smart_folder(out_w, out_h, thick, out_r, profile_type, corner_type, alignment)
        return True

    def reject(self):
        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()
        return True

    def setup_smart_folder(self, out_w, out_h, thick, out_r, profile_type, corner_type, alignment):
        """Creates the Live Parameter Folder inside the FreeCAD Tree."""
        doc = App.ActiveDocument
        folder_name = f"{self.sketch.Name}_DuctSystem"
        group = doc.getObject(folder_name)
        
        # Start transaction for undo support
        doc.openTransaction("Create Duct Network")
        
        try:
            if not group:
                group = doc.addObject("App::DocumentObjectGroup", folder_name)
                
            # Add dynamic properties
            if not hasattr(group, "DuctWidth"): group.addProperty("App::PropertyLength", "DuctWidth", "Live Parameters", "Width")
            if not hasattr(group, "DuctHeight"): group.addProperty("App::PropertyLength", "DuctHeight", "Live Parameters", "Height")
            if not hasattr(group, "DuctThickness"): group.addProperty("App::PropertyLength", "DuctThickness", "Live Parameters", "Wall Thickness")
            if not hasattr(group, "DuctRadius"): group.addProperty("App::PropertyLength", "DuctRadius", "Live Parameters", "Profile Corner Radius")
            if not hasattr(group, "LinkedDuctSketchName"): group.addProperty("App::PropertyString", "LinkedDuctSketchName", "System Core", "Linked Sketch")

            # Add Enumeration dropdowns securely
            if not hasattr(group, "DuctProfileType"):
                group.addProperty("App::PropertyEnumeration", "DuctProfileType", "Live Parameters", "Profile Type")
                group.DuctProfileType = ["Rectangular", "Rounded Rectangular", "Circular"]
                
            if not hasattr(group, "DuctCornerType"):
                group.addProperty("App::PropertyEnumeration", "DuctCornerType", "Live Parameters", "Corner Type")
                group.DuctCornerType = ["Rounded", "Mitered"]
                
            if not hasattr(group, "DuctAlignment"):
                group.addProperty("App::PropertyEnumeration", "DuctAlignment", "Live Parameters", "Extrusion Alignment")
                group.DuctAlignment = ["Center", "Inner", "Outer"]

            # Push the submitted values into the smart folder
            group.DuctWidth = out_w
            group.DuctHeight = out_h
            group.DuctThickness = thick
            group.DuctRadius = out_r
            group.LinkedDuctSketchName = self.sketch.Name
            group.DuctProfileType = profile_type
            group.DuctCornerType = corner_type
            group.DuctAlignment = alignment
            
            # Manually trigger the observer to construct the first geometry
            App.GlobalDuctObserver.trigger_rebuild_manually(group)
            
            # Commit the transaction
            doc.commitTransaction()
            
        except Exception as e:
            doc.abortTransaction()
            App.Console.PrintError(f"Failed to create duct network: {e}\n")
            QtWidgets.QMessageBox.critical(None, "Error", f"Failed to create duct network:\n{e}")

# ==========================================
# FREECAD COMMAND INITIATION
# ==========================================
class CreateNetworkDuct:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('Ducts.svg') if 'ComfacUtils' in globals() else "", 
            'MenuText': "Generate Smart Duct Network",
            'ToolTip': "Generates parametric ducts that adapt to Sketch changes automatically"
        }

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        if not sel or not sel[0].isDerivedFrom("Sketcher::SketchObject"):
            QtWidgets.QMessageBox.warning(None, "Error", "Please select a 2D Sketch path first!")
            return

        sketch = sel[0]
        edges = [e for e in sketch.Shape.Edges if e.Length > 0.001]
        invalid_edge = get_invalid_short_edge(edges, 250.0)
        
        if invalid_edge:
            QtWidgets.QMessageBox.critical(
                None, 
                "Dimension Error", 
                f"Cannot generate duct.\n\nThe sketch contains a connected line segment measuring {invalid_edge.Length:.2f} mm.\nLines that connect to form junctions (Elbows, Tees, Crosses) must be strictly greater than 250 mm to allow room for bends."
            )
            return

        # Progress UI
        progress = QtWidgets.QProgressDialog("Launching Smart Duct Tool...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Loading")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            panel = DuctTaskPanel(sketch)
            FreeCADGui.Control.showDialog(panel)
        finally:
            progress.close()

try:
    FreeCADGui.addCommand('CreateNetworkDuct', CreateNetworkDuct())
except Exception:
    pass