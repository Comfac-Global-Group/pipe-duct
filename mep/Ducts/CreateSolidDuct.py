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
    """Checks if any edge is shorter than min_length AND connects to another edge."""
    for i, target_edge in enumerate(edges):
        if target_edge.Length <= min_length:
            connected = False
            for v in target_edge.Vertexes:
                for j, other_edge in enumerate(edges):
                    if i == j: continue
                    for ov in other_edge.Vertexes:
                        if (v.Point - ov.Point).Length < 0.001:
                            connected = True
                            break
                    if connected: break
                if connected: break
            if connected: return target_edge
    return None

# ==========================================
# GEOMETRY ENGINE (SOLID CFD DUCTS)
# ==========================================
class SolidDuctGeom:
    @staticmethod
    def build_solid_geometry(sketch, w, d, rad, profile_type, corner_type, alignment):
        """PURE MATH: Returns a solid swept duct without inner voids."""
        try:
            sketch_normal = sketch.Placement.Rotation.multVec(App.Vector(0, 0, 1))
            calc_inner_rad = d * 0.5
            all_solid_shells = []

            edges = [e for e in sketch.Shape.Edges if e.Length > 0.001]
            junctions = DuctGeometryUtils.get_junction_points(edges)
            simple_paths = DuctGeometryUtils.build_simple_paths(edges, junctions)

            offset_val = 0.0
            if alignment == "Inner": offset_val = -(w / 2.0)
            elif alignment == "Outer": offset_val = (w / 2.0)

            for path_edges in simple_paths:
                if corner_type == "Rounded":
                    process_edges = DuctGeometryUtils.fillet_wire_path(path_edges, sketch_normal, w, offset_val, calc_inner_rad)
                else: 
                    process_edges = path_edges

                if not process_edges: continue
                
                # --- FIXED: Solid Duct specific extension math ---
                if len(process_edges) == 1:
                    e = process_edges[0]
                    if hasattr(e.Curve, 'TypeId') and 'GeomLine' in e.Curve.TypeId:
                        v_pts = [v.Point for v in e.Vertexes]
                        p_s = v_pts[0]
                        p_e = v_pts[-1]
                        dir_vec = (p_e - p_s).normalize()
                        new_s = p_s - dir_vec * (w + 10.0) if any(p_s.isEqual(jp, 0.001) for jp in junctions) else p_s
                        new_e = p_e + dir_vec * (w + 10.0) if any(p_e.isEqual(jp, 0.001) for jp in junctions) else p_e
                        process_edges[0] = Part.makeLine(new_s, new_e)
                else:
                    # Safely extend first edge without breaking connection
                    e_first = process_edges[0]
                    if hasattr(e_first.Curve, 'TypeId') and 'GeomLine' in e_first.Curve.TypeId:
                        v_first = [v.Point for v in e_first.Vertexes]
                        e_next = process_edges[1]
                        v_next = [v.Point for v in e_next.Vertexes]
                        
                        shared_pt = next((p1 for p1 in v_first for p2 in v_next if p1.isEqual(p2, 0.001)), None)
                        if shared_pt:
                            free_pt = v_first[0] if v_first[1].isEqual(shared_pt, 0.001) else v_first[1]
                            if any(free_pt.isEqual(jp, 0.001) for jp in junctions):
                                d1 = (shared_pt - free_pt).normalize()
                                process_edges[0] = Part.makeLine(free_pt - d1 * (w + 10.0), shared_pt)
                    
                    # Safely extend last edge without breaking connection
                    e_last = process_edges[-1]
                    if hasattr(e_last.Curve, 'TypeId') and 'GeomLine' in e_last.Curve.TypeId:
                        v_last = [v.Point for v in e_last.Vertexes]
                        e_prev = process_edges[-2]
                        v_prev = [v.Point for v in e_prev.Vertexes]
                        
                        shared_pt_last = next((p1 for p1 in v_last for p2 in v_prev if p1.isEqual(p2, 0.001)), None)
                        if shared_pt_last:
                            free_pt_last = v_last[0] if v_last[1].isEqual(shared_pt_last, 0.001) else v_last[1]
                            if any(free_pt_last.isEqual(jp, 0.001) for jp in junctions):
                                d2 = (free_pt_last - shared_pt_last).normalize()
                                process_edges[-1] = Part.makeLine(shared_pt_last, free_pt_last + d2 * (w + 10.0))
                # ------------------------------------------------

                process_wire = Part.Wire(process_edges)
                has_arcs = any(hasattr(e.Curve, 'TypeId') and 'GeomCircle' in e.Curve.TypeId for e in process_edges)
                t_mode = 2 if has_arcs else 1
                
                first_edge = process_wire.OrderedEdges[0]
                start_pt = first_edge.valueAt(first_edge.FirstParameter)
                tangent = first_edge.tangentAt(first_edge.FirstParameter).normalize()
                
                X_dir = sketch_normal.cross(tangent).normalize()
                shifted_start_pt = start_pt + (X_dir * offset_val)

                prof = DuctGeometryUtils.create_profile(w, d, rad, shifted_start_pt, tangent, sketch_normal, profile_type)
                
                try:
                    sweep_solid = process_wire.makePipeShell([prof], True, True, t_mode)
                    if not sweep_solid.isNull(): all_solid_shells.append(sweep_solid)
                except Exception as inner_e:
                    App.Console.PrintError(f"PipeShell Error: {str(inner_e)}\n")

            if not all_solid_shells: return None
            return DuctGeometryUtils.fuse_shapes(all_solid_shells)
            
        except Exception as e:
            App.Console.PrintError(f"SolidGeom Error: {str(e)}\n")
            return None

