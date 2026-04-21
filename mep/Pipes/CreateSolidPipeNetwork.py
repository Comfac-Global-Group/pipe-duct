import FreeCAD as App
import FreeCADGui
import Part
import Import
import math
import json
import os
from compat import QtWidgets, QtCore, QtGui

# Safely import ComfacUtils
try:
    import ComfacUtils
except ImportError:
    ComfacUtils = None

# ==========================================================
# GEOMETRY ENGINE (Headless Math for CFD)
# ==========================================================
class SolidPipeGeometryEngine:
    def build_cfd_geometry(self, sketch, id_val):
        """PURE MATH: Returns the CFD solid domain shape."""
        shapes = []
        valid_edges = [edge for edge in sketch.Shape.Edges if edge.Length > 0.001]

        if not valid_edges: return None

        try:
            for edge in valid_edges:
                start_param = edge.FirstParameter
                start_pt = edge.valueAt(start_param)
                tangent = edge.tangentAt(start_param)
                
                circ = Part.Circle(start_pt, tangent, id_val/2.0)
                prof = Part.Wire([circ.toShape()])
                sweep = Part.Wire([edge]).makePipeShell([prof], True, True)
                shapes.append(sweep)

            endpoints = []
            for edge in valid_edges:
                endpoints.append(edge.Vertexes[0].Point)
                endpoints.append(edge.Vertexes[-1].Point)

            intersection_points = []
            for pt in endpoints:
                count = sum(1 for p in endpoints if pt.isEqual(p, 0.001))
                if count > 1 and not any(pt.isEqual(ipt, 0.001) for ipt in intersection_points):
                    intersection_points.append(pt)

            for pt in intersection_points:
                shapes.append(Part.makeSphere(id_val/2.0, pt))

            if not shapes: return None

            master_shape = shapes[0]
            for shape in shapes[1:]:
                master_shape = master_shape.fuse(shape)
                
            return master_shape.removeSplitter()
        except Exception as e:
            App.Console.PrintError(f"CFD Build Error: {e}\n")
            return None


# ==========================================
# LIVE BACKGROUND OBSERVER (CFD PIPES)
# ==========================================
class SolidPipeLiveObserver:
    def __init__(self):
        self.pending_rebuilds = set()
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        # Wired to the check function to handle hiding the model while sketching
        self.timer.timeout.connect(self.check_and_process_rebuilds)
        self.is_generating = False
        self.last_error = ""

    def trigger_rebuild_manually(self, cfd_obj):
        self.pending_rebuilds.add(cfd_obj)
        self.process_rebuilds()

    def slotChangedObject(self, obj, prop):
        if self.is_generating: return
        needs_rebuild = False
        
        if obj.isDerivedFrom("Sketcher::SketchObject") and prop in ["Shape", "Placement"]:
            if obj.Document:
                for doc_obj in obj.Document.Objects:
                    # STRICT FINGERPRINT CHECK: Only target objects that are actually CFD Pipes!
                    # This prevents the script from crashing when editing Cable Tray folders.
                    if hasattr(doc_obj, "LinkedSketch") and getattr(doc_obj, "LinkedSketch", None) == obj:
                        if hasattr(doc_obj, "CFD_OuterDiameter"):
                            self.pending_rebuilds.add(doc_obj)
                            needs_rebuild = True

        # STRICT FINGERPRINT CHECK
        if hasattr(obj, "CFD_OuterDiameter") and prop in ["CFD_OuterDiameter", "CFD_WallThickness", "LinkedSketch"]:
            self.pending_rebuilds.add(obj)
            needs_rebuild = True
                
        if needs_rebuild:
            self.timer.start(500)

    def check_and_process_rebuilds(self):
        valid_objs = [o for o in self.pending_rebuilds if o.Document]
        if not valid_objs:
            self.pending_rebuilds.clear()
            return

        # Hide models while user is actively drawing lines in the sketch
        in_edit_mode = False
        if FreeCADGui.ActiveDocument and FreeCADGui.ActiveDocument.getInEdit():
            in_edit_mode = True

        if in_edit_mode:
            for obj in valid_objs:
                if hasattr(obj, "ViewObject") and obj.ViewObject:
                    obj.ViewObject.Visibility = False
            self.timer.start(1000)
            return

        for obj in valid_objs:
            if hasattr(obj, "ViewObject") and obj.ViewObject:
                obj.ViewObject.Visibility = True

        self.pending_rebuilds = set(valid_objs)
        self.process_rebuilds()

    def process_rebuilds(self):
        self.is_generating = True
        
        # New Progress Loading Dialog for consistency with your other tools
        progress = QtWidgets.QProgressDialog("Generating CFD Pipe Domain...\nPlease Wait.", None, 0, 0)
        progress.setWindowTitle("Processing")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            for cfd_obj in list(self.pending_rebuilds):
                if cfd_obj.Document: 
                    self.rebuild_cfd(cfd_obj)
        except Exception as e:
            App.Console.PrintError(f"CFD Pipe Observer Error: {str(e)}\n")
        finally:
            progress.close()
            self.pending_rebuilds.clear()
            self.is_generating = False

    def rebuild_cfd(self, cfd_obj):
        # Safety Guard: Ensure this isn't a folder from another script
        if not hasattr(cfd_obj, "CFD_OuterDiameter"): return
        
        doc = cfd_obj.Document
        sketch = getattr(cfd_obj, "LinkedSketch", None)
        if not sketch: return
        
        od_prop = getattr(cfd_obj, "CFD_OuterDiameter", 50.0)
        thick_prop = getattr(cfd_obj, "CFD_WallThickness", 3.0)
        
        od = od_prop.Value if hasattr(od_prop, 'Value') else float(od_prop)
        thick = thick_prop.Value if hasattr(thick_prop, 'Value') else float(thick_prop)
        
        id_val = od - (2 * thick)
        if id_val <= 0:
            error_msg = "Wall thickness is too large for the selected Outer Diameter!"
            if self.last_error != error_msg:
                self.last_error = error_msg
                QtWidgets.QMessageBox.critical(None, "Routing Error", error_msg)
            return

        engine = SolidPipeGeometryEngine()
        final_shape = engine.build_cfd_geometry(sketch, id_val)

        if not final_shape: return
        
        self.last_error = "" 

        # Preserves PartDesign Body hierarchy and native colors
        if hasattr(cfd_obj, "BaseFeature") and cfd_obj.BaseFeature:
            cfd_obj.BaseFeature.Shape = final_shape
        else:
            cfd_obj.Shape = final_shape
            
        doc.recompute()

