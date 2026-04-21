import FreeCAD as App
import FreeCADGui
import Part
import math
import json
import os
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils

# ==========================================================
# PHOTOREALISTIC CONDUIT LOCKNUT GENERATOR V3
# ==========================================================
class ConduitLocknutTaskPanel:
    def __init__(self, detected_radius=None, placement=None):
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)
        self.detected_radius = detected_radius
        self.target_placement = placement

        self.preview = ComfacUtils.PreviewManager(App.ActiveDocument, "Locknut_Preview")
        
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "PipeLocknutData.json")
        with open(data_path, 'r') as f:
            self.conduit_data = json.load(f)
        
        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(list(self.conduit_data.keys()))
        self.size_cb = QtWidgets.QComboBox()
        
        self.thickness_input = QtWidgets.QDoubleSpinBox()
        self.thickness_input.setRange(1.0, 30.0)
        self.thickness_input.setValue(3.0)
        self.thickness_input.setSuffix(" mm")
        
        self.layout.addRow("Locknut Type:", self.type_cb)
        self.layout.addRow("Trade Size:", self.size_cb)
        self.layout.addRow("Nut Thickness:", self.thickness_input)
        
        self.type_cb.currentTextChanged.connect(self.update_sizes_dropdown)
        self.size_cb.currentIndexChanged.connect(self.trigger_preview)
        self.thickness_input.valueChanged.connect(self.trigger_preview)
        self.update_sizes_dropdown(self.type_cb.currentText())
        self.trigger_preview()

    def update_sizes_dropdown(self, val_type):
        self.size_cb.clear()
        if val_type in self.conduit_data:
            self.size_cb.addItems(list(self.conduit_data[val_type].keys()))

            if "PVC" in val_type:
                self.thickness_input.setValue(8.0)
            elif "Compression" in val_type:
                self.thickness_input.setValue(5.0)
            else:
                self.thickness_input.setValue(3.0)
        self.trigger_preview()

    def trigger_preview(self):
        try:
            ctype = self.type_cb.currentText()
            csize = self.size_cb.currentText()
            thickness = self.thickness_input.value()
            pipe_od = self.detected_radius * 2.0 if self.detected_radius else self.conduit_data[ctype][csize][0]
            ghost_shape = self.build_geometry(ctype, pipe_od, thickness)
            if ghost_shape:
                self.preview.update(ghost_shape)
        except:
            pass

    def build_geometry(self, ctype, pipe_od, thickness):
        try:
            pos = App.Vector(0,0,0)
            direction = App.Vector(0,0,1)
            if self.target_placement:
                direction = self.target_placement.Rotation.multVec(App.Vector(0,0,1))
                pos = self.target_placement.Base

            R_outer = pipe_od / 2.0
            R_inner = R_outer - 2.0

            from ComfacUtils import TOLERANCE

            if "PVC" in ctype:
                R_outer += 6.0
                body = Part.makeCylinder(R_outer, thickness, pos, direction)
                bore = Part.makeCylinder(R_inner, thickness + 2, pos - direction, direction)
                body = body.cut(bore)
                return body.removeSplitter()
            else:
                R_outer += 3.0
                body = Part.makeCylinder(R_outer, thickness, pos, direction)
                bore = Part.makeCylinder(R_inner, thickness + 2, pos - direction, direction)
                body = body.cut(bore)
                return body.removeSplitter()
        except:
            return None

    def accept(self):
        ctype = self.type_cb.currentText()
        csize = self.size_cb.currentText()
        thickness = self.thickness_input.value()
        pipe_od = self.detected_radius * 2.0 if self.detected_radius else self.conduit_data[ctype][csize][0]

        self.preview.clear()
        FreeCADGui.Control.closeDialog()
        self.generate_locknut(ctype, pipe_od, thickness)
        return True

    def reject(self):
        self.preview.clear()
        FreeCADGui.Control.closeDialog()
        return True

    # --- GEOMETRY HELPERS ---

    def make_trapezoid_tab(self, R_inner, R_outer, W_base, W_tip, thickness):
        """Draws a 2D trapezoid and extrudes it to create highly realistic tabs."""
        p1 = App.Vector(R_inner, -W_base/2.0, 0)
        p2 = App.Vector(R_outer, -W_tip/2.0, 0)
        p3 = App.Vector(R_outer, W_tip/2.0, 0)
        p4 = App.Vector(R_inner, W_base/2.0, 0)
        
        wire = Part.makePolygon([p1, p2, p3, p4, p1])
        face = Part.Face(wire)
        return face.extrude(App.Vector(0, 0, thickness))

    def add_threads(self, body, R_in, thickness, pos, dir_v):
        """Adds internal helical ridges to simulate threads."""
        threads = []
        num_threads = max(3, int(thickness / 1.5))
        pitch = thickness / (num_threads + 1)
        
        for j in range(num_threads):
            z_offset = (j + 1) * pitch
            t = Part.makeTorus(R_in, 0.4, pos + dir_v * z_offset, dir_v)
            threads.append(t)
            
        if threads:
            t_comp = threads[0]
            for i in range(1, len(threads)):
                t_comp = t_comp.fuse(threads[i])
            body = body.fuse(t_comp)
        return body

    # --- SPECIFIC FACTORY GENERATORS (MATCHING PHOTOS) ---

    def build_pvc_locknut(self, D, thickness, pos, dir_v, color):
        """PHOTO 1: Flanged Hex Nut (Orange)"""
        R_in = D / 2.0
        R_hex = R_in + max(6.0, D * 0.2)
        R_flange = R_hex * 1.25
        
        flange_t = max(2.0, thickness * 0.35)
        hex_t = thickness - flange_t
        
        # 1. Base Flange
        flange = Part.makeCylinder(R_flange, flange_t, pos, dir_v)
        
        # 2. Hex Top
        pts = []
        for i in range(6):
            angle = math.radians(i * 60)
            pts.append(App.Vector(R_hex * math.cos(angle), R_hex * math.sin(angle), 0))
        pts.append(pts[0]) 
        wire = Part.Wire([Part.makeLine(pts[i], pts[i+1]) for i in range(6)])
        hex_nut = Part.Face(wire).extrude(App.Vector(0, 0, hex_t))
        hex_nut.Placement = App.Placement(pos + dir_v * flange_t, App.Rotation(dir_v, 0))
        
        # 3. Combine & Bore
        body = flange.fuse(hex_nut)
        bore = Part.makeCylinder(R_in, thickness + 2.0, pos - dir_v, dir_v)
        body = body.cut(bore)
        body = self.add_threads(body, R_in, thickness, pos, dir_v)
        
        return [("PVC_Flange_Nut", body, color)]

    def build_stamped_locknut(self, D, thickness, pos, dir_v, color):
        """PHOTO 2: Thin Stamped Steel Ring with 8 Narrow Trapezoid Tabs"""
        R_in = D / 2.0
        R_valley = R_in + max(3.0, D * 0.08)
        R_out = R_in + max(6.0, D * 0.22)
        
        num_tabs = 8
        W_base = max(4.0, D * 0.15)
        W_tip = max(3.0, D * 0.10)
        
        # 1. Base inner ring
        body = Part.makeCylinder(R_valley, thickness, pos, dir_v)
        
        # 2. Add 8 tapered tabs
        tabs = []
        for i in range(num_tabs):
            tab = self.make_trapezoid_tab(R_valley - 0.5, R_out, W_base, W_tip, thickness)
            rot = App.Rotation(App.Vector(0,0,1), i * (360.0/num_tabs))
            tab.Placement = App.Placement(App.Vector(0,0,0), rot)
            tabs.append(tab)
            
        for tab in tabs:
            # Align tabs with final position/direction
            tab.Placement = App.Placement(pos, App.Rotation(App.Vector(0,0,1), dir_v)).multiply(tab.Placement)
            body = body.fuse(tab)
            
        # 3. Bore & Threads
        bore = Part.makeCylinder(R_in, thickness + 2.0, pos - dir_v, dir_v)
        body = body.cut(bore)
        body = self.add_threads(body, R_in, thickness, pos, dir_v)
        
        return [("Stamped_Locknut", body, color)]

    def build_cast_locknut(self, D, thickness, pos, dir_v, color):
        """PHOTO 3: Thick Die-Cast Zinc Ring with 6 Chunky Lugs"""
        R_in = D / 2.0
        R_valley = R_in + max(4.0, D * 0.12)
        R_out = R_in + max(8.0, D * 0.28)
        
        num_tabs = 6
        W_base = max(6.0, D * 0.25) # Much wider base than stamped
        W_tip = max(4.0, D * 0.15)
        
        # 1. Base inner ring
        body = Part.makeCylinder(R_valley, thickness, pos, dir_v)
        
        # 2. Add 6 chunky tapered lugs
        tabs = []
        for i in range(num_tabs):
            tab = self.make_trapezoid_tab(R_valley - 0.5, R_out, W_base, W_tip, thickness)
            rot = App.Rotation(App.Vector(0,0,1), i * (360.0/num_tabs))
            tab.Placement = App.Placement(App.Vector(0,0,0), rot)
            tabs.append(tab)
            
        for tab in tabs:
            tab.Placement = App.Placement(pos, App.Rotation(App.Vector(0,0,1), dir_v)).multiply(tab.Placement)
            body = body.fuse(tab)
            
        # 3. Bore & Threads
        bore = Part.makeCylinder(R_in, thickness + 2.0, pos - dir_v, dir_v)
        body = body.cut(bore)
        body = self.add_threads(body, R_in, thickness, pos, dir_v)
        
        return [("Cast_Compression_Nut", body, color)]

    # --- MAIN GENERATOR ROUTER ---

    def generate_locknut(self, ctype, pipe_od, thickness):
        doc = App.ActiveDocument
        if not doc:
            doc = App.newDocument("Conduit_Locknuts")
            
        pos = App.Vector(0,0,0)
        direction = App.Vector(0,0,1)

        if self.target_placement:
            direction = self.target_placement.Rotation.multVec(App.Vector(0,0,1))
            pos = self.target_placement.Base

        parts = []
        if "PVC" in ctype:
            # PHOTO 1: Bright Safety Orange
            col_orange = (1.0, 0.4, 0.0) 
            parts = self.build_pvc_locknut(pipe_od, thickness, pos, direction, col_orange)
        elif "Stamped" in ctype:
            # PHOTO 2: Shiny Silver/Zinc
            col_galv = (0.88, 0.90, 0.92)
            parts = self.build_stamped_locknut(pipe_od, thickness, pos, direction, col_galv)
        elif "Compression" in ctype:
            # PHOTO 3: Matte Grey Die-Cast
            col_cast = (0.65, 0.67, 0.70)
            parts = self.build_cast_locknut(pipe_od, thickness, pos, direction, col_cast)

        doc.openTransaction("Add Conduit Locknut")
        
        obj = doc.addObject("Part::Feature", ctype.split("(")[0].strip().replace(" ", "_"))
        
        compound_shapes = []
        face_colors = []
        for name, shape, color in parts:
            compound_shapes.append(shape)
            face_colors.extend([color] * len(shape.Faces))
            
        obj.Shape = Part.makeCompound(compound_shapes).removeSplitter()
        
        if hasattr(obj, "ViewObject"):
            obj.ViewObject.DiffuseColor = face_colors
            obj.ViewObject.LineColor = (0.2, 0.2, 0.2)
            obj.ViewObject.DisplayMode = "Shaded"
        
        doc.recompute()
        doc.commitTransaction()

# ==========================================================
# COMMAND REGISTRATION
# ==========================================================
import ComfacUtils
class CreatePipeLocknut:
    def GetResources(self):
        return {
            'Pixmap' : ComfacUtils.get_icon_path("Locknut.svg"),
            'MenuText': "Pipe Locknut",
            'ToolTip': "Create highly realistic PVC, Stamped, or Cast locknuts"
        }

    def Activated(self):
        sel = FreeCADGui.Selection.getSelectionEx()
        detected_r = None
        target_place = None

        if sel and sel[0].HasSubObjects:
            face = sel[0].SubObjects[0]
            if isinstance(face, Part.Face):
                for edge in face.Edges:
                    if hasattr(edge.Curve, "Radius"):
                        detected_r = edge.Curve.Radius
                        break
                
                center = face.CenterOfMass
                uv = face.Surface.parameter(center)
                normal = face.normalAt(uv[0], uv[1])
                target_place = App.Placement(center, App.Rotation(App.Vector(0,0,1), normal))

        panel = ConduitLocknutTaskPanel(detected_r, target_place)
        FreeCADGui.Control.showDialog(panel)

FreeCADGui.addCommand('CreatePipeLocknut', CreatePipeLocknut())