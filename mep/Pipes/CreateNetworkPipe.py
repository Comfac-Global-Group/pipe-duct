import os
import json
import math
import FreeCAD
import FreeCADGui
import Part
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils
import Pipes.CreateNetworkPipeFittings as PFittings

# ==========================================
# GEOMETRY & VALIDATION ENGINE
# ==========================================
class NetworkGeometryEngine:
    @staticmethod
    def build_geometry(sketches, od, id_val):
        try:
            outer_shapes, inner_shapes = [], []
            valid_edges = []
            for obj in sketches:
                valid_edges.extend([edge for edge in obj.Shape.Edges if edge.Length > ComfacUtils.TOLERANCE])

            if not valid_edges:
                return None

            endpoints = []
            for edge in valid_edges:
                try:
                    endpoints.append(edge.Vertexes[0].Point)
                    endpoints.append(edge.Vertexes[-1].Point)
                except:
                    endpoints.append(edge.valueAt(edge.FirstParameter))
                    endpoints.append(edge.valueAt(edge.LastParameter))

            intersection_points = []
            MATCH_TOLERANCE = 0.5

            for pt in endpoints:
                already_found = False
                for ipt in intersection_points:
                    if (pt - ipt).Length < MATCH_TOLERANCE:
                        already_found = True
                        break

                if not already_found:
                    count = sum(1 for p in endpoints if (pt - p).Length < MATCH_TOLERANCE)
                    if count > 1:
                        intersection_points.append(pt)

            for edge in valid_edges:
                start_pt = edge.valueAt(edge.FirstParameter)
                tangent = edge.tangentAt(edge.FirstParameter)
                circ_out = Part.Circle(start_pt, tangent, od/2.0).toShape()
                outer_shapes.append(Part.Wire([edge]).makePipeShell([Part.Wire([circ_out])], True, True))
                circ_in = Part.Circle(start_pt, tangent, id_val/2.0).toShape()
                inner_shapes.append(Part.Wire([edge]).makePipeShell([Part.Wire([circ_in])], True, True))

            for pt in intersection_points:
                # Safely ensure od and id_val are floats to prevent Base.Quantity errors
                float_od = od.Value if hasattr(od, 'Value') else float(od)
                float_id = id_val.Value if hasattr(id_val, 'Value') else float(id_val)
                
                outer_shapes.append(Part.makeSphere(float_od/2.0, pt))
                inner_shapes.append(Part.makeSphere(float_id/2.0, pt))

            if not outer_shapes: return None

            master_outer = ComfacUtils.fuse_shapes(outer_shapes)
            master_inner = ComfacUtils.fuse_shapes(inner_shapes)

            if not master_outer or not master_inner: return None

            return master_outer.cut(master_inner).removeSplitter()
        except Exception as e:
            FreeCAD.Console.PrintError(f"Geometry build failed: {e}\n")
            return None

    @staticmethod
    def validate_angles(sketches, show_msg=True):
        """Scans sketch line intersections and blocks impossible 3D angles."""
        edges = []
        for obj in sketches:
            edges.extend([e for e in obj.Shape.Edges if e.Length > ComfacUtils.TOLERANCE])
        
        lines = []
        for e in edges:
            try:
                p1 = e.Vertexes[0].Point
                p2 = e.Vertexes[-1].Point
            except:
                p1 = e.valueAt(e.FirstParameter)
                p2 = e.valueAt(e.LastParameter)
            lines.append((p1, p2))
            
        MATCH_TOLERANCE = 0.5
        vertices = {}
        for p1, p2 in lines:
            found_k1, found_k2 = None, None
            for k in vertices.keys():
                pt = FreeCAD.Vector(k[0], k[1], k[2])
                if (pt - p1).Length < MATCH_TOLERANCE: found_k1 = k
                if (pt - p2).Length < MATCH_TOLERANCE: found_k2 = k
            
            k1 = found_k1 if found_k1 else (round(p1.x, 2), round(p1.y, 2), round(p1.z, 2))
            k2 = found_k2 if found_k2 else (round(p2.x, 2), round(p2.y, 2), round(p2.z, 2))
            
            if k1 not in vertices: vertices[k1] = []
            if k2 not in vertices: vertices[k2] = []
            
            try:
                vertices[k1].append((FreeCAD.Vector(p2.x - p1.x, p2.y - p1.y, p2.z - p1.z).normalize()))
                vertices[k2].append((FreeCAD.Vector(p1.x - p2.x, p1.y - p2.y, p1.z - p2.z).normalize()))
            except Exception:
                continue
            
        for k, vectors in vertices.items():
            if len(vectors) == 2:
                v1, v2 = vectors[0], vectors[1]
                dot = max(-1.0, min(1.0, v1.dot(v2)))
                angle_deg = math.degrees(math.acos(dot))
                
                if (abs(angle_deg - 180.0) > 5.0 and 
                    abs(angle_deg - 90.0) > 5.0 and 
                    abs(angle_deg - 45.0) > 5.0 and 
                    abs(angle_deg - 135.0) > 5.0):
                    
                    if show_msg:
                        QtWidgets.QMessageBox.critical(
                            None, 
                            "Invalid Sketch Angle", 
                            f"Found an invalid bend angle of {angle_deg:.1f}°.\n\nThe system strictly supports straight lines (180°), 90°, and 45° angles. Please fix your sketch to match standard manufactured pipe fittings."
                        )
                    return False
            elif len(vectors) > 2:
                for i in range(len(vectors)):
                    for j in range(i+1, len(vectors)):
                        v1, v2 = vectors[i], vectors[j]
                        dot = max(-1.0, min(1.0, v1.dot(v2)))
                        angle_deg = math.degrees(math.acos(dot))
                        if (abs(angle_deg - 180.0) > 5.0 and abs(angle_deg - 90.0) > 5.0):
                            if show_msg:
                                QtWidgets.QMessageBox.critical(
                                    None, 
                                    "Invalid Junction", 
                                    f"Found an invalid intersection angle of {angle_deg:.1f}°.\n\nTees and Crosses must connect strictly at 90° or 180°."
                                )
                            return False
        return True

    @staticmethod
    def validate_segment_lengths(sketches, od, show_msg=True):
        min_allowed = od / 2.0 
        for obj in sketches:
            edges = [e for e in obj.Shape.Edges if e.Length > ComfacUtils.TOLERANCE]
            for edge in edges:
                if edge.Length < min_allowed:
                    if show_msg:
                        QtWidgets.QMessageBox.critical(
                            None, 
                            "Sketch Dimension Error", 
                            f"A sketch segment in {obj.Label} is mathematically too short to generate this pipe!\n\n"
                            f"To safely route a pipe with an Outer Diameter of {od} mm, "
                            f"every straight segment must be at least {min_allowed:.1f} mm long.\n"
                            f"Found a segment of only {edge.Length:.1f} mm."
                        )
                    return False
        return True

    @staticmethod
    def validate_sketch_geometry(sketches, show_msg=True):
        for obj in sketches:
            edges = [e for e in obj.Shape.Edges if e.Length > ComfacUtils.TOLERANCE]
            for edge in edges:
                if hasattr(edge.Curve, "Radius") or "Line" not in edge.Curve.TypeId:
                    if show_msg:
                        QtWidgets.QMessageBox.critical(None, "Sketch Error", f"Pipes require sharp corners! Found a curve in {obj.Label}.")
                    return False
        return True


