import os
import json
import FreeCAD as App
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils

class PipeHangerTaskPanel:
    def __init__(self, pipe_od, pipe_length, pipe_dir, p_center):
        # Auto-detected geometric data
        self.pipe_od_val = pipe_od
        self.pipe_length = pipe_length
        self.pipe_dir = pipe_dir
        self.p_center = p_center

        # Load pipe data from JSON
        self.pipe_data = {}
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "PipeData.json")
        try:
            with open(data_path, 'r') as f:
                self.pipe_data = json.load(f)
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to load pipe data: {e}\n")
            self.pipe_data = {}

        # Flatten pipe data to {size_name: OD} for UI
        self.sizes = {}
        for ptype, sizes in self.pipe_data.items():
            for size_name, values in sizes.items():
                od = values[0] if isinstance(values, list) else values
                self.sizes[size_name] = od

        self.preview = ComfacUtils.PreviewManager(App.ActiveDocument, "Hanger_Preview")

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(["Band Hanger", "Clevis Hanger"])
        
        # --- NEW: Angle Rotation Input ---
        self.angle_input = QtWidgets.QDoubleSpinBox()
        self.angle_input.setRange(-360.0, 360.0)
        self.angle_input.setSingleStep(90.0)
        self.angle_input.setValue(0.0)
        self.angle_input.setSuffix(" °")
        
        self.size_cb = QtWidgets.QComboBox()
        self.size_cb.addItems(list(self.sizes.keys()) + ["Custom"])

        self.od_input = QtWidgets.QDoubleSpinBox()
        self.od_input.setRange(5.0, 1000.0)
        self.od_input.setSuffix(" mm")
        
        # --- Linear Array Inputs ---
        self.count_input = QtWidgets.QSpinBox()
        self.count_input.setRange(1, 500)
        self.count_input.setValue(1)
        
        self.spacing_input = QtWidgets.QDoubleSpinBox()
        self.spacing_input.setRange(10.0, 50000.0)
        self.spacing_input.setValue(1500.0) # Standard 1.5m spacing
        self.spacing_input.setSuffix(" mm")

        self.width_input = QtWidgets.QDoubleSpinBox()
        self.width_input.setRange(5.0, 100.0)
        self.width_input.setValue(25.0)
        self.width_input.setSuffix(" mm")

        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.5, 15.0)
        self.thick_input.setValue(2.0)
        self.thick_input.setSuffix(" mm")

        self.layout.addRow("Hanger Type:", self.type_cb)
        self.layout.addRow("Angle Rotation:", self.angle_input) # Added to layout
        self.layout.addRow("Pipe Size:", self.size_cb)
        self.layout.addRow("Pipe OD:", self.od_input)
        self.layout.addRow(QtWidgets.QLabel("")) # Spacer
        self.layout.addRow(QtWidgets.QLabel("<b>Array Settings</b>"))
        self.layout.addRow("Number of Hangers:", self.count_input)
        self.layout.addRow("Distance Between:", self.spacing_input)
        self.layout.addRow(QtWidgets.QLabel("")) # Spacer
        self.layout.addRow("Material Width:", self.width_input)
        self.layout.addRow("Material Thick:", self.thick_input)

        self.size_cb.currentIndexChanged.connect(self.update_ui)
        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.angle_input.valueChanged.connect(self.trigger_preview) # Connected to preview
        self.od_input.valueChanged.connect(self.trigger_preview)
        self.count_input.valueChanged.connect(self.trigger_preview)
        self.spacing_input.valueChanged.connect(self.trigger_preview)
        self.width_input.valueChanged.connect(self.trigger_preview)
        self.thick_input.valueChanged.connect(self.trigger_preview)

        # Auto-match combo box to detected OD
        self.od_input.setValue(self.pipe_od_val)
        matched_size = "Custom"
        best_match = None
        best_diff = float('inf')
        for key, val in self.sizes.items():
            diff = abs(val - self.pipe_od_val)
            if diff < best_diff:
                best_diff = diff
                best_match = key
        if best_diff < 2.0:  # 2mm tolerance
            matched_size = best_match
        self.size_cb.setCurrentText(matched_size)
        self.update_ui()

    def update_ui(self):
        val_size = self.size_cb.currentText()
        if val_size in self.sizes:
            self.od_input.setValue(self.sizes[val_size])
            self.od_input.setEnabled(False)
        else:
            self.od_input.setEnabled(True)
        self.trigger_preview()

    def trigger_preview(self):
        od = self.od_input.value()
        thick = self.thick_input.value()
        width = self.width_input.value()
        h_type = self.type_cb.currentText()
        angle_rot = self.angle_input.value() # Fetch angle
        count = self.count_input.value()
        spacing = self.spacing_input.value()
        array_length = (count - 1) * spacing

        ghost_shape = self.build_array_geometry(od, thick, width, h_type, count, spacing, array_length, angle_rot)
        if ghost_shape:
            self.preview.update(ghost_shape)

    def build_array_geometry(self, od, thick, width, h_type, count, spacing, array_length, angle_rot):
        try:
            shapes = []
            start_pos = self.p_center - self.pipe_dir * (array_length / 2.0)
            Z_local = self.pipe_dir
            Y_global = App.Vector(0, 0, 1)
            if abs(Z_local.z) > 0.99: Y_global = App.Vector(1, 0, 0)
            
            # Create base vectors
            X_base = Y_global.cross(Z_local).normalize()
            Y_base = Z_local.cross(X_base).normalize()

            # Apply Angle Rotation
            roll_rot = App.Rotation(Z_local, angle_rot)
            X_local = roll_rot.multVec(X_base)
            Y_local = roll_rot.multVec(Y_base)

            for i in range(count):
                if h_type == "Band Hanger": shape = self.get_band_hanger_shape(od, thick, width)
                else: shape = self.get_clevis_hanger_shape(od, thick, width)
                shape.translate(App.Vector(0, 0, -width/2.0))
                pt = start_pos + self.pipe_dir * (spacing * i)
                mat = App.Matrix(X_local.x, Y_local.x, Z_local.x, pt.x,
                                 X_local.y, Y_local.y, Z_local.y, pt.y,
                                 X_local.z, Y_local.z, Z_local.z, pt.z,
                                 0.0, 0.0, 0.0, 1.0)
                shape.transformShape(mat)
                shapes.append(shape)
            return Part.makeCompound(shapes)
        except:
            return None

    def accept(self):
        od = self.od_input.value()
        thick = self.thick_input.value()
        width = self.width_input.value()
        h_type = self.type_cb.currentText()
        angle_rot = self.angle_input.value() # Fetch angle
        count = self.count_input.value()
        spacing = self.spacing_input.value()

        array_length = (count - 1) * spacing
        if array_length > self.pipe_length:
            reply = QtWidgets.QMessageBox.question(
                None, "Array Warning",
                f"The total length of this hanger array ({array_length} mm) is longer than the selected pipe segment ({self.pipe_length:.1f} mm).\n\n"
                "Some hangers may be placed floating in the air. Do you want to generate anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        self.preview.clear()
        FreeCADGui.Control.closeDialog()

        final_shape = self.build_array_geometry(od, thick, width, h_type, count, spacing, array_length, angle_rot)
        if final_shape:
            self.commit_hanger_array(final_shape, h_type)

    def reject(self):
        self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def commit_hanger_array(self, final_compound, h_type):
        doc = App.ActiveDocument
        doc.openTransaction("Generate Hanger Array")
        try:
            obj = doc.addObject("Part::Feature", f"{h_type.replace(' ', '_')}_Array")
            obj.Shape = final_compound
            obj.ViewObject.ShapeColor = (0.6, 0.6, 0.6)
            doc.recompute()
            doc.commitTransaction()
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Generation Error", f"Failed to array hangers:\n{str(e)}")

    def get_band_hanger_shape(self, od, thick, width):
        # THE FIX: Added vertical clearance before angling inwards
        r_in = od / 2.0
        r_out = r_in + thick
        h_bend = r_in + 5.0   # Go straight up past the equator before bending
        h_top = r_in + 35.0   # Raise the pinch point so it scales with the pipe size
        flat_w = 12.0
        
        # Inner Teardrop Wire (Explicit Polygon)
        arc_i = Part.Arc(App.Vector(-r_in, 0, 0), App.Vector(0, -r_in, 0), App.Vector(r_in, 0, 0)).toShape()
        w_in = Part.Wire([
            arc_i, 
            Part.makeLine(App.Vector(r_in, 0, 0), App.Vector(r_in, h_bend, 0)),
            Part.makeLine(App.Vector(r_in, h_bend, 0), App.Vector(flat_w, h_top, 0)),
            Part.makeLine(App.Vector(flat_w, h_top, 0), App.Vector(-flat_w, h_top, 0)),
            Part.makeLine(App.Vector(-flat_w, h_top, 0), App.Vector(-r_in, h_bend, 0)),
            Part.makeLine(App.Vector(-r_in, h_bend, 0), App.Vector(-r_in, 0, 0))
        ])
        
        # Outer Teardrop Wire (Explicit Polygon)
        flat_w_out = flat_w + thick
        h_top_out = h_top + thick
        arc_o = Part.Arc(App.Vector(-r_out, 0, 0), App.Vector(0, -r_out, 0), App.Vector(r_out, 0, 0)).toShape()
        w_out = Part.Wire([
            arc_o, 
            Part.makeLine(App.Vector(r_out, 0, 0), App.Vector(r_out, h_bend, 0)),
            Part.makeLine(App.Vector(r_out, h_bend, 0), App.Vector(flat_w_out, h_top_out, 0)),
            Part.makeLine(App.Vector(flat_w_out, h_top_out, 0), App.Vector(-flat_w_out, h_top_out, 0)),
            Part.makeLine(App.Vector(-flat_w_out, h_top_out, 0), App.Vector(-r_out, h_bend, 0)),
            Part.makeLine(App.Vector(-r_out, h_bend, 0), App.Vector(-r_out, 0, 0))
        ])
        
        # Make Face and Extrude (Solid approach)
        strap = Part.Face(w_out).cut(Part.Face(w_in)).extrude(App.Vector(0, 0, width))
        
        # Add Top Nut 
        collar = Part.makeCylinder(7.0, 12.0, App.Vector(0, h_top_out - 1.0, width/2), App.Vector(0, 1, 0))
        # Drop the rod hole down dynamically so it doesn't float
        rod_hole = Part.makeCylinder(5.0, 50.0, App.Vector(0, h_bend, width/2), App.Vector(0, 1, 0))
        
        return strap.fuse(collar).cut(rod_hole).removeSplitter()

    def get_clevis_hanger_shape(self, od, thick, width):
        r_in = (od / 2.0) + 1.0
        r_out = r_in + thick
        u_h = r_in + 12.0
        
        arc_i = Part.Arc(App.Vector(-r_in, 0, 0), App.Vector(0, -r_in, 0), App.Vector(r_in, 0, 0)).toShape()
        w_in = Part.Wire([arc_i, Part.makeLine(App.Vector(r_in, 0, 0), App.Vector(r_in, u_h, 0)), 
                          Part.makeLine(App.Vector(r_in, u_h, 0), App.Vector(-r_in, u_h, 0)),
                          Part.makeLine(App.Vector(-r_in, u_h, 0), App.Vector(-r_in, 0, 0))])
        
        arc_o = Part.Arc(App.Vector(-r_out, 0, 0), App.Vector(0, -r_out, 0), App.Vector(r_out, 0, 0)).toShape()
        w_out = Part.Wire([arc_o, Part.makeLine(App.Vector(r_out, 0, 0), App.Vector(r_out, u_h, 0)), 
                           Part.makeLine(App.Vector(r_out, u_h, 0), App.Vector(-r_out, u_h, 0)),
                           Part.makeLine(App.Vector(-r_out, u_h, 0), App.Vector(-r_out, 0, 0))])
        
        u_strap = Part.Face(w_out).cut(Part.Face(w_in)).extrude(App.Vector(0, 0, width))
        
        y_w_in = r_out + 0.5; y_w_out = y_w_in + thick
        y_top_h = 30.0; y_flat = 8.0
        
        yo_w = Part.Wire([Part.makeLine(App.Vector(-y_w_out, u_h - 5, 0), App.Vector(-y_w_out, u_h + 10, 0)),
                          Part.makeLine(App.Vector(-y_w_out, u_h + 10, 0), App.Vector(-y_flat - thick, u_h + y_top_h + thick, 0)),
                          Part.makeLine(App.Vector(-y_flat - thick, u_h + y_top_h + thick, 0), App.Vector(y_flat + thick, u_h + y_top_h + thick, 0)),
                          Part.makeLine(App.Vector(y_flat + thick, u_h + y_top_h + thick, 0), App.Vector(y_w_out, u_h + 10, 0)),
                          Part.makeLine(App.Vector(y_w_out, u_h + 10, 0), App.Vector(y_w_out, u_h - 5, 0)),
                          Part.makeLine(App.Vector(y_w_out, u_h - 5, 0), App.Vector(-y_w_out, u_h - 5, 0))])
        
        yi_w = Part.Wire([Part.makeLine(App.Vector(-y_w_in, u_h - 6, 0), App.Vector(-y_w_in, u_h + 10, 0)),
                          Part.makeLine(App.Vector(-y_w_in, u_h + 10, 0), App.Vector(-y_flat, u_h + y_top_h, 0)),
                          Part.makeLine(App.Vector(-y_flat, u_h + y_top_h, 0), App.Vector(y_flat, u_h + y_top_h, 0)),
                          Part.makeLine(App.Vector(y_flat, u_h + y_top_h, 0), App.Vector(y_w_in, u_h + 10, 0)),
                          Part.makeLine(App.Vector(y_w_in, u_h + 10, 0), App.Vector(y_w_in, u_h - 6, 0)),
                          Part.makeLine(App.Vector(y_w_in, u_h - 6, 0), App.Vector(-y_w_in, u_h - 6, 0))])
        
        yoke = Part.Face(yo_w).cut(Part.Face(yi_w)).extrude(App.Vector(0, 0, width))
        
        bolt_hole = Part.makeCylinder(3.5, y_w_out*3, App.Vector(-y_w_out*1.5, u_h + 2, width/2), App.Vector(1, 0, 0))
        rod_hole = Part.makeCylinder(5.0, 30.0, App.Vector(0, u_h + y_top_h - 5, width/2), App.Vector(0, 1, 0))
        cross_bolt = Part.makeCylinder(3.0, y_w_out*2 + 10, App.Vector(-y_w_out - 5, u_h + 2, width/2), App.Vector(1, 0, 0))

        return u_strap.fuse(yoke).cut(bolt_hole).cut(rod_hole).fuse(cross_bolt).removeSplitter()


class CreateHangerCommand:
    def GetResources(self):
        return {'Pixmap': ComfacUtils.get_icon_path('PipeHanger.svg'), 'MenuText': "Array Pipe Hangers", 'ToolTip': "Select a pipe to array hangers along it"}
        
    def extract_pipe_data(self, sel_obj, sub_objs):
        # Intelligent Scanner: Finds the longest straight cylinder face in the selection
        faces_to_check = sub_objs if sub_objs else sel_obj.Shape.Faces
        best_face = None
        max_len = -1
        p_center, pipe_dir, pipe_od = None, None, None
        
        for face in faces_to_check:
            if isinstance(face.Surface, Part.Cylinder):
                circles = [e for e in face.Edges if isinstance(e.Curve, Part.Circle)]
                if len(circles) >= 2:
                    p1 = circles[0].Curve.Center
                    p2 = circles[-1].Curve.Center
                    length = (p2 - p1).Length
                    if length > max_len:
                        max_len = length
                        best_face = face
                        p_center = (p1 + p2) / 2.0
                        pipe_dir = (p2 - p1).normalize()
                        pipe_od = face.Surface.Radius * 2.0
                        
        # Fallback for irregular pipes
        if best_face is None and faces_to_check:
            for face in faces_to_check:
                if isinstance(face.Surface, Part.Cylinder):
                    pipe_od = face.Surface.Radius * 2.0
                    pipe_dir = face.Surface.Axis
                    p_center = face.CenterOfMass
                    max_len = face.BoundBox.DiagonalLength * 0.8 
                    break
                    
        return pipe_od, max_len, pipe_dir, p_center

    def Activated(self):
        selEx = FreeCADGui.Selection.getSelectionEx()
        if not selEx:
            QtWidgets.QMessageBox.warning(None, "Selection Error", "Please select a Pipe object in the tree or a specific cylindrical pipe face in the 3D view.")
            return
            
        obj = selEx[0].Object
        subs = selEx[0].SubObjects
        
        od, length, direction, center = self.extract_pipe_data(obj, subs)
        
        if od is None:
            QtWidgets.QMessageBox.warning(None, "Detection Error", "Could not mathematically detect a straight cylindrical pipe segment in the current selection.\n\nPlease click directly on the straight outer face of a pipe.")
            return
            
        panel = PipeHangerTaskPanel(od, length, direction, center)
        FreeCADGui.Control.showDialog(panel)

try:
    FreeCADGui.addCommand('CreatePipeHanger', CreateHangerCommand())
except:
    pass