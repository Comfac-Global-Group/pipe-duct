import FreeCAD
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui

# ==========================================================
# CORRUGATED SHEET MAKER (Parametric Sine-Wave Generator)
# ==========================================================
class CorrugatedSheetTaskPanel:
    def __init__(self):
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)
        
        # Profile Type Dropdown
        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems([
            "Corrugated Metal Roofing", 
            "Cardboard Fluting (Inner Core)", 
            "Cardboard (Single-Face / One Liner)",
            "Cardboard (Double-Face / Two Liners)"
        ])
        
        self.length_input = QtWidgets.QDoubleSpinBox()
        self.length_input.setRange(10.0, 20000.0)
        self.length_input.setValue(2000.0)
        self.length_input.setSingleStep(100.0)
        self.length_input.setSuffix(" mm")
        
        self.width_input = QtWidgets.QDoubleSpinBox()
        self.width_input.setRange(10.0, 10000.0)
        self.width_input.setValue(1000.0)
        self.width_input.setSingleStep(50.0)
        self.width_input.setSuffix(" mm")
        
        self.pitch_input = QtWidgets.QDoubleSpinBox()
        self.pitch_input.setRange(1.0, 500.0)
        self.pitch_input.setValue(76.2)
        self.pitch_input.setSingleStep(5.0)
        self.pitch_input.setSuffix(" mm")
        
        self.amp_input = QtWidgets.QDoubleSpinBox()
        self.amp_input.setRange(0.1, 500.0)
        self.amp_input.setValue(18.0)
        self.amp_input.setSingleStep(1.0)
        self.amp_input.setSuffix(" mm")
        
        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.01, 50.0)
        self.thick_input.setValue(0.5)
        self.thick_input.setDecimals(2)
        self.thick_input.setSingleStep(0.1)
        self.thick_input.setSuffix(" mm")
        
        self.layout.addRow("Material Type:", self.type_cb)
        self.layout.addRow("Sheet Length (Extrusion):", self.length_input)
        self.layout.addRow("Sheet Width (Wave Span):", self.width_input)
        self.layout.addRow("Wave Pitch (Peak to Peak):", self.pitch_input)
        self.layout.addRow("Wave Amplitude (Total Height):", self.amp_input)
        self.layout.addRow("Material Thickness:", self.thick_input)
        
        # Connect dropdown change to update the default values
        self.type_cb.currentTextChanged.connect(self.update_defaults)

    def update_defaults(self):
        sheet_type = self.type_cb.currentText()
        if "Cardboard" in sheet_type:
            # Set to standard cardboard sizes
            self.pitch_input.setValue(8.0) 
            self.amp_input.setValue(4.0) 
            self.thick_input.setValue(0.3)
            self.length_input.setValue(300.0)
            self.width_input.setValue(300.0)
        else:
            # Set to standard metal sheet sizes
            self.pitch_input.setValue(76.2) 
            self.amp_input.setValue(18.0) 
            self.thick_input.setValue(0.5)
            self.length_input.setValue(2000.0)
            self.width_input.setValue(1000.0)

    def accept(self):
        sheet_type = self.type_cb.currentText()
        L = self.length_input.value()
        W = self.width_input.value()
        P = self.pitch_input.value()
        A = self.amp_input.value()
        T = self.thick_input.value()

        FreeCADGui.Control.closeDialog()
        self.generate_sheet(sheet_type, L, W, P, A, T)
        return True

    def reject(self):
        FreeCADGui.Control.closeDialog()
        return True

    def generate_sheet(self, sheet_type, L, W, P, A, T):
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument()
            
        pts_top = []
        pts_bottom = []
        
        num_waves = W / P
        # High resolution points mapped directly to a rigid polygon
        points_per_wave = 40 
        total_points = max(10, int(num_waves * points_per_wave))
        
        k = 2 * math.pi / P
        
        # Mathematically Plot the Corrugation Wave
        for i in range(total_points + 1):
            x = (i / total_points) * W
            z = (A / 2.0) * math.sin(k * x) 
            
            # Calculate the true normal direction to offset the thickness uniformly
            dz_dx = (A / 2.0) * k * math.cos(k * x)
            length_norm = math.sqrt(1 + dz_dx**2)
            nx = -dz_dx / length_norm
            nz = 1.0 / length_norm
            
            pts_top.append(FreeCAD.Vector(x, 0, z))
            pts_bottom.append(FreeCAD.Vector(x - nx * T, 0, z - nz * T))
        
        pts_bottom.reverse() # Reverse to connect in a continuous loop
        
        # Use makePolygon to rigidly trace the points
        poly_points = pts_top + pts_bottom + [pts_top[0]]
        wire = Part.Wire(Part.makePolygon(poly_points))
        
        # Form Face and Extrude the Inner Core
        face = Part.Face(wire)
        solid = face.extrude(FreeCAD.Vector(0, L, 0))
        
        # Add Flat Liners based on dropdown selection
        if "Liner" in sheet_type:
            overlap = T * 0.1 # 10% overlap to prevent boolean fusing errors
            fuses = [solid]
            
            # Bottom Cardboard Liner (Always present if there's any liner)
            p1b = FreeCAD.Vector(0, 0, -A/2.0 - T + overlap)
            p2b = FreeCAD.Vector(W, 0, -A/2.0 - T + overlap)
            p3b = FreeCAD.Vector(W, 0, -A/2.0 - 2*T)
            p4b = FreeCAD.Vector(0, 0, -A/2.0 - 2*T)
            bot_wire = Part.Wire(Part.makePolygon([p1b, p2b, p3b, p4b, p1b]))
            bot_solid = Part.Face(bot_wire).extrude(FreeCAD.Vector(0, L, 0))
            fuses.append(bot_solid)
            
            # Top Cardboard Liner (Only if Double-Face is selected)
            if "Double" in sheet_type or "Two" in sheet_type:
                p1 = FreeCAD.Vector(0, 0, A/2.0 - overlap)
                p2 = FreeCAD.Vector(W, 0, A/2.0 - overlap)
                p3 = FreeCAD.Vector(W, 0, A/2.0 + T)
                p4 = FreeCAD.Vector(0, 0, A/2.0 + T)
                top_wire = Part.Wire(Part.makePolygon([p1, p2, p3, p4, p1]))
                top_solid = Part.Face(top_wire).extrude(FreeCAD.Vector(0, L, 0))
                fuses.append(top_solid)
            
            # Fuse them together into a single rigid board
            solid = fuses[0].fuse(fuses[1:]).removeSplitter()

        # --- UNDO TRANSACTION START ---
        doc.openTransaction("Create Corrugated Sheet")
        try:
            # Smart Auto-Nesting Logic
            sel = FreeCADGui.Selection.getSelection()
            parent_container = None
            is_body = False
            
            if sel:
                for parent in sel[0].InList + [sel[0]]:
                    if parent.isDerivedFrom("PartDesign::Body"):
                        parent_container = parent
                        is_body = True
                        break
                    elif parent.isDerivedFrom("App::Part") or parent.isDerivedFrom("App::DocumentObjectGroup"):
                        parent_container = parent
                        break
            else:
                try:
                    active_body = FreeCADGui.ActiveDocument.ActiveView.getActiveObject("pdbody")
                    if active_body:
                        parent_container = active_body
                        is_body = True
                except: pass

            if is_body:
                # Wrapper Fix for PartDesign
                raw_sheet = doc.addObject("Part::Feature", "Raw_Corrugated_Data")
                raw_sheet.Shape = solid
                raw_sheet.ViewObject.Visibility = False 
                
                obj = parent_container.newObject("PartDesign::FeatureBase", "Corrugated_Sheet")
                obj.BaseFeature = raw_sheet
            else:
                # Standard Part
                obj = doc.addObject("Part::Feature", "Corrugated_Sheet")
                obj.Shape = solid
                if parent_container:
                    parent_container.addObject(obj)

            # Store the generation variables inside the object
            try:
                obj.addProperty("App::PropertyString", "MaterialType", "CorrugatedData", "Type of material")
                obj.addProperty("App::PropertyLength", "SheetLength", "CorrugatedData", "Length of the sheet")
                obj.addProperty("App::PropertyLength", "SheetWidth", "CorrugatedData", "Width of the sheet")
                obj.addProperty("App::PropertyLength", "WavePitch", "CorrugatedData", "Distance between waves")
                obj.addProperty("App::PropertyLength", "WaveAmplitude", "CorrugatedData", "Total height of the wave")
                obj.addProperty("App::PropertyLength", "SheetThickness", "CorrugatedData", "Thickness of the material")
                
                obj.MaterialType = sheet_type
                obj.SheetLength = L
                obj.SheetWidth = W
                obj.WavePitch = P
                obj.WaveAmplitude = A
                obj.SheetThickness = T
            except: pass

            # Apply accurate colors
            if "Cardboard" in sheet_type:
                obj.ViewObject.ShapeColor = (0.76, 0.60, 0.42) # Cardboard Brown
            else:
                obj.ViewObject.ShapeColor = (0.75, 0.75, 0.8) # Metal Silver
            
            if hasattr(obj, "Refine"):
                obj.Refine = True
            
            doc.recompute()
            doc.commitTransaction()
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Error", f"Failed to generate sheet.\n\n{e}")
        # --- UNDO TRANSACTION END ---

import ComfacUtils

class CreateCorrugatedSheet:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('Corrugated_Sheet.svg'),
            'MenuText': "Create Corrugated Sheet",
            'ToolTip': "Generates parametric corrugated metal or cardboard sheets"
        }

    def Activated(self):
        panel = CorrugatedSheetTaskPanel()
        FreeCADGui.Control.showDialog(panel)

FreeCADGui.addCommand('CreateCorrugatedSheet', CreateCorrugatedSheet())