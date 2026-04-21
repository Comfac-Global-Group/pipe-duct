import FreeCAD as App
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui

try:
    import ComfacUtils
except ImportError:
    pass

class UniversalFastenerTaskPanel:
    def __init__(self, d_width, d_height, seg_length, seg_dir, p_center, target_obj=None):
        self.d_w = d_width
        self.d_h = d_height
        self.seg_length = seg_length
        self.seg_dir = seg_dir
        self.p_center = p_center
        self.target_obj = target_obj

        self.materials = {
            "Galvanized Steel": (0.6, 0.6, 0.6, 2.0),
            "Copper": (0.72, 0.45, 0.2, 1.5),
            "Stainless Steel": (0.5, 0.5, 0.55, 2.0),
            "PVC (Gray)": (0.3, 0.3, 0.3, 4.0),
            "Brass": (0.75, 0.65, 0.2, 2.0)
        }
        
        self.preview = ComfacUtils.PreviewManager(App.ActiveDocument, "DuctFastener_Preview") if 'ComfacUtils' in globals() else None

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(["Half Strap (L-Shape)", "Full Strap (U-Shape)", "Half Z-Strap"])

        self.mat_cb = QtWidgets.QComboBox()
        self.mat_cb.addItems(list(self.materials.keys()))
        
        self.roll_input = QtWidgets.QDoubleSpinBox()
        self.roll_input.setRange(-360.0, 360.0)
        self.roll_input.setSingleStep(90.0) 
        self.roll_input.setValue(0.0)
        self.roll_input.setSuffix(" °")

        self.w_input = QtWidgets.QDoubleSpinBox()
        self.w_input.setRange(1.0, 5000.0); self.w_input.setValue(self.d_w); self.w_input.setSuffix(" mm")

        self.h_input = QtWidgets.QDoubleSpinBox()
        self.h_input.setRange(1.0, 5000.0); self.h_input.setValue(self.d_h); self.h_input.setSuffix(" mm")

        self.count_input = QtWidgets.QSpinBox()
        self.count_input.setRange(1, 500); self.count_input.setValue(1)
        
        self.spacing_input = QtWidgets.QDoubleSpinBox()
        self.spacing_input.setRange(10.0, 50000.0); self.spacing_input.setValue(1500.0); self.spacing_input.setSuffix(" mm")

        self.strap_w_input = QtWidgets.QDoubleSpinBox()
        self.strap_w_input.setRange(1.0, 500.0); self.strap_w_input.setValue(25.0); self.strap_w_input.setSuffix(" mm")
        
        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.1, 20.0); self.thick_input.setValue(2.0); self.thick_input.setSuffix(" mm")

        self.bolt_input = QtWidgets.QDoubleSpinBox()
        self.bolt_input.setRange(1.0, 50.0); self.bolt_input.setValue(8.0); self.bolt_input.setSuffix(" mm")

        self.layout.addRow("Fastener Type:", self.type_cb)
        self.layout.addRow("Material:", self.mat_cb)
        self.layout.addRow("Roll Alignment:", self.roll_input)
        self.layout.addRow(QtWidgets.QLabel(""))
        self.layout.addRow("Detected Width:", self.w_input)
        self.layout.addRow("Detected Height:", self.h_input)
        self.layout.addRow(QtWidgets.QLabel(""))
        self.layout.addRow(QtWidgets.QLabel("<b>Array Settings</b>"))
        self.layout.addRow("Number of Fasteners:", self.count_input)
        self.layout.addRow("Distance Between:", self.spacing_input)
        self.layout.addRow(QtWidgets.QLabel(""))
        self.layout.addRow("Material Thick:", self.thick_input)
        self.layout.addRow("Strap Width:", self.strap_w_input)
        self.layout.addRow("Bolt Hole Dia:", self.bolt_input)

        self.mat_cb.currentIndexChanged.connect(self.update_material)
        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.roll_input.valueChanged.connect(self.trigger_preview)
        self.count_input.valueChanged.connect(self.trigger_preview)
        self.spacing_input.valueChanged.connect(self.trigger_preview)
        self.w_input.valueChanged.connect(self.trigger_preview)
        self.h_input.valueChanged.connect(self.trigger_preview)
        
        self.update_material()
        self.trigger_preview()

    def update_material(self):
        mat = self.mat_cb.currentText()
        self.thick_input.setValue(self.materials[mat][3])
        self.trigger_preview()

    def trigger_preview(self):
        if not self.preview: return
        h_type = self.type_cb.currentText()
        w = self.w_input.value()
        h = self.h_input.value()
        t = self.thick_input.value()
        sw = self.strap_w_input.value()
        b_dia = self.bolt_input.value()
        roll_angle = self.roll_input.value()
        count = self.count_input.value()
        spacing = self.spacing_input.value()
        array_length = (count - 1) * spacing
        
        ghost_shape = self.build_array_geometry(h_type, w, h, t, sw, b_dia, count, spacing, array_length, roll_angle)
        if ghost_shape:
            self.preview.update(ghost_shape)

    def build_array_geometry(self, h_type, w, h, t, sw, b_dia, count, spacing, array_length, roll_angle):
        try:
            shapes = []
            start_pos = self.p_center - self.seg_dir * (array_length / 2.0)
            Z_local = self.seg_dir
            Y_global = App.Vector(0, 1, 0)
            if abs(Z_local.y) > 0.99: Y_global = App.Vector(1, 0, 0)
                
            X_base = Y_global.cross(Z_local).normalize()
            Y_base = Z_local.cross(X_base).normalize()
            
            roll_rot = App.Rotation(Z_local, roll_angle)
            X_local = roll_rot.multVec(X_base)
            Y_local = roll_rot.multVec(Y_base)

            for i in range(count):
                shape = self.get_fastener_shape(h_type, w, h, t, sw, b_dia)
                pt = start_pos + self.seg_dir * (spacing * i)
                
                mat_trans = App.Matrix(X_local.x, Y_local.x, Z_local.x, pt.x,
                                 X_local.y, Y_local.y, Z_local.y, pt.y,
                                 X_local.z, Y_local.z, Z_local.z, pt.z,
                                 0.0, 0.0, 0.0, 1.0)
                shape.transformShape(mat_trans)
                shapes.append(shape)
                
            return Part.makeCompound(shapes)
        except:
            return None

    def accept(self):
        h_type = self.type_cb.currentText()
        mat = self.mat_cb.currentText()
        roll_angle = self.roll_input.value()
        w = self.w_input.value()
        h = self.h_input.value()
        t = self.thick_input.value()
        sw = self.strap_w_input.value()
        b_dia = self.bolt_input.value()
        count = self.count_input.value()
        spacing = self.spacing_input.value()
        array_length = (count - 1) * spacing
        
        if array_length > self.seg_length:
            reply = QtWidgets.QMessageBox.question(
                None, "Array Warning", 
                f"The array ({array_length} mm) is longer than the segment ({self.seg_length:.1f} mm). Generate anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()
        
        final_shape = self.build_array_geometry(h_type, w, h, t, sw, b_dia, count, spacing, array_length, roll_angle)
        if final_shape:
            self.commit_fastener_array(final_shape, h_type, mat)

    def reject(self):
        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def get_fastener_shape(self, h_type, duct_w, duct_h, t, sw, b_dia):
        clearance = 0.5
        rw_in = (duct_w / 2.0) + clearance
        rh_in = (duct_h / 2.0) + clearance
        holes = [] 
        face = None

        if h_type == "Half Strap (L-Shape)":
            pts = [
                App.Vector(-rw_in - 30, rh_in + t, 0),
                App.Vector(-rw_in, rh_in + t, 0),
                App.Vector(-rw_in, -rh_in, 0),
                App.Vector(rw_in, -rh_in, 0),
                App.Vector(rw_in, -rh_in - t, 0),
                App.Vector(-rw_in - t, -rh_in - t, 0),
                App.Vector(-rw_in - t, rh_in, 0),
                App.Vector(-rw_in - 30, rh_in, 0)
            ]
            pts.append(pts[0]) 
            face = Part.Face(Part.Wire(Part.makePolygon(pts)))
            holes.append((-rw_in - 15, rh_in + t/2, sw/2))

        elif h_type == "Full Strap (U-Shape)":
            pts = [
                App.Vector(-rw_in - 30, rh_in + t, 0),
                App.Vector(-rw_in, rh_in + t, 0),
                App.Vector(-rw_in, -rh_in, 0),
                App.Vector(rw_in, -rh_in, 0),
                App.Vector(rw_in, rh_in + t, 0),
                App.Vector(rw_in + 30, rh_in + t, 0),
                App.Vector(rw_in + 30, rh_in, 0),
                App.Vector(rw_in + t, rh_in, 0),
                App.Vector(rw_in + t, -rh_in - t, 0),
                App.Vector(-rw_in - t, -rh_in - t, 0),
                App.Vector(-rw_in - t, rh_in, 0),
                App.Vector(-rw_in - 30, rh_in, 0)
            ]
            pts.append(pts[0])
            face = Part.Face(Part.Wire(Part.makePolygon(pts)))
            holes.extend([(-rw_in - 15, rh_in + t/2, sw/2), (rw_in + 15, rh_in + t/2, sw/2)])

        elif h_type == "Half Z-Strap":
            pts = [
                App.Vector(-rw_in - 30, rh_in + 20 + t, 0),
                App.Vector(-rw_in, rh_in + 20 + t, 0),
                App.Vector(-rw_in, -rh_in, 0),
                App.Vector(rw_in, -rh_in, 0),
                App.Vector(rw_in, -rh_in - t, 0),
                App.Vector(-rw_in - t, -rh_in - t, 0),
                App.Vector(-rw_in - t, rh_in + 20, 0),
                App.Vector(-rw_in - 30, rh_in + 20, 0)
            ]
            pts.append(pts[0])
            face = Part.Face(Part.Wire(Part.makePolygon(pts)))
            holes.append((-rw_in - 15, rh_in + 20 + t/2, sw/2))

        final_shape = face.extrude(App.Vector(0, 0, sw))

        h_rad = b_dia / 2.0 
        for hp in holes:
            cyl = Part.makeCylinder(h_rad, t * 10, App.Vector(hp[0], hp[1] - (t*5), hp[2]), App.Vector(0, 1, 0))
            final_shape = final_shape.cut(cyl)

        final_shape.translate(App.Vector(0, 0, -sw/2.0))
        return final_shape.removeSplitter()

    def commit_fastener_array(self, final_compound, h_type, mat):
        doc = App.ActiveDocument
        doc.openTransaction("Generate Fastener Array")
        try:
            obj = doc.addObject("Part::Feature", f"{h_type.replace(' ', '_')}_Array")
            obj.Shape = final_compound
            
            # --- Auto-grouping logic ---
            if self.target_obj:
                parent_container = None
                for parent in self.target_obj.InList:
                    if parent.isDerivedFrom("PartDesign::Body") or parent.isDerivedFrom("App::Part") or parent.isDerivedFrom("App::DocumentObjectGroup"):
                        parent_container = parent
                        break
                
                if parent_container:
                    parent_container.addObject(obj)
                elif self.target_obj.isDerivedFrom("App::DocumentObjectGroup"):
                    self.target_obj.addObject(obj)
            # ---------------------------
            
            color = self.materials[mat]
            obj.ViewObject.ShapeColor = (color[0], color[1], color[2])
            
            doc.recompute()
            doc.commitTransaction()
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Generation Error", f"Failed to place fasteners:\n{str(e)}")

class CreateDuctFastenerCommand:
    def GetResources(self):
        return {'Pixmap': ComfacUtils.get_icon_path('DuctFasteners.svg') if 'ComfacUtils' in globals() else "", 'MenuText': "Array Duct Fasteners"}
        
    def extract_duct_data(self, selEx_obj):
        obj = selEx_obj.Object
        subs = selEx_obj.SubObjects
        doc = App.ActiveDocument

        def find_source(o):
            if hasattr(o, "DuctWidth") or hasattr(o, "SolidWidth") or hasattr(o, "PipeOuter") or hasattr(o, "SourceNetworks"): return o
            for p in o.InList:
                if hasattr(p, "DuctWidth") or hasattr(p, "SolidWidth") or hasattr(p, "PipeOuter") or hasattr(p, "SourceNetworks"): return p
            return None
        
        target_folder = find_source(obj)
        if not target_folder:
            return None

        w, h = 100.0, 100.0
        offset_val = 0.0
        sketch = None

        source = target_folder
        if hasattr(source, "SourceNetworks") and source.SourceNetworks:
            source = source.SourceNetworks[0]
            
        if hasattr(source, "DuctWidth"):
            w = float(source.DuctWidth)
            h = float(getattr(source, "DuctHeight", getattr(source, "DuctDepth", w)))
            alignment = getattr(source, "DuctAlignment", getattr(source, "Alignment", "Center"))
            if alignment == "Inner": offset_val = -(w / 2.0)
            elif alignment == "Outer": offset_val = (w / 2.0)
            sketch_name = getattr(source, "LinkedDuctSketchName", getattr(source, "SketchName", ""))
            sketch = doc.getObject(sketch_name) if sketch_name else None
        elif hasattr(source, "SolidWidth"):
            w = float(source.SolidWidth)
            h = float(getattr(source, "SolidDepth", w))
            alignment = getattr(source, "SolidAlignment", "Center")
            if alignment == "Inner": offset_val = -(w / 2.0)
            elif alignment == "Outer": offset_val = (w / 2.0)
            sketch_name = getattr(source, "LinkedSolidSketchName", "")
            sketch = doc.getObject(sketch_name) if sketch_name else None
        elif hasattr(source, "PipeOuter"):
            w = float(source.PipeOuter)
            h = w
            sketch_name = getattr(source, "LinkedPipeSketchName", getattr(source, "SketchName", ""))
            sketch = doc.getObject(sketch_name) if sketch_name else None

        # =========================================================
        # THE AUTO-ADOPT EXACT INSULATION SIZE LOGIC
        # =========================================================
        insulation_obj = None
        
        if hasattr(obj, "InsulatedWidth") or "Insulation" in obj.Name:
            insulation_obj = obj
        elif target_folder and hasattr(target_folder, "Group"):
            for child in target_folder.Group:
                if hasattr(child, "InsulatedWidth") or "Insulation" in child.Name:
                    insulation_obj = child
                    break
                    
        if insulation_obj:
            if hasattr(insulation_obj, "InsulatedWidth"):
                w = float(insulation_obj.InsulatedWidth)
                h = float(insulation_obj.InsulatedHeight)
            else:
                w += 50.0
                h += 50.0
        # =========================================================

        click_center = None
        if subs and hasattr(subs[0], "CenterOfMass"):
            click_center = subs[0].CenterOfMass
        elif hasattr(obj, "Shape") and hasattr(obj.Shape, "CenterOfMass"):
            click_center = obj.Shape.CenterOfMass
        elif hasattr(obj, "Shape") and hasattr(obj.Shape, "BoundBox"):
            click_center = obj.Shape.BoundBox.Center

        best_center = App.Vector(0,0,0)
        d_dir = App.Vector(1,0,0)
        max_len = 1000.0

        if sketch:
            sketch_normal = sketch.Placement.Rotation.multVec(App.Vector(0, 0, 1))
            edges = [e for e in sketch.Shape.Edges if e.Length > 0.001]
            lines = [e for e in edges if hasattr(e.Curve, 'TypeId') and 'GeomLine' in e.Curve.TypeId]

            if not lines:
                return w, h, 1000.0, App.Vector(1,0,0), App.Vector(0,0,0), target_folder

            if click_center and subs:
                min_dist = float('inf')
                for edge in lines:
                    p1 = edge.valueAt(edge.FirstParameter)
                    p2 = edge.valueAt(edge.LastParameter)
                    tangent = (p2 - p1).normalize()

                    if offset_val != 0.0:
                        X_dir = sketch_normal.cross(tangent).normalize()
                        shift = X_dir * offset_val
                        p1 = p1 + shift
                        p2 = p2 + shift

                    seg_center = (p1 + p2) / 2.0
                    dist = (seg_center - click_center).Length
                    
                    if dist < min_dist:
                        min_dist = dist
                        best_center = seg_center
                        d_dir = tangent
                        max_len = (p2 - p1).Length
            else:
                longest_edge = None
                curr_max = -1
                for edge in lines:
                    if edge.Length > curr_max:
                        curr_max = edge.Length
                        longest_edge = edge
                
                if longest_edge:
                    p1 = longest_edge.valueAt(longest_edge.FirstParameter)
                    p2 = longest_edge.valueAt(longest_edge.LastParameter)
                    tangent = (p2 - p1).normalize()
                    
                    if offset_val != 0.0:
                        X_dir = sketch_normal.cross(tangent).normalize()
                        shift = X_dir * offset_val
                        p1 = p1 + shift
                        p2 = p2 + shift
                        
                    best_center = (p1 + p2) / 2.0
                    d_dir = tangent
                    max_len = curr_max

        return w, h, max_len, d_dir, best_center, target_folder

    def Activated(self):
        selEx = FreeCADGui.Selection.getSelectionEx()
        if not selEx:
            QtWidgets.QMessageBox.warning(None, "Selection Error", "Please select a Smart Folder, Duct face, or Insulation.")
            return
            
        res = self.extract_duct_data(selEx[0])
        if not res:
            QtWidgets.QMessageBox.warning(None, "Selection Error", "Invalid selection. Please select a Duct/Solid/Pipe Folder, Merged Network, or Insulation.")
            return

        w, h, length, direction, center, target_obj = res
        panel = UniversalFastenerTaskPanel(w, h, length, direction, center, target_obj)
        FreeCADGui.Control.showDialog(panel)

try:
    FreeCADGui.addCommand('CreateDuctFastener', CreateDuctFastenerCommand())
except: pass