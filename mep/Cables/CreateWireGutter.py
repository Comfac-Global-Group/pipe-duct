import FreeCAD as App
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui

# Safely import ComfacUtils
try:
    import ComfacUtils
except ImportError:
    ComfacUtils = None

class DetailedWireGutterTaskPanel:
    def __init__(self):
        # Specified Dimensions
        self.lengths = [2400]
        self.widths = [150, 300]
        self.depths = [150, 300]
        
        self.components = [
            "NEMA 4X HINGED WIREWAY (OPEN)",
            "NEMA 4X HINGED WIREWAY (CLOSED)"
        ]

        self.doc = App.ActiveDocument
        self.preview_obj = None
        
        # --- INITIALIZE LIVE PREVIEW MANAGER ---
        self.preview_manager = None
        if ComfacUtils and hasattr(ComfacUtils, 'PreviewManager'):
            self.preview_manager = ComfacUtils.PreviewManager(self.doc) 
            if hasattr(self.preview_manager, 'init'):
                try:
                    self.preview_manager.init(self.doc, "Wire_Gutter_Preview")
                except TypeError:
                    self.preview_manager.init("Wire_Gutter_Preview")
        # ---------------------------------------

        # Setup Task Panel Form
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        # UI Elements
        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(self.components)
        
        self.length_cb = QtWidgets.QComboBox()
        self.length_cb.addItems([f"{l} MM" for l in self.lengths] + ["Custom"])

        self.custom_length = QtWidgets.QDoubleSpinBox()
        self.custom_length.setRange(1.0, 10000.0)
        self.custom_length.setValue(2400.0)
        self.custom_length.setSuffix(" mm")

        self.width_cb = QtWidgets.QComboBox()
        self.width_cb.addItems([f"{w} MM" for w in self.widths])

        self.depth_cb = QtWidgets.QComboBox()
        self.depth_cb.addItems([f"{d} MM" for d in self.depths])

        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(1.0, 10.0)
        self.thick_input.setValue(2.0)
        self.thick_input.setSuffix(" mm")

        # Layout Assembly
        self.layout.addRow("Enclosure Type:", self.type_cb)
        self.layout.addRow("Standard Length:", self.length_cb)
        self.layout.addRow("Custom Length:", self.custom_length)
        self.layout.addRow("Gutter Width:", self.width_cb)
        self.layout.addRow("Gutter Depth:", self.depth_cb)
        self.layout.addRow("Sheet Thickness:", self.thick_input)

        # Connect UI logic
        self.length_cb.currentIndexChanged.connect(self.update_ui)
        
        # --- HOOK UI CHANGES TO THE LIVE PREVIEW ---
        self.type_cb.currentIndexChanged.connect(self.update_preview)
        self.custom_length.valueChanged.connect(self.update_preview)
        self.width_cb.currentIndexChanged.connect(self.update_preview)
        self.depth_cb.currentIndexChanged.connect(self.update_preview)
        self.thick_input.valueChanged.connect(self.update_preview)

        self.update_ui()
        self.update_preview()

    def update_ui(self):
        val_len = self.length_cb.currentText()
        if val_len == "Custom":
            self.custom_length.setEnabled(True)
        else:
            self.custom_length.setValue(float(val_len.replace(" MM", "")))
            self.custom_length.setEnabled(False)
        self.update_preview()

    def update_preview(self, *args):
        if not self.doc: return
        
        # Native Fallback cleanup
        existing_ghost = self.doc.getObject("Preview_Ghost")
        if existing_ghost:
            self.doc.removeObject(existing_ghost.Name)
            self.doc.recompute()

        comp_type = self.type_cb.currentText()
        l = self.custom_length.value()
        w = float(self.width_cb.currentText().replace(" MM", ""))
        d = float(self.depth_cb.currentText().replace(" MM", ""))
        t = self.thick_input.value()
        is_open = "OPEN" in comp_type

        try:
            shape = self.make_nema4x(l, w, d, t, is_open)
            
            if not shape: return

            if self.preview_manager:
                self.preview_manager.update(shape, color=(0.85, 0.85, 0.87))
            else:
                self.preview_obj = self.doc.addObject("Part::Feature", "Preview_Ghost")
                self.preview_obj.Shape = shape.removeSplitter()
                if hasattr(self.preview_obj, "ViewObject") and self.preview_obj.ViewObject:
                    self.preview_obj.ViewObject.ShapeColor = (0.85, 0.85, 0.87)
                    self.preview_obj.ViewObject.Transparency = 60
                self.doc.recompute()
                
        except Exception as e:
            App.Console.PrintWarning(f"Preview generation skipped: {str(e)}\n")

    def accept(self):
        # Clear the preview before finalizing
        if self.preview_manager:
            if hasattr(self.preview_manager, 'clear'): self.preview_manager.clear()
        elif self.doc and self.doc.getObject("Preview_Ghost"):
            self.doc.removeObject("Preview_Ghost")
            self.doc.recompute()

        comp_type = self.type_cb.currentText()
        l = self.custom_length.value()
        w = float(self.width_cb.currentText().replace(" MM", ""))
        d = float(self.depth_cb.currentText().replace(" MM", ""))
        t = self.thick_input.value()
        
        FreeCADGui.Control.closeDialog()
        self.generate_gutter(comp_type, l, w, d, t)

    def reject(self):
        # Clear the preview on cancel
        if self.preview_manager:
            if hasattr(self.preview_manager, 'clear'): self.preview_manager.clear()
        elif self.doc and self.doc.getObject("Preview_Ghost"):
            self.doc.removeObject("Preview_Ghost")
            self.doc.recompute()
            
        FreeCADGui.Control.closeDialog()

    def generate_gutter(self, comp_type, l, w, d, t):
        doc = App.ActiveDocument or App.newDocument("Detailed_Wire_Gutter")
        doc.openTransaction("Generate Wire Gutter")
        
        try:
            is_open = "OPEN" in comp_type
            shape = self.make_nema4x(l, w, d, t, is_open)
            color = (0.85, 0.85, 0.87) # Brighter Stainless Steel look
            
            # Clean up the name for the FreeCAD tree
            feat_name = comp_type.replace(" ", "_").replace("(", "").replace(")", "")
            obj = doc.addObject("Part::Feature", feat_name)
            
            # Apply shape and merge seams for a clean folded metal look
            obj.Shape = shape.removeSplitter()
            
            # Apply the paint color automatically
            if hasattr(obj, "ViewObject") and obj.ViewObject is not None:
                obj.ViewObject.ShapeColor = color
                
            doc.recompute()
            FreeCADGui.SendMsgToActiveView("ViewFit")
        except Exception as e:
            doc.abortTransaction()
            App.Console.PrintError(f"Failed to generate gutter: {str(e)}\n")
        finally:
            doc.commitTransaction()

    # ==========================================
    # PHOTO REPLICATION: NEMA 4X HINGED 
    # ==========================================
    def make_latch(self, t):
        """Creates the toggle clamp style latches seen in the photo"""
        # Flat base plate attached to the front wall
        base = Part.makeBox(30, t, 40, App.Vector(-15, -t, -35))
        
        # The hook part that grabs the lid
        hook = Part.makeBox(20, 12, 10, App.Vector(-10, -12, -5))
        
        # The angled toggle mechanism
        toggle = Part.makeBox(20, t*2.5, 30, App.Vector(-10, -t-6, -28))
        toggle.rotate(App.Vector(0, 0, -28), App.Vector(1, 0, 0), -12)
        
        # Two large screws holding it in place
        s1 = Part.makeCylinder(4.5, 4, App.Vector(-8, 3, -25), App.Vector(0, -1, 0))
        s2 = Part.makeCylinder(4.5, 4, App.Vector(8, 3, -25), App.Vector(0, -1, 0))
        
        # Indent slot for realistic screw look
        slot = Part.makeBox(10, 1.5, 1, App.Vector(-5, 2, -25.5))
        s1 = s1.cut(slot.copy().translate(App.Vector(-8, 0, 0)))
        s2 = s2.cut(slot.copy().translate(App.Vector(8, 0, 0)))

        return base.fuse([hook, toggle, s1, s2])

    def make_nema4x(self, l, w, d, t, is_open):
        """Replicates the Stainless Hinged Wireway with 2 Latches and Inner Holes"""
        # 1. Main Trough Body
        outer = Part.makeBox(l, w, d)
        inner = Part.makeBox(l - 2*t, w - 2*t, d)
        inner.translate(App.Vector(t, t, t))
        body = outer.cut(inner)

        # 2. Inward Return Flanges (The lip the gasket seats against)
        lip = 20.0
        lip_f = Part.makeBox(l, lip, t, App.Vector(0, 0, d - t))
        lip_b = Part.makeBox(l, lip, t, App.Vector(0, w - lip, d - t))
        lip_l = Part.makeBox(lip, w, t, App.Vector(0, 0, d - t))
        lip_r = Part.makeBox(lip, w, t, App.Vector(l - lip, 0, d - t))
        body = body.fuse([lip_f, lip_b, lip_l, lip_r])

        # 3. Inner Mounting Holes (Punched through the back/bottom wall)
        hole_radius = 4.5
        hole_offset = 50.0 # Placed 50mm from the corners
        
        # Ensure offset isn't larger than half the width if the box is small
        x_off = min(hole_offset, l/4.0)
        y_off = min(hole_offset, w/4.0)
        
        h1 = Part.makeCylinder(hole_radius, t*3, App.Vector(x_off, y_off, -t))
        h2 = Part.makeCylinder(hole_radius, t*3, App.Vector(l - x_off, y_off, -t))
        h3 = Part.makeCylinder(hole_radius, t*3, App.Vector(x_off, w - y_off, -t))
        h4 = Part.makeCylinder(hole_radius, t*3, App.Vector(l - x_off, w - y_off, -t))
        
        # Cut the holes out of the main body
        body = body.cut(h1).cut(h2).cut(h3).cut(h4)

        # 4. Front Latches (Exactly 2, spaced evenly)
        num_latches = 2
        spacing = l / 3.0
        latches = []
        for i in range(1, num_latches + 1):
            latch = self.make_latch(t)
            latch.translate(App.Vector(spacing * i, 0, d))
            latches.append(latch)
        body = body.fuse(latches)

        # 5. Hinged Lid (Shallow pan with a thick gasket)
        lid_thickness = 15.0
        lid_outer = Part.makeBox(l, w, lid_thickness)
        # Hollow it out to make a pan
        lid_inner = Part.makeBox(l - 2*t, w - 2*t, lid_thickness, App.Vector(t, t, -t))
        lid_pan = lid_outer.cut(lid_inner)

        # Create the prominent internal gasket
        gasket_w = 20.0
        g_outer = Part.makeBox(l - 2*t, w - 2*t, 6, App.Vector(t, t, 0))
        g_inner = Part.makeBox(l - 2*t - 2*gasket_w, w - 2*t - 2*gasket_w, 6, App.Vector(t + gasket_w, t + gasket_w, 0))
        gasket = g_outer.cut(g_inner)
        
        lid = lid_pan.fuse(gasket)

        # 6. Open / Close Logic
        if is_open:
            lid.translate(App.Vector(0, 0, d))
            # Hinge at the back-top corner, rotating 110 degrees like the photo
            lid.rotate(App.Vector(0, w, d), App.Vector(1, 0, 0), 110) 
        else:
            lid.translate(App.Vector(0, 0, d))

        return body.fuse(lid)

# Command Registration
import ComfacUtils

class CreateWireGutter:
    def GetResources(self):
        icon_path = ComfacUtils.get_icon_path('WireGutter.svg') if ComfacUtils else ""
        return {
            'Pixmap': icon_path, 
            'MenuText': "Generate Detailed Wire Gutter", 
            'ToolTip': "Create highly detailed NEMA 4X wire gutters"
        }
    def Activated(self):
        doc = App.ActiveDocument
        if not doc:
            App.newDocument("Wire_Gutter_Design")
        FreeCADGui.Control.showDialog(DetailedWireGutterTaskPanel())

try:
    FreeCADGui.addCommand('CreateWireGutter', CreateWireGutter())
except Exception as e:
    App.Console.PrintError(f"Failed to load command: {str(e)}\n")