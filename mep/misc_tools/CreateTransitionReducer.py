import FreeCAD as App
import FreeCADGui as Gui
import Part
import math

try:
    import Ducts.DuctGeometryUtils as DuctGeometryUtils
except ImportError:
    App.Console.PrintError("Error: Could not find DuctGeometryUtils.py. Ensure it is in the same directory.\n")

try:
    from compat import QtWidgets, QtCore, QtGui
except ImportError:
    from compat import QtWidgets, QtCore, QtGui
    from compat import QtWidgets, QtCore, QtGui

class TransitionTaskPanel:
    def __init__(self):
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(self.form)
        
        # 1. Grab the Selection
        sel_ex = Gui.Selection.getSelectionEx()
        if not sel_ex or not sel_ex[0].HasSubObjects or not sel_ex[0].SubElementNames[0].startswith("Face"):
            App.Console.PrintError("Please select a Face of a duct first.\n")
            return
            
        self.obj = sel_ex[0].Object
        self.face = sel_ex[0].SubObjects[0]
        
        # 2. Determine Local Axes and exact W1 / D1
        self.center = self.face.CenterOfMass
        self.normal = self.face.normalAt(0,0)
        
        self.local_X = None
        for edge in self.face.OuterWire.Edges:
            if hasattr(edge.Curve, 'Direction'):
                self.local_X = edge.Curve.Direction
                break
                
        if self.local_X is None: 
            global_Z = App.Vector(0,0,1)
            self.local_X = App.Vector(1,0,0) if abs(self.normal.z) > 0.99 else self.normal.cross(global_Z).normalize()
            
        self.local_Y = self.normal.cross(self.local_X).normalize()
        
        verts = self.face.OuterWire.Vertexes
        x_vals = [(v.Point - self.center).dot(self.local_X) for v in verts]
        y_vals = [(v.Point - self.center).dot(self.local_Y) for v in verts]
        
        self.W1 = max(x_vals) - min(x_vals)
        self.D1 = max(y_vals) - min(y_vals)
        
        # --- THE FIX: Open the transaction immediately ---
        App.ActiveDocument.openTransaction("Create Transition Reducer")
        
        # 3. Create the Temporary Preview Object (Now safely inside the transaction)
        self.preview_obj = App.ActiveDocument.addObject("Part::Feature", "Preview_Transition")
        if self.preview_obj.ViewObject:
            self.preview_obj.ViewObject.Transparency = 50 
            self.preview_obj.ViewObject.ShapeColor = (0.3, 0.6, 0.9) 
        
        # 4. Build the UI
        self.setup_ui()
        
    def setup_ui(self):
        self.layout.addWidget(QtWidgets.QLabel(f"Original Size (W1 x D1): {self.W1:.1f} x {self.D1:.1f} mm"))
        
        self.layout.addWidget(QtWidgets.QLabel("Target Profile:"))
        self.shape_combo = QtWidgets.QComboBox()
        self.shape_combo.addItems(["Rectangular", "Circular", "Match Original"])
        self.layout.addWidget(self.shape_combo)
        
        # --- Width Input with 100mm Minimum ---
        self.w2_label = QtWidgets.QLabel("Target Width (W2):")
        self.layout.addWidget(self.w2_label)
        self.w2_input = QtWidgets.QDoubleSpinBox()
        self.w2_input.setMinimum(100.0) # Enforce Minimum
        self.w2_input.setMaximum(10000.0)
        self.w2_input.setSingleStep(50.0)
        self.w2_input.setValue(max(self.W1, 100.0)) 
        self.layout.addWidget(self.w2_input)
        
        # --- Depth Input with 100mm Minimum ---
        self.d2_label = QtWidgets.QLabel("Target Depth (D2):")
        self.layout.addWidget(self.d2_label)
        self.d2_input = QtWidgets.QDoubleSpinBox()
        self.d2_input.setMinimum(100.0) # Enforce Minimum
        self.d2_input.setMaximum(10000.0)
        self.d2_input.setSingleStep(50.0) 
        self.d2_input.setValue(max(self.D1, 100.0)) 
        self.layout.addWidget(self.d2_input)
        
        self.layout.addWidget(QtWidgets.QLabel("Calculation Ratio (p):"))
        self.p_input = QtWidgets.QDoubleSpinBox()
        self.p_input.setSuffix("%")
        self.p_input.setRange(0.1, 1000.0)
        self.p_input.setValue(50.0)
        self.layout.addWidget(self.p_input)
        
        self.layout.addWidget(QtWidgets.QLabel("Final Transition Length (L):"))
        self.l_input = QtWidgets.QDoubleSpinBox()
        self.l_input.setMaximum(100000.0)
        self.layout.addWidget(self.l_input)
        
        self.layout.addWidget(QtWidgets.QLabel("Alignment:"))
        self.align_combo = QtWidgets.QComboBox()
        self.align_combo.addItems([
            "Concentric", 
            "Eccentric (Top Flat)", 
            "Eccentric (Bottom Flat)",
            "Eccentric (Left Flat)", 
            "Eccentric (Right Flat)"
        ])
        self.layout.addWidget(self.align_combo)
        
        self.shape_combo.currentIndexChanged.connect(self.on_shape_change)
        self.w2_input.valueChanged.connect(self.update_length)
        self.d2_input.valueChanged.connect(self.update_length)
        self.p_input.valueChanged.connect(self.update_length)
        self.l_input.valueChanged.connect(self.update_preview)
        self.align_combo.currentIndexChanged.connect(self.update_preview)
        
        self.update_length()

    def on_shape_change(self):
        shape = self.shape_combo.currentText()
        if shape == "Circular":
            self.w2_label.setText("Target Diameter (D):")
            self.d2_label.hide()
            self.d2_input.hide()
        else:
            self.w2_label.setText("Target Width (W2):")
            self.d2_label.show()
            self.d2_input.show()
        self.update_length()
        self.update_preview()

    def update_length(self):
        W2 = self.w2_input.value()
        D2 = W2 if self.shape_combo.currentText() == "Circular" else self.d2_input.value()
        p = self.p_input.value() / 100.0
        
        avg_original = (self.W1 + self.D1) / 2.0
        avg_target = (W2 + D2) / 2.0
        
        calc_L = (avg_original + avg_target) * p
        self.l_input.blockSignals(True) # Prevent double preview update
        self.l_input.setValue(calc_L)
        self.l_input.blockSignals(False)
        self.update_preview()

    def update_preview(self, *args):
        W2 = self.w2_input.value()
        shape_type = self.shape_combo.currentText()
        target_W = max(W2, 0.01)
        target_D = max((W2 if shape_type == "Circular" else self.d2_input.value()), 0.01)
        L = self.l_input.value()
        alignment = self.align_combo.currentText()
        
        outer_wire = self.face.OuterWire
        inner_wire = None
        thickness = 0.0
        
        if len(self.face.Wires) > 1:
            for w in self.face.Wires:
                if not w.isEqual(outer_wire):
                    inner_wire = w
                    break
            if inner_wire and len(inner_wire.Vertexes) > 0:
                dist, _, _ = outer_wire.distToShape(inner_wire.Vertexes[0])
                thickness = dist

        offset_vec = App.Vector(0,0,0)
        if alignment != "Concentric":
            if "Top Flat" in alignment:
                offset_vec += self.local_Y * (self.D1 - target_D) / 2.0
            elif "Bottom Flat" in alignment:
                offset_vec -= self.local_Y * (self.D1 - target_D) / 2.0
            elif "Right Flat" in alignment:
                offset_vec += self.local_X * (self.W1 - target_W) / 2.0
            elif "Left Flat" in alignment:
                offset_vec -= self.local_X * (self.W1 - target_W) / 2.0
                
        target_center = self.center + (self.normal * L) + offset_vec

        def get_target_profile(is_inner=False):
            t = thickness if is_inner else 0.0
            tw = max(target_W - 2*t, 0.01)
            td = max(target_D - 2*t, 0.01)
            
            if shape_type == "Rectangular":
                return DuctGeometryUtils.create_profile(tw, td, 0.0, target_center, self.normal, self.local_Y, "Rectangular")
            elif shape_type == "Circular":
                return DuctGeometryUtils.create_profile(tw, td, 0.0, target_center, self.normal, self.local_Y, "Round")
            elif shape_type == "Match Original":
                src_wire = inner_wire if is_inner else outer_wire
                sx = tw / self.W1 if self.W1 != 0 else 1.0
                sy = td / self.D1 if self.D1 != 0 else 1.0
                
                m1 = App.Matrix(); m1.move(-self.center.x, -self.center.y, -self.center.z)
                m2 = App.Matrix()
                m2.A11 = self.local_X.x; m2.A12 = self.local_X.y; m2.A13 = self.local_X.z
                m2.A21 = self.local_Y.x; m2.A22 = self.local_Y.y; m2.A23 = self.local_Y.z
                m2.A31 = self.normal.x;  m2.A32 = self.normal.y;  m2.A33 = self.normal.z
                
                m3 = App.Matrix(); m3.scale(sx, sy, 1.0)
                flat_mat = m3.multiply(m2.inverse()).multiply(m1)
                
                w_new = src_wire.copy()
                w_new.transformShape(flat_mat)
                
                m_rot = m2; w_new.transformShape(m_rot)
                m_pos = App.Matrix(); m_pos.move(target_center.x, target_center.y, target_center.z)
                w_new.transformShape(m_pos)
                
                return w_new

        try:
            wire2_out = get_target_profile(is_inner=False)
            final_shape = Part.makeLoft([outer_wire, wire2_out], True)
            
            if inner_wire and thickness > 0:
                wire2_in = get_target_profile(is_inner=True)
                inner_solid = Part.makeLoft([inner_wire, wire2_in], True)
                final_shape = final_shape.cut(inner_solid)

            self.preview_obj.Shape = final_shape
            App.ActiveDocument.recompute()
        except Exception as e:
            pass

    def accept(self):
        try:
            self.preview_obj.Label = "TransitionReducer"
            if self.preview_obj.ViewObject and self.obj.ViewObject:
                self.preview_obj.ViewObject.Transparency = 0
                self.preview_obj.ViewObject.ShapeColor = self.obj.ViewObject.ShapeColor
            
            try:
                merged = DuctGeometryUtils.fuse_shapes([self.obj.Shape, self.preview_obj.Shape])
                fusion = App.ActiveDocument.addObject("Part::Feature", "Merged_Duct_System")
                fusion.Shape = merged
            except:
                fusion = App.ActiveDocument.addObject("Part::MultiFuse", "Merged_Duct_System")
                fusion.Shapes = [self.obj, self.preview_obj]
            
            self.obj.ViewObject.Visibility = False
            self.preview_obj.ViewObject.Visibility = False

            App.ActiveDocument.recompute()
            
            # Commit all changes into a single Undo Step
            App.ActiveDocument.commitTransaction()
            
        except Exception as e:
            # If fusion fails, abort the transaction entirely
            App.ActiveDocument.abortTransaction()
            App.Console.PrintError(f"Failed to finalize transition: {str(e)}\n")
            
        Gui.Control.closeDialog()

    def reject(self):
        # Automatically deletes the preview object and undoes any changes
        App.ActiveDocument.abortTransaction()
        Gui.Control.closeDialog()

import ComfacUtils
class CommandCreateTransition:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path("Connection.svg"),
            'MenuText': 'Create Transition Reducer',
            'ToolTip': 'Creates a transition from a selected duct face.'
        }

    def Activated(self):
        panel = TransitionTaskPanel()
        if hasattr(panel, 'obj'):
            Gui.Control.showDialog(panel)

Gui.addCommand('Create_Transition', CommandCreateTransition())