# ==========================================
# LIVE BACKGROUND OBSERVER
# ==========================================
class SolidDuctLiveObserver:
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
                    if doc_obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(doc_obj, "LinkedSolidSketchName"):
                        if doc_obj.LinkedSolidSketchName == obj.Name:
                            self.pending_rebuilds.add(doc_obj)
                            needs_rebuild = True

        if obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(obj, "LinkedSolidSketchName"):
            if prop in ["SolidWidth", "SolidDepth", "SolidRadius", "SolidProfileType", "SolidCornerType", "SolidAlignment"]:
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
        sketch_name = getattr(group, "LinkedSolidSketchName", "")
        sketch = doc.getObject(sketch_name) if sketch_name else None
        if not sketch: return
        
        w_prop = getattr(group, "SolidWidth", 100.0)
        d_prop = getattr(group, "SolidDepth", 100.0)
        r_prop = getattr(group, "SolidRadius", 15.0)
        
        w = w_prop.Value if hasattr(w_prop, 'Value') else float(w_prop)
        d = d_prop.Value if hasattr(d_prop, 'Value') else float(d_prop)
        rad = r_prop.Value if hasattr(r_prop, 'Value') else float(r_prop)
        
        prof_type = group.getPropertyByName("SolidProfileType") if hasattr(group, "SolidProfileType") else "Rectangular"
        corn_type = group.getPropertyByName("SolidCornerType") if hasattr(group, "SolidCornerType") else "Rounded"
        align = group.getPropertyByName("SolidAlignment") if hasattr(group, "SolidAlignment") else "Center"

        # PROGRESS DIALOG
        progress = QtWidgets.QProgressDialog("Calculating Solid CFD Geometry...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Generating 3D Domain")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            edges = [e for e in sketch.Shape.Edges if e.Length > 0.001]
            invalid_edge = get_invalid_short_edge(edges, 250.0)
            if invalid_edge:
                raise ValueError(f"Sketch has a line of {invalid_edge.Length:.2f} mm. Intersecting lines must be > 250mm.")

            final_shape = SolidDuctGeom.build_solid_geometry(sketch, w, d, rad, prof_type, corn_type, align)
            
            if not final_shape:
                raise ValueError("Failed to process network. Check sketch for invalid continuous loops.")

            # Purge old geometry
            for child in group.Group:
                if child != sketch and child.Name.startswith("CFD_Domain_"):
                    doc.removeObject(child.Name)

            # Generate new Geometry (Removed transparency entirely)
            obj = doc.addObject("Part::Feature", "CFD_Domain_Network")
            obj.Shape = final_shape
            if hasattr(obj, "ViewObject") and obj.ViewObject: 
                obj.ViewObject.ShapeColor = (0.3, 0.3, 0.3) # Solid Dark Grey CFD Domain
            group.addObject(obj)

            doc.recompute()
            
        except ValueError as ve:
            error_msg = str(ve)
            for child in group.Group:
                if child != sketch and child.Name.startswith("CFD_Domain_"):
                    doc.removeObject(child.Name)
            doc.recompute()
            App.Console.PrintError(f"\n[SOLID DUCT ERROR] {error_msg}\n")
            QtWidgets.QMessageBox.critical(None, "Routing Error", error_msg)
            
        finally:
            progress.close()

