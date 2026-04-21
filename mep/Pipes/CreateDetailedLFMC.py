import FreeCAD as App
import FreeCADGui
import Part
import math
import json
import os
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils

class DetailedLFMCTaskPanel:
    def __init__(self):
        json_path = os.path.join(os.path.dirname(__file__), "..", "data", "FlexibleMetalConduitData.json")
        with open(json_path, 'r') as f:
            data = json.load(f)
        self.sizes = data["LFMC"]

        self.fittings = [
            "ST CONNECTOR (LIQUID TIGHT)",
            "90 DEGREE ANGLE CONNECTOR (LIQUID TIGHT)"
        ]

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.preview = ComfacUtils.PreviewManager(App.ActiveDocument, "DetailedLFMC_Preview")

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(self.fittings)

        self.size_cb = QtWidgets.QComboBox()
        self.size_cb.addItems(list(self.sizes.keys()))

        self.layout.addRow("Fitting Type:", self.type_cb)
        self.layout.addRow("Trade Size:", self.size_cb)
        
        self.target_placement = self.get_placement_from_selection()

        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.size_cb.currentIndexChanged.connect(self.trigger_preview)
        self.trigger_preview()

    def get_placement_from_selection(self):
        sel = FreeCADGui.Selection.getSelectionEx()
        if not sel:
            return App.Placement() 
            
        for sel_obj in sel:
            if sel_obj.HasSubObjects:
                for sub in sel_obj.SubObjects:
                    if isinstance(sub, Part.Face):
                        center = sub.CenterOfMass
                        u_min, u_max, v_min, v_max = sub.ParameterRange
                        u = (u_min + u_max) / 2.0
                        v = (v_min + v_max) / 2.0
                        normal = sub.normalAt(u, v)
                        rot = App.Rotation(App.Vector(0,0,1), normal)
                        return App.Placement(center, rot)
                        
        return App.Placement()

    def trigger_preview(self):
        try:
            f_type = self.type_cb.currentText()
            size_label = self.size_cb.currentText()
            if size_label in self.sizes:
                D = self.sizes[size_label]
                if "ST CONNECTOR" in f_type:
                    ghost_shape = self.make_straight_connector(D)
                else:
                    ghost_shape = self.make_angle_connector(D)
                if ghost_shape:
                    ghost_shape.Placement = self.target_placement
                    self.preview.update(ghost_shape)
        except:
            pass

    def accept(self):
        f_type = self.type_cb.currentText()
        size_label = self.size_cb.currentText()
        D = self.sizes[size_label]

        self.preview.clear()
        FreeCADGui.Control.closeDialog()
        self.generate(f_type, size_label, D)

    def reject(self):
        self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def generate(self, f_type, size_label, D):
        doc = App.ActiveDocument or App.newDocument("LFMC_Fittings")
        
        if "ST CONNECTOR" in f_type:
            shape = self.make_straight_connector(D)
        else:
            shape = self.make_angle_connector(D)

        feat_name = f"LFMC_{f_type[:2]}_{size_label.replace(' ', '_').replace('/', '_')}"
        obj = doc.addObject("Part::Feature", feat_name)
        obj.Shape = shape.removeSplitter()
        
        obj.Placement = self.target_placement
        
        if hasattr(obj, "ViewObject"):
            obj.ViewObject.ShapeColor = (0.80, 0.82, 0.85)
            
        doc.recompute()

    def make_hex_prism(self, radius, height, pos, direction=App.Vector(0,0,1)):
        pts = []
        for i in range(7):
            angle = math.radians(i * 60)
            pts.append(App.Vector(radius * math.cos(angle), radius * math.sin(angle), 0))
            
        poly = Part.makePolygon(pts)
        face = Part.Face(poly)
        prism = face.extrude(App.Vector(0, 0, height))
        
        if direction.x == 1:
            prism.rotate(App.Vector(0,0,0), App.Vector(0,1,0), 90)
            
        prism.translate(pos)
        return prism

    def make_straight_connector(self, D):
        r_in = D * 0.32          
        r_throat_in = D * 0.38   
        r_throat_out = D * 0.42  
        r_thread = D * 0.48      
        r_ring = D * 0.60        
        r_hex_lock = D * 0.70    
        r_hex_base = D * 0.65    
        r_hex_nut = D * 0.72     
        
        h_thread = max(15.0, D * 0.3)
        h_lock = max(4.0, D * 0.12)
        h_ring = max(2.0, D * 0.08)
        h_base_hex = D * 0.35
        h_nut = D * 0.40
        h_taper = D * 0.15

        thread = Part.makeCylinder(r_thread, h_thread, App.Vector(0, 0, -h_thread))
        locknut = self.make_hex_prism(r_hex_lock, h_lock, App.Vector(0, 0, 0))
        ring = Part.makeCylinder(r_ring, h_ring, App.Vector(0, 0, h_lock))
        
        base_hex_z = h_lock + h_ring
        base_cyl = Part.makeCylinder(r_hex_base * 0.95, D * 0.05, App.Vector(0, 0, base_hex_z))
        base_hex = self.make_hex_prism(r_hex_base, h_base_hex, App.Vector(0, 0, base_hex_z + D * 0.05))
        
        z_nut = base_hex_z + D * 0.05 + h_base_hex
        gap = Part.makeCylinder(r_thread, D * 0.05, App.Vector(0, 0, z_nut))
        z_nut += D * 0.05
        
        nut = self.make_hex_prism(r_hex_nut, h_nut, App.Vector(0, 0, z_nut))
        
        z_taper = z_nut + h_nut
        taper = Part.makeCone(r_hex_nut * 0.866, r_throat_out + 2, h_taper, App.Vector(0, 0, z_taper))
        
        outer = thread
        for comp in [locknut, ring, base_cyl, base_hex, gap, nut, taper]:
            outer = outer.fuse(comp)

        # Extended main central hollow to guarantee it clears both ends
        hollow_center = Part.makeCylinder(r_throat_in, h_thread + z_taper + h_taper + D + 10, App.Vector(0, 0, -h_thread - 5))
        
        conduit_gap_depth = h_nut + h_taper + D * 0.1
        ferrule_length = D * 0.15 
        
        # Outer gap cutter extended to +5 to clear flush surfaces
        conduit_gap_cutter_out = Part.makeCylinder(r_hex_nut * 0.8, conduit_gap_depth + 5.0, App.Vector(0, 0, z_nut - D * 0.1))
        
        # Inner ferrule cutter stops early, resulting in a hollow entry nut instead of a ferrule that spans the whole length
        cut_in_len = D * 0.1 + ferrule_length + 2.0
        conduit_gap_cutter_in = Part.makeCylinder(r_throat_out, cut_in_len, App.Vector(0, 0, z_nut - D * 0.1 - 2.0))
        
        annular_cut = conduit_gap_cutter_out.cut(conduit_gap_cutter_in)

        final_shape = outer.cut(hollow_center).cut(annular_cut)
        return final_shape

    def make_angle_connector(self, D):
        r_in = D * 0.32          
        r_throat_in = D * 0.38   
        r_throat_out = D * 0.42  
        r_thread = D * 0.48      
        r_ring = D * 0.60        
        r_hex_lock = D * 0.70    
        r_hex_base = D * 0.65    
        r_hex_nut = D * 0.72     
        r_elbow = D * 0.55
        
        h_thread = max(15.0, D * 0.3)
        h_lock = max(4.0, D * 0.12)
        h_ring = max(2.0, D * 0.08)
        h_base_hex = D * 0.35
        h_nut = D * 0.40
        h_taper = D * 0.15
        
        bend_radius = D * 1.0 

        thread = Part.makeCylinder(r_thread, h_thread, App.Vector(0, 0, -h_thread))
        locknut = self.make_hex_prism(r_hex_lock, h_lock, App.Vector(0, 0, 0))
        ring = Part.makeCylinder(r_ring, h_ring, App.Vector(0, 0, h_lock))
        
        base_hex_z = h_lock + h_ring
        base_hex = self.make_hex_prism(r_hex_base, h_base_hex, App.Vector(0, 0, base_hex_z))

        z_start_bend = base_hex_z + h_base_hex
        face_wire = Part.Wire(Part.makeCircle(r_elbow, App.Vector(0, 0, z_start_bend), App.Vector(0, 0, 1)))
        elbow = Part.Face(face_wire).revolve(App.Vector(bend_radius, 0, z_start_bend), App.Vector(0, 1, 0), 90)

        pos_x = bend_radius
        pos_z = z_start_bend + bend_radius
        end_pos = App.Vector(pos_x, 0, pos_z)
        
        step = Part.makeCylinder(r_elbow, D * 0.05, end_pos, App.Vector(1, 0, 0))
        
        pos_nut = end_pos + App.Vector(D * 0.05, 0, 0)
        nut = self.make_hex_prism(r_hex_nut, h_nut, pos_nut, App.Vector(1, 0, 0))
        
        pos_taper = pos_nut + App.Vector(h_nut, 0, 0)
        taper = Part.makeCone(r_hex_nut * 0.866, r_throat_out + 2, h_taper, pos_taper, App.Vector(1, 0, 0))

        outer = thread
        for comp in [locknut, ring, base_hex, elbow, step, nut, taper]:
            outer = outer.fuse(comp)

        # FIX 1: Extended length to correctly punch completely through the base
        hollow_z = Part.makeCylinder(r_throat_in, h_thread + z_start_bend + 10, App.Vector(0, 0, -h_thread - 5))
        
        in_face_wire = Part.Wire(Part.makeCircle(r_throat_in, App.Vector(0, 0, z_start_bend), App.Vector(0, 0, 1)))
        hollow_bend = Part.Face(in_face_wire).revolve(App.Vector(bend_radius, 0, z_start_bend), App.Vector(0, 1, 0), 90)
        
        # FIX 2: Extended length to push cleanly through the nut/taper horizontal section
        hollow_x = Part.makeCylinder(r_throat_in, h_nut + h_taper + D + 10, end_pos + App.Vector(-5, 0, 0), App.Vector(1, 0, 0))

        conduit_gap_depth = h_nut + h_taper + D * 0.1
        ferrule_length = D * 0.15 
        
        # FIX 3: Extended gap cut by +5 and shortened the inner ferrule. 
        # This completely hollows out the entrance of the nut, leaving just the short ferrule at the base
        cut_out = Part.makeCylinder(r_hex_nut * 0.8, conduit_gap_depth + 5.0, pos_nut - App.Vector(D * 0.1, 0, 0), App.Vector(1, 0, 0))
        
        cut_in_len = D * 0.1 + ferrule_length + 2.0
        cut_in = Part.makeCylinder(r_throat_out, cut_in_len, pos_nut - App.Vector(D * 0.1 + 2.0, 0, 0), App.Vector(1, 0, 0))
        
        annular_cut = cut_out.cut(cut_in)

        final_shape = outer.cut(hollow_z).cut(hollow_bend).cut(hollow_x).cut(annular_cut)
        return final_shape

class CreateDetailedLFMC:
    def GetResources(self):
        icon_path = ComfacUtils.get_icon_path('LFMC.svg') or ComfacUtils.get_icon_path('Part_Feature.svg')
        return {
            'Pixmap': icon_path, 
            'MenuText': "Generate LFMC Fittings", 
            'ToolTip': "Create Photorealistic LFMC Connectors"
        }
    def Activated(self):
        FreeCADGui.Control.showDialog(DetailedLFMCTaskPanel())

try:
    FreeCADGui.addCommand('CreateDetailedLFMC', CreateDetailedLFMC())
except Exception:
    pass

if __name__ == "__main__":
    FreeCADGui.Control.showDialog(DetailedLFMCTaskPanel())