# ==========================================
# LIVE BACKGROUND OBSERVER (NETWORK)
# ==========================================
class NetworkLiveObserver:
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
        
        # If sketch changes, find which folder owns it
        if obj.isDerivedFrom("Sketcher::SketchObject") and prop in ["Shape", "Placement"]:
            if obj.Document:
                for doc_obj in obj.Document.Objects:
                    if doc_obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(doc_obj, "LinkedSketches"):
                        if obj in doc_obj.LinkedSketches:
                            self.pending_rebuilds.add(doc_obj)
                            needs_rebuild = True

        # If user tweaks folder properties manually
        if obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(obj, "LinkedSketches"):
            if prop in ["PipeOuterDiameter", "PipeThickness", "PipeMaterial"]:
                self.pending_rebuilds.add(obj)
                needs_rebuild = True
                
        if needs_rebuild:
            self.timer.start(500)

    def process_rebuilds(self):
        if not self.pending_rebuilds: return
        self.is_generating = True
        try:
            for group in list(self.pending_rebuilds):
                if group.Document:
                    self.rebuild_network_folder(group)
        finally:
            self.pending_rebuilds.clear()
            self.is_generating = False

    def rebuild_network_folder(self, group):
        doc = group.Document
        sketches = getattr(group, "LinkedSketches", [])
        if not sketches: return
        
        # Safely extract floats to avoid Base.Quantity TypeError crash
        od_raw = getattr(group, "PipeOuterDiameter", 0.0)
        od = od_raw.Value if hasattr(od_raw, 'Value') else float(od_raw)
        
        thick_raw = getattr(group, "PipeThickness", 0.0)
        thick = thick_raw.Value if hasattr(thick_raw, 'Value') else float(thick_raw)
        
        id_val = od - (2 * thick)
        if id_val <= 0: return
        
        # Validation checks (Silent in background)
        if not NetworkGeometryEngine.validate_angles(sketches, show_msg=False):
            FreeCAD.Console.PrintWarning("Live Update Paused: Invalid sketch angles detected.\n")
            return
        if not NetworkGeometryEngine.validate_segment_lengths(sketches, od, show_msg=False):
            FreeCAD.Console.PrintWarning("Live Update Paused: Sketch segments too short.\n")
            return
            
        new_shape = NetworkGeometryEngine.build_geometry(sketches, od, id_val)
        if not new_shape: return
        
        # Find the master Network Object
        network_obj = None
        for child in group.Group:
            if child.Name.startswith("Pipe_Network"):
                network_obj = child
                break
        if not network_obj: return
        
        # Update Master Shape
        network_obj.Shape = new_shape
        network_obj.PipeOuter = od
        network_obj.PipeInner = id_val
        doc.recompute()
        
        # Clear out old fittings
        to_remove = [c for c in group.Group if c != network_obj]
        for c in to_remove:
            group.removeObject(c)
            doc.removeObject(c.Name)
            
        # Re-run Auto Fittings
        def run_live_fittings():
            existing_objs = set([o.Name for o in doc.Objects])
            try:
                fittings_panel = PFittings.PipeFittingTaskPanel(network_obj)
                
                # Safe casting to float to avoid Quantity errors in fittings logic
                fit_thick = float(fittings_panel.thick_input.value())
                sock_len = float(fittings_panel.length_input.value())
                
                raw_id = fittings_panel.pipe_od
                fit_id = raw_id.Value if hasattr(raw_id, 'Value') else float(raw_id)
                
                fit_od = fit_id + (2 * fit_thick)
                fittings_panel.generate_fittings(fit_od, fit_id, sock_len)
                
                if hasattr(fittings_panel, 'preview'):
                    fittings_panel.preview.clear()
                    
                # Group new fittings into the folder
                for o in doc.Objects:
                    if o.Name not in existing_objs:
                        if "preview" in o.Name.lower() or "preview" in o.Label.lower():
                            doc.removeObject(o.Name)
                        else:
                            group.addObject(o)
                doc.recompute()
            except Exception as e:
                FreeCAD.Console.PrintWarning(f"Live fittings failed: {e}\n")

        QtCore.QTimer.singleShot(50, run_live_fittings)

