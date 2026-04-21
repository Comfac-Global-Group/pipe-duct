import FreeCAD as App
import FreeCADGui
import Part
import math
import json
import os
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils

class DetailedFMCFittingsTaskPanel:
    def __init__(self):
        json_path = os.path.join(os.path.dirname(__file__), "..", "data", "FlexibleMetalConduitData.json")
        with open(json_path, 'r') as f:
            data = json.load(f)
        self.sizes = data["FMC"]

        self.fittings = [
            "STRAIGHT (ST) SQUEEZE CONNECTOR"
        ]

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.preview = ComfacUtils.PreviewManager(App.ActiveDocument, "DetailedFMC_Preview")

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(self.fittings)

        self.size_cb = QtWidgets.QComboBox()
        self.size_cb.addItems(list(self.sizes.keys()))

        self.layout.addRow("Fitting Type:", self.type_cb)
        self.layout.addRow("Trade Size:", self.size_cb)

        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.size_cb.currentIndexChanged.connect(self.trigger_preview)
        self.trigger_preview()

    def trigger_preview(self):
        try:
            size_label = self.size_cb.currentText()
            if size_label in self.sizes:
                D = self.sizes[size_label]
                ghost_shape = self.make_squeeze_connector(D)
                if ghost_shape:
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
        doc = App.ActiveDocument or App.newDocument("Detailed_FMC_Fittings")
        
        shape = self.make_squeeze_connector(D)

        # Clean output name for the FreeCAD tree
        feat_name = f"FMC_ST_{size_label.replace(' ', '_').replace('/', '_')}"
        obj = doc.addObject("Part::Feature", feat_name)
        obj.Shape = shape.removeSplitter()
        
        # Apply standard die-cast zinc/silver color
        if hasattr(obj, "ViewObject"):
            obj.ViewObject.ShapeColor = (0.85, 0.85, 0.88)
            
        doc.recompute()

    # --- GEOMETRY HELPERS ---

    def make_hex_prism(self, radius, height, pos):
        """Creates a solid hexagonal prism for locknuts"""
        pts = []
        for i in range(7):
            angle = math.radians(i * 60)
            pts.append(App.Vector(radius * math.cos(angle), radius * math.sin(angle), 0))
            
        poly = Part.makePolygon(pts)
        face = Part.Face(poly)
        prism = face.extrude(App.Vector(0, 0, height))
        prism.translate(pos)
        return prism

    # --- FITTING GENERATORS ---

    def make_squeeze_connector(self, D):
        """Generates a detailed ST Flexible Metal Conduit (FMC) Squeeze Connector"""
        r_in = D * 0.35      
        r_thread = D * 0.45  
        r_stop = D * 0.55    # Smooth ring before ribs
        r_ribbed = D * 0.65  # Ribbed body radius
        r_collar = D * 0.55  # Top receiving split collar
        
        H_thread = max(15.0, D * 0.4)
        H_lock = max(4.0, D * 0.15)
        H_stop = D * 0.08
        H_ribbed = D * 0.3
        H_collar = D * 0.6

        # 1. Base Locknut (Thin Hex on threads)
        locknut = self.make_hex_prism(D * 0.7, H_lock, App.Vector(0, 0, -D * 0.2))
        
        # 2. Main Thread (Goes into the junction box)
        thread = Part.makeCylinder(r_thread, H_thread, App.Vector(0, 0, -H_thread))
        
        # 3. Stop Flange (Smooth ring right after thread)
        stop_flange = Part.makeCylinder(r_stop, H_stop, App.Vector(0, 0, 0))
        
        # 4. Ribbed Main Body (Die-cast teeth around circumference)
        rib_core = Part.makeCylinder(r_ribbed * 0.9, H_ribbed, App.Vector(0, 0, H_stop))
        body = rib_core
        for i in range(16): # 16 ribs around the body
            angle = math.radians(i * 22.5)
            cx = (r_ribbed * 0.9) * math.cos(angle)
            cy = (r_ribbed * 0.9) * math.sin(angle)
            rib = Part.makeCylinder(D * 0.04, H_ribbed, App.Vector(cx, cy, H_stop))
            body = body.fuse(rib)
            
        # 5. Top Split Collar
        Z_collar = H_stop + H_ribbed
        collar_base = Part.makeCylinder(r_collar, H_collar, App.Vector(0, 0, Z_collar))
        
        # Cut the wide slit to make it a C-clamp
        slit = Part.makeBox(D, D * 0.3, H_collar + 2.0, App.Vector(0, -D * 0.15, Z_collar - 1.0))
        collar = collar_base.cut(slit)
        
        # 6. Squeeze Ears (Protruding clamping tabs)
        Z_ear = Z_collar + H_collar * 0.5
        
        # Top Ear (+Y direction)
        ear1_cyl = Part.makeCylinder(D * 0.25, D * 0.12, App.Vector(D * 0.75, D * 0.15, Z_ear), App.Vector(0, 1, 0))
        ear1_box = Part.makeBox(D * 0.3, D * 0.12, D * 0.5, App.Vector(D * 0.45, D * 0.15, Z_ear - D * 0.25))
        
        # Bottom Ear (-Y direction)
        ear2_cyl = Part.makeCylinder(D * 0.25, D * 0.12, App.Vector(D * 0.75, -D * 0.27, Z_ear), App.Vector(0, 1, 0))
        ear2_box = Part.makeBox(D * 0.3, D * 0.12, D * 0.5, App.Vector(D * 0.45, -D * 0.27, Z_ear - D * 0.25))

        # 7. Clamping Screw
        screw_head = Part.makeCylinder(D * 0.18, D * 0.1, App.Vector(D * 0.75, D * 0.27, Z_ear), App.Vector(0, 1, 0))
        screw_shaft = Part.makeCylinder(D * 0.08, D * 0.8, App.Vector(D * 0.75, D * 0.27, Z_ear), App.Vector(0, -1, 0))
        
        # Cut a flathead slot into the screw head for extreme realism
        slot = Part.makeBox(D * 0.4, D * 0.04, D * 0.04, App.Vector(D * 0.55, D * 0.35, Z_ear - D * 0.02))
        screw_head = screw_head.cut(slot)

        # Iteratively fuse all outer components to ensure safety across older FreeCAD versions
        outer = thread
        components = [locknut, stop_flange, body, collar, ear1_cyl, ear1_box, ear2_cyl, ear2_box, screw_head, screw_shaft]
        for comp in components:
            outer = outer.fuse(comp)

        # 8. Hollow out the center for the wires
        hollow = Part.makeCylinder(r_in, H_thread + H_stop + H_ribbed + H_collar + 10.0, App.Vector(0, 0, -H_thread - 5.0))
        
        return outer.cut(hollow)

# Command Registration for Toolbar
import ComfacUtils

class CreateDetailedFMC:
    def GetResources(self):
        icon_path = ComfacUtils.get_icon_path('FMC.svg') or ComfacUtils.get_icon_path('Part_Feature.svg')
        return {
            'Pixmap': icon_path, 
            'MenuText': "Generate Detailed FMC Fitting", 
            'ToolTip': "Create highly detailed FMC Squeeze Connectors"
        }
    def Activated(self):
        FreeCADGui.Control.showDialog(DetailedFMCFittingsTaskPanel())

try:
    FreeCADGui.addCommand('CreateDetailedFMC', CreateDetailedFMC())
except Exception as e:
    App.Console.PrintError(f"Failed to load command: {str(e)}\n")