if not hasattr(App, "GlobalSolidDuctObserver"):
    App.GlobalSolidDuctObserver = SolidDuctLiveObserver()
    App.addDocumentObserver(App.GlobalSolidDuctObserver)

# ==========================================
# UI CONTROLLER
# ==========================================
class SolidDuctTaskPanel:
    def __init__(self, sketch):
        self.sketch = sketch
        self.doc = App.ActiveDocument
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.preview = ComfacUtils.PreviewManager(self.doc, "SolidDuct_Preview") if 'ComfacUtils' in globals() else None
        
        self.mode_label = QtWidgets.QLabel("<b>Live Folder Mode Active</b><br>CFD Domain will adapt to Sketch changes.")
        self.layout.addRow(self.mode_label)
        
        self.shape_combo = QtWidgets.QComboBox()
        self.shape_combo.addItems(["Rectangular", "Rounded Rectangular", "Round"])
        
        self.corner_combo = QtWidgets.QComboBox()
        self.corner_combo.addItems(["Rounded", "Mitered"])
        
        self.align_combo = QtWidgets.QComboBox()
        self.align_combo.addItems(["Center", "Inner", "Outer"])
        
        self.w_input = QtWidgets.QDoubleSpinBox()
        self.w_input.setMinimum(100.0); self.w_input.setMaximum(5000.0)
        self.w_input.setSingleStep(50.0); self.w_input.setValue(100.0)
        self.w_input.setDecimals(2); self.w_input.setSuffix(" mm")
        
        self.d_input = QtWidgets.QDoubleSpinBox()
        self.d_input.setMinimum(100.0); self.d_input.setMaximum(5000.0)
        self.d_input.setSingleStep(50.0); self.d_input.setValue(100.0)
        self.d_input.setDecimals(2); self.d_input.setSuffix(" mm")
        
        self.rad_input = QtWidgets.QDoubleSpinBox()
        self.rad_input.setRange(0.0, 1000.0); self.rad_input.setValue(15.0)
        self.rad_input.setDecimals(2); self.rad_input.setSuffix(" mm")
        
        self.inner_rad_label = QtWidgets.QLabel()
        self.outer_rad_label = QtWidgets.QLabel()
        
        self.layout.addRow("Fluid Profile Type:", self.shape_combo)
        self.layout.addRow("Corner Elbow Type:", self.corner_combo)
        self.layout.addRow("Extrusion Alignment:", self.align_combo)
        self.layout.addRow("Fluid Width (or Dia):", self.w_input)
        self.layout.addRow("Fluid Depth (Height):", self.d_input)
        self.layout.addRow("Profile Corner Rad:", self.rad_input)
        self.layout.addRow("Calculated Inner Bend:", self.inner_rad_label)
        self.layout.addRow("Calculated Outer Bend:", self.outer_rad_label)

        self.d_input.valueChanged.connect(self.update_radii)
        self.shape_combo.currentTextChanged.connect(self.update_ui_state)
        self.w_input.valueChanged.connect(self.trigger_preview)
        self.d_input.valueChanged.connect(self.trigger_preview)
        self.rad_input.valueChanged.connect(self.trigger_preview)
        self.shape_combo.currentIndexChanged.connect(self.trigger_preview)
        self.corner_combo.currentIndexChanged.connect(self.trigger_preview)
        self.align_combo.currentIndexChanged.connect(self.trigger_preview)

        self.update_radii()
        self.update_ui_state()
        self.trigger_preview()

    def update_radii(self):
        d = self.d_input.value()
        self.inner_rad_label.setText(f"<span style='color: gray; font-weight: bold;'>{d * 0.5:.2f} mm</span>")
        self.outer_rad_label.setText(f"<span style='color: gray; font-weight: bold;'>{d * 2.0:.2f} mm</span>")
        self.trigger_preview()

    def update_ui_state(self):
        shape = self.shape_combo.currentText()
        if shape == "Rounded Rectangular": self.rad_input.setEnabled(True)
        else: self.rad_input.setEnabled(False)
        self.trigger_preview()

    def trigger_preview(self):
        if not self.preview: return
        try:
            edges = [e for e in self.sketch.Shape.Edges if e.Length > 0.001]
            if get_invalid_short_edge(edges, 250.0):
                self.preview.clear()
                return

            w = self.w_input.value()
            d = self.d_input.value()
            rad = self.rad_input.value()
            profile_type = self.shape_combo.currentText()
            corner_type = self.corner_combo.currentText()
            alignment = self.align_combo.currentText()
            
            ghost_shape = SolidDuctGeom.build_solid_geometry(self.sketch, w, d, rad, profile_type, corner_type, alignment)
            if ghost_shape:
                self.preview.update(ghost_shape, color=(0.4, 0.7, 1.0)) # Fluid Blue Preview
        except: pass

    def accept(self):
        edges = [e for e in self.sketch.Shape.Edges if e.Length > 0.001]
        invalid_edge = get_invalid_short_edge(edges, 250.0)
        
        if invalid_edge:
            QtWidgets.QMessageBox.critical(
                None, 
                "Dimension Error", 
                f"Cannot generate CFD Domain!\n\nYour sketch contains a connected line that is {invalid_edge.Length:.2f} mm.\nLines forming elbows, tees, or crosses must be strictly longer than 250 mm to allow room for fluid bends."
            )
            return False

        profile_type = self.shape_combo.currentText()
        corner_type = self.corner_combo.currentText()
        alignment = self.align_combo.currentText()

        w = self.w_input.value()
        d = self.d_input.value()
        rad = self.rad_input.value()

        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()
        
        self.setup_smart_folder(w, d, rad, profile_type, corner_type, alignment)
        return True

    def reject(self):
        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()
        return True

    def setup_smart_folder(self, w, d, rad, profile_type, corner_type, alignment):
        doc = App.ActiveDocument
        folder_name = f"{self.sketch.Name}_SolidCFDSystem"
        group = doc.getObject(folder_name)
        
        if not group:
            group = doc.addObject("App::DocumentObjectGroup", folder_name)
            
        if not hasattr(group, "SolidWidth"): group.addProperty("App::PropertyLength", "SolidWidth", "Live Parameters", "Fluid Width")
        if not hasattr(group, "SolidDepth"): group.addProperty("App::PropertyLength", "SolidDepth", "Live Parameters", "Fluid Depth")
        if not hasattr(group, "SolidRadius"): group.addProperty("App::PropertyLength", "SolidRadius", "Live Parameters", "Corner Radius")
        if not hasattr(group, "LinkedSolidSketchName"): group.addProperty("App::PropertyString", "LinkedSolidSketchName", "System Core", "Linked Sketch")

        if not hasattr(group, "SolidProfileType"):
            group.addProperty("App::PropertyEnumeration", "SolidProfileType", "Live Parameters", "Profile Type")
            group.SolidProfileType = ["Rectangular", "Rounded Rectangular", "Round"]
            
        if not hasattr(group, "SolidCornerType"):
            group.addProperty("App::PropertyEnumeration", "SolidCornerType", "Live Parameters", "Corner Type")
            group.SolidCornerType = ["Rounded", "Mitered"]
            
        if not hasattr(group, "SolidAlignment"):
            group.addProperty("App::PropertyEnumeration", "SolidAlignment", "Live Parameters", "Extrusion Alignment")
            group.SolidAlignment = ["Center", "Inner", "Outer"]

        group.SolidWidth = w
        group.SolidDepth = d
        group.SolidRadius = rad
        group.LinkedSolidSketchName = self.sketch.Name
        group.SolidProfileType = profile_type
        group.SolidCornerType = corner_type
        group.SolidAlignment = alignment
        
        App.GlobalSolidDuctObserver.trigger_rebuild_manually(group)

# ==========================================
# COMMAND REGISTRATION
# ==========================================
class CreateSolidDuctNetwork:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('Solid_Duct.svg') if 'ComfacUtils' in globals() else "", 
            'MenuText': "Generate Solid Duct (CFD)",
            'ToolTip': "Generates a live parametric fluid domain"
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
                f"Cannot generate domain.\n\nThe sketch contains a connected line segment measuring {invalid_edge.Length:.2f} mm.\nLines must be strictly greater than 250 mm to allow room for fluid bends."
            )
            return

        progress = QtWidgets.QProgressDialog("Launching Smart CFD Tool...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Loading")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            panel = SolidDuctTaskPanel(sketch)
            FreeCADGui.Control.showDialog(panel)
        finally:
            progress.close()

try:
    FreeCADGui.addCommand('Create_Solid_Duct', CreateSolidDuctNetwork())
except Exception:
    pass