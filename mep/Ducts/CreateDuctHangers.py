import FreeCAD as App
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui

try:
    import ComfacUtils
except ImportError:
    pass

class UniversalHangerTaskPanel:
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

        self.preview = ComfacUtils.PreviewManager(App.ActiveDocument, "DuctHanger_Preview") if 'ComfacUtils' in globals() else None

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems([
            "Strut Hanger", "Trapeze Hanger", 
            "Round Wire Hanger", "Round Strap Hanger"
        ])

        self.mat_cb = QtWidgets.QComboBox()
        self.mat_cb.addItems(list(self.materials.keys()))
        
        # --- REPLACED INVERT WITH ROLL ALIGNMENT ---
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
        self.strap_w_input.setRange(1.0, 500.0); self.strap_w_input.setValue(41.0); self.strap_w_input.setSuffix(" mm")
        
        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.1, 20.0); self.thick_input.setValue(2.5); self.thick_input.setSuffix(" mm")

        self.bolt_input = QtWidgets.QDoubleSpinBox()
        self.bolt_input.setRange(1.0, 50.0); self.bolt_input.setValue(10.0); self.bolt_input.setSuffix(" mm")

        self.layout.addRow("Hanger Type:", self.type_cb)
        self.layout.addRow("Material:", self.mat_cb)
        self.layout.addRow("Roll Alignment:", self.roll_input)
        self.layout.addRow(QtWidgets.QLabel(""))
        self.layout.addRow("Detected Width:", self.w_input)
        self.layout.addRow("Detected Height:", self.h_input)
        self.layout.addRow(QtWidgets.QLabel(""))
        self.layout.addRow(QtWidgets.QLabel("<b>Array Settings</b>"))
        self.layout.addRow("Number of Hangers:", self.count_input)
        self.layout.addRow("Distance Between:", self.spacing_input)
        self.layout.addRow(QtWidgets.QLabel(""))
        self.layout.addRow("Material Thick:", self.thick_input)
        self.layout.addRow("Strut Width:", self.strap_w_input)
        self.layout.addRow("Threaded Rod Dia:", self.bolt_input)

        self.mat_cb.currentIndexChanged.connect(self.update_material)
        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.roll_input.valueChanged.connect(self.trigger_preview)
        self.w_input.valueChanged.connect(self.trigger_preview)
        self.h_input.valueChanged.connect(self.trigger_preview)
        self.count_input.valueChanged.connect(self.trigger_preview)
        self.spacing_input.valueChanged.connect(self.trigger_preview)
        self.thick_input.valueChanged.connect(self.trigger_preview)
        self.strap_w_input.valueChanged.connect(self.trigger_preview)
        self.bolt_input.valueChanged.connect(self.trigger_preview)

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
        count = self.count_input.value()
        spacing = self.spacing_input.value()
        array_length = (count - 1) * spacing
        roll_angle = self.roll_input.value()

        ghost_shape = self.build_array_geometry(h_type, w, h, t, sw, b_dia, count, spacing, array_length, roll_angle)
        if ghost_shape:
            self.preview.update(ghost_shape)

    def build_array_geometry(self, h_type, w, h, t, sw, b_dia, count, spacing, array_length, roll_angle):
        try:
            shapes = []
            start_pos = self.p_center - self.seg_dir * (array_length / 2.0)
            Z_local = self.seg_dir
            is_hanger = "Hanger" in h_type

            UP = App.Vector(0, 0, 1)
            if abs(Z_local.z) > 0.99:
                UP = App.Vector(0, 1, 0)

            # Calculate base orientation
            Y_base = UP - Z_local * UP.dot(Z_local)
            if Y_base.Length < 0.001: Y_base = App.Vector(1, 0, 0)
            Y_base.normalize()
            X_base = Y_base.cross(Z_local).normalize()

            # Apply Roll Angle
            roll_rot = App.Rotation(Z_local, roll_angle)
            X_local = roll_rot.multVec(X_base)
            Y_local = roll_rot.multVec(Y_base)

            for i in range(count):
                shape = self.get_hanger_shape(h_type, w, h, t, sw, b_dia)
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
        self.generate_hanger_array(h_type, mat, w, h, t, sw, b_dia, count, spacing, array_length, roll_angle)

    def reject(self):
        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def get_hanger_shape(self, h_type, duct_w, duct_h, t, sw, b_dia):
        clearance = 0.5
        rw_in = (duct_w / 2.0) + clearance
        rh_in = (duct_h / 2.0) + clearance
        holes = [] 
        face = None

        if h_type == "Strut Hanger":
            pts = [
                App.Vector(-rw_in, rh_in + 30, 0),
                App.Vector(-rw_in, -rh_in, 0),
                App.Vector(rw_in, -rh_in, 0),
                App.Vector(rw_in, rh_in + 30, 0),
                App.Vector(rw_in + t, rh_in + 30, 0),
                App.Vector(rw_in + t, -rh_in - t, 0),
                App.Vector(-rw_in - t, -rh_in - t, 0),
                App.Vector(-rw_in - t, rh_in + 30, 0)
            ]
            pts.append(pts[0])
            face = Part.Face(Part.Wire(Part.makePolygon(pts)))
            holes.extend([(-rw_in - t/2, rh_in + 15, sw/2), (rw_in + t/2, rh_in + 15, sw/2)])
            
            final_shape = face.extrude(App.Vector(0, 0, sw))

        elif h_type == "Trapeze Hanger":
            strut_height = 41.0
            strut_width = max(sw, 41.0)
            pad_h = 10.0
            
            rod_len = duct_h + pad_h + strut_height + 100.0 
            overhang = 40.0
            
            total_len = duct_w + (overhang * 2)
            half_L = total_len / 2.0
            
            strut_y_base = -rh_in - pad_h - strut_height
            
            base_strut = Part.makeBox(total_len, strut_height, strut_width, App.Vector(-half_L, strut_y_base, 0))
            
            inner_w = strut_width - (2*t)
            inner_h = strut_height - t
            ch_cut = Part.makeBox(total_len, inner_h, inner_w, App.Vector(-half_L, strut_y_base + t, t))
            
            slot_w = inner_w - (t * 4)
            slot_cut = Part.makeBox(total_len, t * 2, slot_w, App.Vector(-half_L, strut_y_base + strut_height - t, (strut_width - slot_w)/2))
            
            final_shape = base_strut.cut(ch_cut).cut(slot_cut)
            
            pad_w = duct_w * 0.8
            pad = Part.makeBox(pad_w, pad_h, strut_width, App.Vector(-pad_w/2, -rh_in - pad_h, 0))
            final_shape = final_shape.fuse(pad)
            
            rod_r = b_dia / 2.0
            rod_l = Part.makeCylinder(rod_r, rod_len, App.Vector(-half_L + 15, strut_y_base, strut_width/2), App.Vector(0, 1, 0))
            rod_r_obj = Part.makeCylinder(rod_r, rod_len, App.Vector(half_L - 15, strut_y_base, strut_width/2), App.Vector(0, 1, 0))
            
            washer = Part.makeCylinder(rod_r + 6, t, App.Vector(0,0,0), App.Vector(0,1,0))
            nut = Part.makeCylinder(rod_r + 4, t*2, App.Vector(0,0,0), App.Vector(0,1,0))
            
            w_l1 = washer.copy(); w_l1.translate(App.Vector(-half_L + 15, strut_y_base + strut_height, strut_width/2))
            w_l2 = washer.copy(); w_l2.translate(App.Vector(-half_L + 15, strut_y_base - t, strut_width/2))
            n_l1 = nut.copy(); n_l1.translate(App.Vector(-half_L + 15, strut_y_base + strut_height + t, strut_width/2))
            n_l2 = nut.copy(); n_l2.translate(App.Vector(-half_L + 15, strut_y_base - t - t*2, strut_width/2))
            
            w_r1 = washer.copy(); w_r1.translate(App.Vector(half_L - 15, strut_y_base + strut_height, strut_width/2))
            w_r2 = washer.copy(); w_r2.translate(App.Vector(half_L - 15, strut_y_base - t, strut_width/2))
            n_r1 = nut.copy(); n_r1.translate(App.Vector(half_L - 15, strut_y_base + strut_height + t, strut_width/2))
            n_r2 = nut.copy(); n_r2.translate(App.Vector(half_L - 15, strut_y_base - t - t*2, strut_width/2))

            final_shape = final_shape.fuse(rod_l).fuse(rod_r_obj)
            final_shape = final_shape.fuse(w_l1).fuse(w_l2).fuse(n_l1).fuse(n_l2)
            final_shape = final_shape.fuse(w_r1).fuse(w_r2).fuse(n_r1).fuse(n_r2)

        else: 
            rad_in = max(rw_in, rh_in)
            rad_out = rad_in + t
            if h_type == "Round Strap Hanger":
                arc_i = Part.Arc(App.Vector(-rad_in, 0, 0), App.Vector(0, -rad_in, 0), App.Vector(rad_in, 0, 0)).toShape()
                w_in = Part.Wire([arc_i, 
                                  Part.makeLine(App.Vector(rad_in, 0, 0), App.Vector(rad_in, rad_in + 20, 0)),
                                  Part.makeLine(App.Vector(rad_in, rad_in + 20, 0), App.Vector(-rad_in, rad_in + 20, 0)),
                                  Part.makeLine(App.Vector(-rad_in, rad_in + 20, 0), App.Vector(-rad_in, 0, 0))])
                
                arc_o = Part.Arc(App.Vector(-rad_out, 0, 0), App.Vector(0, -rad_out, 0), App.Vector(rad_out, 0, 0)).toShape()
                w_out = Part.Wire([arc_o,
                                   Part.makeLine(App.Vector(rad_out, 0, 0), App.Vector(rad_out + 30, 0, 0)),
                                   Part.makeLine(App.Vector(rad_out + 30, 0, 0), App.Vector(rad_out + 30, t, 0)),
                                   Part.makeLine(App.Vector(rad_out + 30, t, 0), App.Vector(rad_out, t, 0)),
                                   Part.makeLine(App.Vector(rad_out, t, 0), App.Vector(rad_out, rad_in + 20 + t, 0)),
                                   Part.makeLine(App.Vector(rad_out, rad_in + 20 + t, 0), App.Vector(-rad_out, rad_in + 20 + t, 0)),
                                   Part.makeLine(App.Vector(-rad_out, rad_in + 20 + t, 0), App.Vector(-rad_out, t, 0)),
                                   Part.makeLine(App.Vector(-rad_out, t, 0), App.Vector(-rad_out - 30, t, 0)),
                                   Part.makeLine(App.Vector(-rad_out - 30, t, 0), App.Vector(-rad_out - 30, 0, 0)),
                                   Part.makeLine(App.Vector(-rad_out - 30, 0, 0), App.Vector(-rad_out, 0, 0))])
                face = Part.Face(w_out).cut(Part.Face(w_in))
                holes.extend([(-rad_out - 15, t/2, sw/2), (rad_out + 15, t/2, sw/2)])
            else:
                w_in = Part.Wire(Part.makeCircle(rad_in, App.Vector(0,0,0), App.Vector(0,0,1)))
                w_out = Part.Wire(Part.makeCircle(rad_out, App.Vector(0,0,0), App.Vector(0,0,1)))
                face = Part.Face(w_out).cut(Part.Face(w_in))

            final_shape = face.extrude(App.Vector(0, 0, sw))

        h_rad = b_dia / 2.0 
        for hp in holes:
            if h_type == "Strut Hanger":
                cyl = Part.makeCylinder(h_rad, t * 10, App.Vector(hp[0] - (t*5), hp[1], hp[2]), App.Vector(1, 0, 0))
            else:
                cyl = Part.makeCylinder(h_rad, t * 10, App.Vector(hp[0], hp[1] - (t*5), hp[2]), App.Vector(0, 1, 0))
            final_shape = final_shape.cut(cyl)

        final_shape.translate(App.Vector(0, 0, -sw/2.0))
        return final_shape.removeSplitter()

    def generate_hanger_array(self, h_type, mat, w, h, t, sw, b_dia, count, spacing, array_length, roll_angle):
        doc = App.ActiveDocument
        doc.openTransaction("Generate Hanger Array")
        
        try:
            shapes = []
            start_pos = self.p_center - self.seg_dir * (array_length / 2.0)
            
            Z_local = self.seg_dir
            is_hanger = "Hanger" in h_type
            
            UP = App.Vector(0, 0, 1)
            if abs(Z_local.z) > 0.99: 
                UP = App.Vector(0, 1, 0)
                
            # Calculate base orientation
            Y_base = UP - Z_local * UP.dot(Z_local) 
            if Y_base.Length < 0.001: Y_base = App.Vector(1, 0, 0)
            Y_base.normalize()
            X_base = Y_base.cross(Z_local).normalize()

            # Apply Roll Angle
            roll_rot = App.Rotation(Z_local, roll_angle)
            X_local = roll_rot.multVec(X_base)
            Y_local = roll_rot.multVec(Y_base)
            
            for i in range(count):
                shape = self.get_hanger_shape(h_type, w, h, t, sw, b_dia)
                pt = start_pos + self.seg_dir * (spacing * i)
                
                mat_trans = App.Matrix(X_local.x, Y_local.x, Z_local.x, pt.x,
                                 X_local.y, Y_local.y, Z_local.y, pt.y,
                                 X_local.z, Y_local.z, Z_local.z, pt.z,
                                 0.0, 0.0, 0.0, 1.0)
                shape.transformShape(mat_trans)
                shapes.append(shape)
                
            final_compound = Part.makeCompound(shapes)
            obj = doc.addObject("Part::Feature", f"{h_type.replace(' ', '_')}_Array")
            obj.Shape = final_compound
            
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
            
            color = self.materials[mat]
            obj.ViewObject.ShapeColor = (color[0], color[1], color[2])
            
            doc.recompute()
            doc.commitTransaction()
            
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Generation Error", f"Failed to array hangers:\n{str(e)}")

class CreateDuctHangersCommand:
    def GetResources(self):
        return {'Pixmap': ComfacUtils.get_icon_path('DuctHangers.svg') if 'ComfacUtils' in globals() else "", 'MenuText': "Array Universal Hangers"}
        
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
        panel = UniversalHangerTaskPanel(w, h, length, direction, center, target_obj)
        FreeCADGui.Control.showDialog(panel)

try:
    FreeCADGui.addCommand('CreateDuctHangers', CreateDuctHangersCommand())
except: pass