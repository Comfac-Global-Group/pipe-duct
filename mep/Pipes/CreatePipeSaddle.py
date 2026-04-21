import FreeCAD as App
import FreeCADGui
import Part
import math
import json
import os
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils

class PipeSaddleTaskPanel:
    def __init__(self, pipe_od, pipe_length, pipe_dir, p_center):
        self.pipe_od_val = pipe_od
        self.pipe_length = pipe_length
        self.pipe_dir = pipe_dir
        self.p_center = p_center

        # Load sizes from PipeData.json
        self.sizes = {}
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "PipeData.json")
        try:
            with open(data_path, 'r') as f:
                pipe_data = json.load(f)
            # Flatten all pipe types and sizes into a single dictionary
            for pipe_type, sizes in pipe_data.items():
                for size_name, dims in sizes.items():
                    key = f"{pipe_type} - {size_name}"
                    self.sizes[key] = dims  # dims is [OD, WallThickness]
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to load pipe data: {e}\n")
            # Fallback to minimal defaults
            self.sizes = {
                "Copper Type K - 1/4 inch": [9.525, 0.889], "Copper Type K - 3/8 inch": [12.7, 1.2446],
                "Copper Type K - 1/2 inch": [15.875, 1.2446], "Copper Type K - 3/4 inch": [22.225, 1.651],
                "Copper Type K - 1 inch": [28.575, 1.8288]
            }

        # 1. Initialize the Live Preview Ghost
        self.preview = ComfacUtils.PreviewManager(App.ActiveDocument, "Saddle_Preview")

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(["Double Sided", "Single Sided"])
        
        self.roll_input = QtWidgets.QDoubleSpinBox()
        self.roll_input.setRange(-360.0, 360.0)
        self.roll_input.setSingleStep(90.0)
        self.roll_input.setValue(0.0)
        self.roll_input.setSuffix(" °")
        
        self.size_cb = QtWidgets.QComboBox()
        size_list = list(self.sizes.keys())
        size_list.sort()
        self.size_cb.addItems(size_list + ["Custom"])

        self.od_input = QtWidgets.QDoubleSpinBox()
        self.od_input.setRange(0.1, 2000.0); self.od_input.setDecimals(4); self.od_input.setSuffix(" mm")

        self.count_input = QtWidgets.QSpinBox()
        self.count_input.setRange(1, 500)
        self.count_input.setValue(1)
        
        self.spacing_input = QtWidgets.QDoubleSpinBox()
        self.spacing_input.setRange(10.0, 50000.0)
        self.spacing_input.setValue(1000.0) 
        self.spacing_input.setSuffix(" mm")

        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.1, 50.0); self.thick_input.setDecimals(4); self.thick_input.setSuffix(" mm")

        self.width_input = QtWidgets.QDoubleSpinBox()
        self.width_input.setRange(1.0, 1000.0); self.width_input.setValue(25.0); self.width_input.setSuffix(" mm")

        self.layout.addRow("Saddle Type:", self.type_cb)
        self.layout.addRow("Roll Alignment:", self.roll_input)
        self.layout.addRow("Pipe Size:", self.size_cb)
        self.layout.addRow("Pipe OD:", self.od_input)
        self.layout.addRow(QtWidgets.QLabel("")) 
        self.layout.addRow(QtWidgets.QLabel("<b>Array Settings</b>"))
        self.layout.addRow("Number of Saddles:", self.count_input)
        self.layout.addRow("Distance Between:", self.spacing_input)
        self.layout.addRow(QtWidgets.QLabel("")) 
        self.layout.addRow("Strap Thick:", self.thick_input)
        self.layout.addRow("Strap Width:", self.width_input)

        # 2. Connect UI changes to trigger the   update
        self.size_cb.currentIndexChanged.connect(self.update_ui)
        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.roll_input.valueChanged.connect(self.trigger_preview)
        self.od_input.valueChanged.connect(self.trigger_preview)
        self.count_input.valueChanged.connect(self.trigger_preview)
        self.spacing_input.valueChanged.connect(self.trigger_preview)
        self.thick_input.valueChanged.connect(self.trigger_preview)
        self.width_input.valueChanged.connect(self.trigger_preview)
        
        self.od_input.setValue(self.pipe_od_val)
        matched_size = "Custom"
        for key, val in self.sizes.items():
            if abs(val[0] - self.pipe_od_val) < 0.5: 
                matched_size = key
                break
        self.size_cb.setCurrentText(matched_size)
        self.update_ui()

    def update_ui(self):
        val_size = self.size_cb.currentText()
        if val_size in self.sizes:
            dims = self.sizes[val_size]
            self.od_input.setValue(dims[0])
            self.thick_input.setValue(dims[1] if len(dims) > 1 else dims[0] * 0.1)
            self.od_input.setEnabled(False); self.thick_input.setEnabled(False)
        else:
            self.od_input.setEnabled(True); self.thick_input.setEnabled(True)
        self.trigger_preview()

    def trigger_preview(self):
        """Builds the shape in memory and sends it to the Ghost manager."""
        od = self.od_input.value()
        thick = self.thick_input.value()
        width = self.width_input.value()
        is_single = (self.type_cb.currentText() == "Single Sided")
        roll_angle = self.roll_input.value()
        count = self.count_input.value()
        spacing = self.spacing_input.value()
        array_length = (count - 1) * spacing
        
        ghost_shape = self.build_array_geometry(od, thick, width, is_single, count, spacing, array_length, roll_angle)
        if ghost_shape:
            self.preview.update(ghost_shape)

    def accept(self):
        od = self.od_input.value()
        thick = self.thick_input.value()
        width = self.width_input.value()
        is_single = (self.type_cb.currentText() == "Single Sided")
        roll_angle = self.roll_input.value()
        count = self.count_input.value()
        spacing = self.spacing_input.value()
        array_length = (count - 1) * spacing

        if array_length > self.pipe_length:
            reply = QtWidgets.QMessageBox.question(
                None, "Array Warning", 
                f"The total length of this saddle array ({array_length} mm) is longer than the selected straight pipe segment ({self.pipe_length:.1f} mm).\n\n"
                "Some saddles may be placed floating in the air past the pipe end. Do you want to generate anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return 

        # 3. Clean up the ghost BEFORE committing the final object
        self.preview.clear()
        FreeCADGui.Control.closeDialog()
        
        final_shape = self.build_array_geometry(od, thick, width, is_single, count, spacing, array_length, roll_angle)
        if final_shape:
            self.commit_saddle_array(final_shape, is_single)

    def reject(self):
        # 3. Clean up if the user cancels
        self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def get_saddle_shape(self, od, thick, width, is_single):
        r_inner = (od / 2.0) + 0.1 
        r_outer = r_inner + thick
        foot_len = 15.0 + (thick * 2)
        bolt_d = 6.5 if od < 100 else 10.5 
        
        arch_outer = Part.makeCylinder(r_outer, width)
        arch_inner = Part.makeCylinder(r_inner, width)
        arch = arch_outer.cut(arch_inner)
        
        bbox = Part.makeBox(r_outer * 3, r_outer * 2, width * 2, App.Vector(-r_outer * 1.5, -r_outer * 2, -width * 0.5))
        arch = arch.cut(bbox)
        
        foot_r = Part.makeBox(foot_len + thick, thick, width, App.Vector(r_inner, 0, 0))
        saddle = arch.fuse(foot_r)
        
        if not is_single:
            foot_l = Part.makeBox(foot_len + thick, thick, width, App.Vector(-r_inner - foot_len - thick, 0, 0))
            saddle = saddle.fuse(foot_l)
            
        saddle = saddle.removeSplitter()
        
        hole_x_offset = r_inner + thick + (foot_len / 2.0)
        hole_z_pos = width / 2.0
        hole_template = Part.makeCylinder(bolt_d / 2.0, thick * 4, App.Vector(0, -thick * 2, 0), App.Vector(0, 1, 0))
        
        hole_r_cut = hole_template.copy()
        hole_r_cut.translate(App.Vector(hole_x_offset, 0, hole_z_pos))
        saddle = saddle.cut(hole_r_cut)
        
        if not is_single:
            hole_l_cut = hole_template.copy()
            hole_l_cut.translate(App.Vector(-hole_x_offset, 0, hole_z_pos))
            saddle = saddle.cut(hole_l_cut)

        saddle.translate(App.Vector(0, 0, -width / 2.0))
        return saddle

    def build_array_geometry(self, od, thick, width, is_single, count, spacing, array_length, roll_angle):
        """Pure math function: returns the final Part.Compound without modifying the tree."""
        try:
            shapes = []
            start_pos = self.p_center - self.pipe_dir * (array_length / 2.0)
            Z_local = self.pipe_dir
            
            Y_global = App.Vector(0, 0, -1)
            if abs(Z_local.z) > 0.99: Y_global = App.Vector(1, 0, 0)
                
            X_base = Y_global.cross(Z_local).normalize()
            Y_base = Z_local.cross(X_base).normalize()
            
            roll_rot = App.Rotation(Z_local, roll_angle)
            X_local = roll_rot.multVec(X_base)
            Y_local = roll_rot.multVec(Y_base)
            
            for i in range(count):
                shape = self.get_saddle_shape(od, thick, width, is_single)
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

    def commit_saddle_array(self, final_compound, is_single):
        doc = App.ActiveDocument
        doc.openTransaction("Generate Saddle Array")
        try:
            saddle_name = "Single_Saddle_Array" if is_single else "Double_Saddle_Array"
            obj = doc.addObject("Part::Feature", saddle_name)
            obj.Shape = final_compound
            obj.ViewObject.ShapeColor = (0.6, 0.6, 0.6)
            
            doc.recompute()
            doc.commitTransaction()
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Generation Error", f"Failed to array saddles:\n{str(e)}")

import ComfacUtils

class CreatePipeSaddle:
    def GetResources(self):
        return {'Pixmap': ComfacUtils.get_icon_path('PipeSaddle.svg'), 'MenuText': "Array Pipe Saddles", 'ToolTip': "Select a pipe to array wall saddles along it"}

    def extract_pipe_data(self, sel_obj, sub_objs):
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
            
        panel = PipeSaddleTaskPanel(od, length, direction, center)
        FreeCADGui.Control.showDialog(panel)

try:
    FreeCADGui.addCommand('CreatePipeSaddle', CreatePipeSaddle())
except:
    pass