# Global Observer Registration
if not hasattr(App, "GlobalSolidPipeObserver"):
    App.GlobalSolidPipeObserver = SolidPipeLiveObserver()
    App.addDocumentObserver(App.GlobalSolidPipeObserver)


# ==========================================================
# TASK PANEL FOR SOLID CFD PIPES
# ==========================================================
class SolidPipeTaskPanel:
    def __init__(self, sketch):
        self.sketch = sketch
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)
        self.doc = App.ActiveDocument
        
        self.mode_label = QtWidgets.QLabel("<b>Live Auto-Routing Active</b><br>CFD domain will update live on sketch edit.")
        self.layout.addRow(self.mode_label)

        self.preview = None
        if ComfacUtils and hasattr(ComfacUtils, 'PreviewManager'):
            self.preview = ComfacUtils.PreviewManager(self.doc)
            if hasattr(self.preview, 'init'):
                try: self.preview.init(self.doc, "SolidPipe_Preview")
                except TypeError: self.preview.init("SolidPipe_Preview")
        
        json_path = os.path.join(os.path.dirname(__file__), "..", "data", "PipeData.json")
        self.pipe_data = {}
        try:
            with open(json_path, 'r') as f:
                self.pipe_data = json.load(f)
        except:
            pass
        
        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(list(self.pipe_data.keys()) + ["uPVC"])

        self.size_cb = QtWidgets.QComboBox()
        
        self.outer_input = QtWidgets.QDoubleSpinBox()
        self.outer_input.setRange(0.1, 1000.0)
        self.outer_input.setDecimals(2)
        self.outer_input.setSuffix(" mm")
        
        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.1, 500.0)
        self.thick_input.setDecimals(2)
        self.thick_input.setSuffix(" mm")
        
        self.layout.addRow("Pipe Type:", self.type_cb)
        self.layout.addRow("Pipe Size:", self.size_cb)
        self.layout.addRow("Outer Diameter:", self.outer_input)
        self.layout.addRow("Wall Thickness:", self.thick_input)

        self.type_cb.currentTextChanged.connect(self.update_sizes_dropdown)
        self.size_cb.currentTextChanged.connect(self.update_ui)
        self.outer_input.valueChanged.connect(self.trigger_preview)
        self.thick_input.valueChanged.connect(self.trigger_preview)

        self.update_sizes_dropdown(self.type_cb.currentText())
        self.trigger_preview()

    def trigger_preview(self):
        if not self.preview: return
        
        od = self.outer_input.value()
        thick = self.thick_input.value()
        id_val = od - (2 * thick)

        if id_val <= 0:
            if hasattr(self.preview, 'clear'): self.preview.clear()
            return
            
        engine = SolidPipeGeometryEngine()
        ghost_shape = engine.build_cfd_geometry(self.sketch, id_val)
        
        if ghost_shape:
            # Translucent blue strictly for the PREVIEW ONLY
            self.preview.update(ghost_shape, color=(0.4, 0.7, 1.0))

    def update_sizes_dropdown(self, val_type):
        self.size_cb.blockSignals(True)
        self.size_cb.clear()
        if val_type in self.pipe_data:
            self.size_cb.addItems(list(self.pipe_data[val_type].keys()))
        self.size_cb.addItem("Custom")
        self.size_cb.blockSignals(False)
        self.update_ui()

    def update_ui(self):
        val_type = self.type_cb.currentText()
        val_size = self.size_cb.currentText()

        if val_type in self.pipe_data and val_size in self.pipe_data[val_type]:
            od, wt = self.pipe_data[val_type][val_size]
            self.outer_input.setValue(od)
            self.thick_input.setValue(wt)
            self.outer_input.setEnabled(False)
            self.thick_input.setEnabled(False)
        else:
            self.outer_input.setEnabled(True)
            self.thick_input.setEnabled(True)

    def validate_sketch_geometry(self):
        edges = [e for e in self.sketch.Shape.Edges if e.Length > 0.001]
        for edge in edges:
            if hasattr(edge.Curve, "Radius") or "Line" not in edge.Curve.TypeId:
                QtWidgets.QMessageBox.critical(
                    self.form, 
                    "Sketch Error", 
                    "CFD Pipes require sharp, unfilleted corners!\n\n"
                    "The tool automatically bridges corners with spherical joints.\n"
                    "Please use straight lines only."
                )
                return False
        return True
    
    def commit_cfd_domain(self, id_val, od, thick):
        """TREE COMMIT: Adds the final shape to the document, restoring Body context."""
        doc = App.ActiveDocument
        doc.openTransaction("Generate Solid CFD Pipe")
        
        try:
            body = None
            for parent in self.sketch.InList:
                if parent.isDerivedFrom("PartDesign::Body"):
                    body = parent
                    break

            # --- PART DESIGN COMPATIBILITY (PRESERVES NATIVE COLOR) ---
            if body:
                raw_pipe = doc.addObject("Part::Feature", f"{self.sketch.Name}_Raw_CFD")
                raw_pipe.ViewObject.Visibility = False 
                
                obj = body.newObject("PartDesign::FeatureBase", f"{self.sketch.Name}_CFD_Domain")
                obj.BaseFeature = raw_pipe
            else:
                obj = doc.addObject("Part::Feature", f"{self.sketch.Name}_CFD_Domain")
                for parent in self.sketch.InList:
                    if parent.isDerivedFrom("App::Part") or parent.isDerivedFrom("App::DocumentObjectGroup"):
                        parent.addObject(obj)
                        break

            if hasattr(obj, "Refine"):
                obj.Refine = True

            # Hook up Live Parameters
            if not hasattr(obj, "CFD_OuterDiameter"):
                obj.addProperty("App::PropertyLength", "CFD_OuterDiameter", "Live Parameters", "Outer Diameter")
            if not hasattr(obj, "CFD_WallThickness"):
                obj.addProperty("App::PropertyLength", "CFD_WallThickness", "Live Parameters", "Wall Thickness")
            if not hasattr(obj, "LinkedSketch"):
                obj.addProperty("App::PropertyLink", "LinkedSketch", "System Core", "Linked Sketch")
                
            obj.CFD_OuterDiameter = od
            obj.CFD_WallThickness = thick
            obj.LinkedSketch = self.sketch

            self.sketch.ViewObject.hide()
            
            App.GlobalSolidPipeObserver.trigger_rebuild_manually(obj)
            
            doc.recompute()
            doc.commitTransaction()
            
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Error", f"Failed to build CFD Pipe:\n{e}")

    def accept(self):
        if not self.validate_sketch_geometry():
            return False

        od = self.outer_input.value()
        thick = self.thick_input.value()
        id_val = od - (2 * thick)

        if id_val <= 0:
            QtWidgets.QMessageBox.critical(self.form, "Error", "Wall thickness is mathematically impossible.")
            return False

        if self.preview and hasattr(self.preview, 'clear'):
            self.preview.clear()
            
        FreeCADGui.Control.closeDialog()
        self.commit_cfd_domain(id_val, od, thick)
        return True

    def reject(self):
        if self.preview and hasattr(self.preview, 'clear'):
            self.preview.clear()
        FreeCADGui.Control.closeDialog()

class CreateSolidPipeNetwork:
    def GetResources(self):
        icon = ComfacUtils.get_icon_path('Wire_Network.svg') if ComfacUtils else ""
        return {
            'Pixmap': icon, 
            'MenuText': "Generate Solid Pipe (CFD)",
            'ToolTip': "Generates a dynamic solid parametric fluid domain"
        }

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        if not sel or not sel[0].isDerivedFrom("Sketcher::SketchObject"):
            QtWidgets.QMessageBox.warning(None, "Error", "Please select a Sketch path first!")
            return

        # Added instant loading dialog on click
        progress = QtWidgets.QProgressDialog("Launching CFD Tool...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Loading")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            panel = SolidPipeTaskPanel(sel[0])
            FreeCADGui.Control.showDialog(panel)
        finally:
            progress.close()
    
try:
    FreeCADGui.addCommand('Create_Solid_Pipe', CreateSolidPipeNetwork())
except Exception:
    pass