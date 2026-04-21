import FreeCAD as App
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils


# ==========================================
# DUCT SCREW TOOL
# ==========================================

class DuctScrewTaskPanel:
    def __init__(self):
        self.sizes = {
            '#8 x 1/2"': (4.2, 13.0),
            '#8 x 3/4"': (4.2, 19.0),
            '#8 x 1"': (4.2, 25.0),
            '#10 x 1/2"': (4.8, 13.0),
            '#10 x 3/4"': (4.8, 19.0),
            '#10 x 1"': (4.8, 25.0),
            'Custom': (4.0, 15.0)
        }

        self.materials = {
            "Zinc Plated": (0.8, 0.8, 0.8),
            "Stainless Steel": (0.6, 0.6, 0.65),
            "Black Phosphate": (0.1, 0.1, 0.1),
            "Copper Plated": (0.72, 0.45, 0.2)
        }

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.preview = ComfacUtils.PreviewManager(App.ActiveDocument, "DuctScrew_Preview")

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems([
            "Self-Piercing (Zip-in)", 
            "Self-Drilling (Tek)", 
            "Hex Washer Head", 
            "Phillips Modified Truss",
            "Register Screw",
            "Stainless Steel Screw"
        ])
        
        self.mat_cb = QtWidgets.QComboBox()
        self.mat_cb.addItems(list(self.materials.keys()))

        self.size_cb = QtWidgets.QComboBox()
        self.size_cb.addItems(list(self.sizes.keys()))

        self.dia_input = QtWidgets.QDoubleSpinBox()
        self.dia_input.setRange(1.0, 10.0); self.dia_input.setValue(4.2); self.dia_input.setSuffix(" mm")

        self.len_input = QtWidgets.QDoubleSpinBox()
        self.len_input.setRange(1.0, 100.0); self.len_input.setValue(13.0); self.len_input.setSuffix(" mm")

        self.snap_label = QtWidgets.QLabel("Select a Surface to Snap Screw")
        self.snap_label.setStyleSheet("color: darkgreen; font-weight: bold;")

        self.layout.addRow(self.snap_label)
        self.layout.addRow("Screw Type:", self.type_cb)
        self.layout.addRow("Material:", self.mat_cb)
        self.layout.addRow("Size Preset:", self.size_cb)
        self.layout.addRow("Shank Diameter:", self.dia_input)
        self.layout.addRow("Shank Length:", self.len_input)

        self.size_cb.currentIndexChanged.connect(self.update_dims)
        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.mat_cb.currentIndexChanged.connect(self.trigger_preview)
        self.dia_input.valueChanged.connect(self.trigger_preview)
        self.len_input.valueChanged.connect(self.trigger_preview)

        self.trigger_preview()

    def update_dims(self):
        sz = self.size_cb.currentText()
        if sz != "Custom":
            self.dia_input.setValue(self.sizes[sz][0])
            self.len_input.setValue(self.sizes[sz][1])
        self.trigger_preview()

    def trigger_preview(self):
        pass

    def accept(self):
        s_type = self.type_cb.currentText()
        mat = self.mat_cb.currentText()
        dia = self.dia_input.value()
        length = self.len_input.value()

        placement = App.Placement()
        sel = FreeCADGui.Selection.getSelectionEx()
        if sel:
            placement = sel[0].Object.Placement

        self.preview.clear()
        FreeCADGui.Control.closeDialog()
        self.generate_screw(s_type, mat, dia, length, placement)

    def reject(self):
        self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def generate_screw(self, s_type, mat, dia, length, placement):
        doc = App.ActiveDocument or App.newDocument("Duct_Screws")
        head_dia = dia * 2.0
        head_thick = dia * 0.6
        doc.openTransaction("Duct Screws")

        if "Hex" in s_type or "Zip-in" in s_type:
            pts = []
            for i in range(7):
                angle = math.radians(i * 60)
                pts.append(App.Vector(head_dia/2 * math.cos(angle), head_dia/2 * math.sin(angle), length))
            head_wire = Part.makePolygon(pts)
            head = Part.Face(head_wire).extrude(App.Vector(0,0, head_thick))
        else:
            head = Part.makeSphere(head_dia/2, App.Vector(0,0, length))
            cut_box = Part.makeBox(head_dia, head_dia, head_dia, App.Vector(-head_dia/2, -head_dia/2, length - head_dia))
            head = head.cut(cut_box)

        core_r = (dia/2) * 0.8
        shank = Part.makeCylinder(core_r, length, App.Vector(0,0,0), App.Vector(0,0,1))
        pitch = 1.2
        num_threads = int(length / pitch)
        
        full_shank = shank
        for i in range(1, num_threads):
            z = i * pitch
            tooth = Part.makeCone(dia/2, core_r, pitch * 0.5, App.Vector(0,0, z), App.Vector(0,0,1))
            full_shank = full_shank.fuse(tooth)

        if "Tek" in s_type:
            tip = Part.makeBox(dia, dia/4, dia/2, App.Vector(-dia/2, -dia/8, 0))
            full_shank = full_shank.fuse(tip)
        else:
            tip = Part.makeCone(dia/2, 0, dia*0.8, App.Vector(0,0,0), App.Vector(0,0,-1))
            full_shank = full_shank.fuse(tip)

        screw_shape = head.fuse(full_shank)
        obj = doc.addObject("Part::Feature", s_type.replace(" ","_"))
        doc.commitTransaction()
        obj.Shape = screw_shape.removeSplitter()
        obj.Placement = placement
        obj.ViewObject.ShapeColor = self.materials[mat]
        doc.recompute()


class CreateDuctScrews:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('DuctScrew.svg'),
            'MenuText': "Duct Screw",
            'ToolTip': "Generates duct mounting screws"
        }

    def Activated(self):
        panel = DuctScrewTaskPanel()
        FreeCADGui.Control.showDialog(panel)


#FreeCADGui.addCommand('CreateDuctScrews', CreateDuctScrews())