# Register Global Observer
if not hasattr(FreeCAD, "GlobalNetworkObserver"):
    FreeCAD.GlobalNetworkObserver = NetworkLiveObserver()
    FreeCAD.addDocumentObserver(FreeCAD.GlobalNetworkObserver)


# ==========================================
# UI TASK PANEL
# ==========================================
class PipeTaskPanel:
    def __init__(self, selected_objs):
        self.selected_objs = selected_objs
        self.primary_obj = selected_objs[0] # Used for container reference
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)
        
        # Load external data
        self.pipe_data = {}
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "PipeData.json")
        try:
            with open(data_path, 'r') as f:
                self.pipe_data = json.load(f)
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to load pipe data: {e}\n")

        # Load colors from external file
        self.colors = {}
        color_path = os.path.join(os.path.dirname(__file__), "..", "data", "PipeColors.json")
        try:
            with open(color_path, 'r') as f:
                self.colors = json.load(f)
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to load pipe colors: {e}\n")

        self.default_colors = self.colors.get("default_colors", {})
        self.default_colors["PVC"] = None  # Uses dropdown
        self.pvc_colors = self.colors.get("pvc_colors", {})

        # --- DYNAMIC WARNING LABEL ---
        self.warning_label = QtWidgets.QLabel("<font color='red'><b>Warning: Invalid angles detected in sketch!<br>Only 45°, 90°, and straight (180°) allowed.</b></font>")
        self.warning_label.setVisible(False)
        self.layout.addRow(self.warning_label)

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(list(self.pipe_data.keys()))

        self.size_cb = QtWidgets.QComboBox()
        
        self.color_cb = QtWidgets.QComboBox()
        
        self.outer_input = QtWidgets.QDoubleSpinBox()
        self.outer_input.setRange(0.1, 2000.0)
        self.outer_input.setDecimals(2)
        self.outer_input.setSuffix(" mm")
        
        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.1, 500.0)
        self.thick_input.setDecimals(2)
        self.thick_input.setSuffix(" mm")
        
        self.layout.addRow("Pipe Type:", self.type_cb)
        self.layout.addRow("Pipe Size:", self.size_cb)
        self.layout.addRow("Color:", self.color_cb)
        self.layout.addRow("Outer Diameter:", self.outer_input)
        self.layout.addRow("Wall Thickness:", self.thick_input)

        self.type_cb.currentTextChanged.connect(self.update_sizes_dropdown)
        self.type_cb.currentTextChanged.connect(self.update_color_options)
        self.size_cb.currentIndexChanged.connect(self.update_ui)

        self.preview = ComfacUtils.PreviewManager(FreeCAD.ActiveDocument, "NetworkPipe_Preview")

        self.outer_input.valueChanged.connect(self.trigger_preview)
        self.thick_input.valueChanged.connect(self.trigger_preview)

        self.update_sizes_dropdown(self.type_cb.currentText())
        self.trigger_preview()

    def trigger_preview(self):
        try:
            # INSTANT BLOCK: Check angles before showing the preview
            is_valid_angles = NetworkGeometryEngine.validate_angles(self.selected_objs, show_msg=False)
            self.warning_label.setVisible(not is_valid_angles)
            
            if not is_valid_angles:
                if self.preview:
                    self.preview.clear()
                return

            od = float(self.outer_input.value())
            thick = float(self.thick_input.value())
            id_val = od - (2 * thick)
            if id_val <= 0:
                return
            ghost_shape = NetworkGeometryEngine.build_geometry(self.selected_objs, od, id_val)
            if ghost_shape:
                self.preview.update(ghost_shape)
        except:
            pass

    def update_sizes_dropdown(self, val_type):
        self.size_cb.blockSignals(True)
        self.size_cb.clear()
        if val_type in self.pipe_data:
            self.size_cb.addItems(list(self.pipe_data[val_type].keys()))
        self.size_cb.addItem("Custom")
        self.size_cb.blockSignals(False)
        self.update_color_options(val_type)
        self.update_ui()

    def update_color_options(self, val_type):
        self.color_cb.blockSignals(True)
        self.color_cb.clear()
        
        is_pvc = "PVC" in val_type
        
        if is_pvc:
            self.color_cb.addItems(list(self.pvc_colors.keys()))
            self.color_cb.setEnabled(True)
        else:
            self.color_cb.setEnabled(False)
        
        self.color_cb.blockSignals(False)

    def update_ui(self):
        val_type = self.type_cb.currentText()
        val_size = self.size_cb.currentText()
        if val_type in self.pipe_data and val_size in self.pipe_data[val_type]:
            od, wt = self.pipe_data[val_type][val_size]
            self.outer_input.setValue(float(od))
            self.thick_input.setValue(float(wt))
            self.outer_input.setEnabled(False)
            self.thick_input.setEnabled(False)
        else:
            self.outer_input.setEnabled(True)
            self.thick_input.setEnabled(True)

    def get_selected_color(self):
        val_type = self.type_cb.currentText()
        
        if "PVC" in val_type:
            color_name = self.color_cb.currentText()
            color = self.pvc_colors.get(color_name, [0.5, 0.5, 0.5])
            return tuple(color) if isinstance(color, list) else color
        
        for key, color in self.default_colors.items():
            if key in val_type and color is not None:
                return tuple(color) if isinstance(color, list) else color
        
        return (0.5, 0.5, 0.5)
    
    def get_pipe_type(self):
        return self.type_cb.currentText()

    def accept(self):
        # Trigger validation with popups when user clicks OK
        if not NetworkGeometryEngine.validate_sketch_geometry(self.selected_objs, show_msg=True): return False
        if not NetworkGeometryEngine.validate_angles(self.selected_objs, show_msg=True): return False 

        od = float(self.outer_input.value())
        if not NetworkGeometryEngine.validate_segment_lengths(self.selected_objs, od): return False

        thick = float(self.thick_input.value())
        id_val = od - (2 * thick)

        if id_val <= 0:
            QtWidgets.QMessageBox.critical(None, "Error", "Wall thickness is too large.")
            return False

        pipe_color = self.get_selected_color()
        pipe_type = self.get_pipe_type()

        self.preview.clear()
        FreeCADGui.Control.closeDialog()

        self.generate_pipes(od, thick, id_val, pipe_color, pipe_type)
        return True

    def reject(self):
        self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def generate_pipes(self, od, thick, id_val, pipe_color, pipe_type):
        try:
            doc = FreeCAD.ActiveDocument
            final_shape = NetworkGeometryEngine.build_geometry(self.selected_objs, od, id_val)
            
            if not final_shape:
                QtWidgets.QMessageBox.warning(None, "Error", "Failed to generate any 3D shapes.")
                return

            doc.openTransaction("Generate Pipe Network")
            try:
                # --- CREATE SMART FOLDER ---
                folder_name = f"{pipe_type.replace(' ', '_').replace('&', 'and')}_Network"
                group = doc.getObject(folder_name)
                if not group: 
                    group = doc.addObject("App::DocumentObjectGroup", folder_name)
                
                # Setup live properties
                if not hasattr(group, "LinkedSketches"):
                    group.addProperty("App::PropertyLinkListGlobal", "LinkedSketches", "System Core", "Linked Sketches")
                group.LinkedSketches = self.selected_objs
                
                if not hasattr(group, "PipeOuterDiameter"):
                    group.addProperty("App::PropertyLength", "PipeOuterDiameter", "Live Parameters", "Pipe OD")
                if not hasattr(group, "PipeThickness"):
                    group.addProperty("App::PropertyLength", "PipeThickness", "Live Parameters", "Wall Thickness")
                if not hasattr(group, "PipeMaterial"):
                    group.addProperty("App::PropertyEnumeration", "PipeMaterial", "Live Parameters", "Pipe Material")
                    
                # --- FIX: Stop CreatePipeLibraries Observer from Crashing ---
                if not hasattr(group, "NominalSize"):
                    group.addProperty("App::PropertyEnumeration", "NominalSize", "Live Parameters", "Nominal Pipe Size")
                    group.NominalSize = [self.size_cb.currentText()]
                    
                group.PipeOuterDiameter = float(od)
                group.PipeThickness = float(thick)
                group.PipeMaterial = [pipe_type]
                group.PipeMaterial = pipe_type
                
                # --- CREATE NETWORK OBJECT ---
                obj = doc.addObject("Part::Feature", "Pipe_Network")
                obj.Shape = final_shape
                
                group.addObject(obj)

                ComfacUtils.add_common_properties(obj, self.primary_obj, {"PipeOuter": float(od), "PipeInner": float(id_val), "PipeType": pipe_type})
                if hasattr(obj, "Refine"): obj.Refine = True
                obj.ViewObject.ShapeColor = pipe_color
                
                if "PVC" in pipe_type:
                    pvc_selection = self.color_cb.currentText()
                    if pvc_selection in self.pvc_colors:
                        color = self.pvc_colors[pvc_selection]
                        color_tuple = tuple(color) if isinstance(color, list) else color
                        obj.addProperty("App::PropertyColor", "PipeColor", "PipeData")
                        obj.PipeColor = color_tuple
                        
                # Hide all original sketches used
                for sel_obj in self.selected_objs:
                    if hasattr(sel_obj, "ViewObject") and sel_obj.ViewObject:
                        sel_obj.ViewObject.hide()

                doc.recompute()
                doc.commitTransaction()
                
                # Trigger Observer manually for the first run
                FreeCAD.GlobalNetworkObserver.trigger_rebuild_manually(group)

            except Exception as e:
                doc.abortTransaction()
                QtWidgets.QMessageBox.critical(None, "Feature Creation Error", f"Failed building the final object:\n{e}")

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Fatal Crash", f"The script crashed completely:\n{str(e)}")


class CreateNetworkPipe:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('Pipes_Network.svg'), 
            'MenuText': "Generate Pipe Network",
            'ToolTip': "Generates interconnected pipes via Task Panel"
        }

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        valid_objs = [obj for obj in sel if hasattr(obj, "Shape") and len(obj.Shape.Edges) > 0]
        
        if not valid_objs:
            QtWidgets.QMessageBox.warning(None, "Selection Error", "Please select your Sketches in the tree before clicking this button!")
            return
            
        FreeCADGui.Control.showDialog(PipeTaskPanel(valid_objs))

FreeCADGui.addCommand('CreateNetworkPipe', CreateNetworkPipe())