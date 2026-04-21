import FreeCAD
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui

# ==========================================================
# 10. PERFORATED SURFACE MAKER (Algebraic Solver Optimized)
# ==========================================================
class PerforatedSheetTaskPanel:
    def __init__(self):
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)
        
        # Dimensions
        self.length_input = QtWidgets.QDoubleSpinBox()
        self.length_input.setRange(10.0, 5000.0)
        self.length_input.setValue(600.0)
        self.length_input.setSingleStep(50.0)
        self.length_input.setSuffix(" mm")
        
        self.width_input = QtWidgets.QDoubleSpinBox()
        self.width_input.setRange(10.0, 5000.0)
        self.width_input.setValue(600.0)
        self.width_input.setSingleStep(50.0)
        self.width_input.setSuffix(" mm")
        
        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.1, 100.0)
        self.thick_input.setValue(2.0)
        self.thick_input.setDecimals(2)
        self.thick_input.setSuffix(" mm")

        self.margin_input = QtWidgets.QDoubleSpinBox()
        self.margin_input.setRange(0.0, 200.0)
        self.margin_input.setValue(25.0) 
        self.margin_input.setSuffix(" mm")
        
        # Hole Specs
        self.shape_cb = QtWidgets.QComboBox()
        self.shape_cb.addItems(["Circle", "Hexagon", "Square"])
        
        self.pattern_cb = QtWidgets.QComboBox()
        self.pattern_cb.addItems(["Staggered (60°)", "Straight Grid"])

        self.size_input = QtWidgets.QDoubleSpinBox()
        self.size_input.setRange(1.0, 200.0)
        self.size_input.setValue(6.0) 
        self.size_input.setDecimals(1)   # FIX 3: Allow 0.5mm steps
        self.size_input.setSingleStep(0.5)
        self.size_input.setSuffix(" mm")
        
        self.open_area_input = QtWidgets.QDoubleSpinBox()
        self.open_area_input.setRange(5.0, 90.0) 
        self.open_area_input.setValue(40.0) 
        self.open_area_input.setDecimals(1)
        self.open_area_input.setSuffix(" %")
        
        self.layout.addRow("Sheet Length (X):", self.length_input)
        self.layout.addRow("Sheet Width (Y):", self.width_input)
        self.layout.addRow("Material Thickness:", self.thick_input)
        self.layout.addRow("Solid Margin (Border):", self.margin_input)
        self.layout.addRow(QtWidgets.QLabel("")) 
        self.layout.addRow("Hole Shape:", self.shape_cb)
        self.layout.addRow("Grid Pattern:", self.pattern_cb)
        self.layout.addRow("Initial Hole Size Guess:", self.size_input)
        self.layout.addRow("Target Open Area (TPA):", self.open_area_input)

    def accept(self):
        L = self.length_input.value()
        W = self.width_input.value()
        T = self.thick_input.value()
        margin = self.margin_input.value()
        shape_type = self.shape_cb.currentText()
        pattern = self.pattern_cb.currentText()
        user_hole_size = self.size_input.value()
        open_area = self.open_area_input.value()

        FreeCADGui.Control.closeDialog()
        self.generate_perforated_sheet(L, W, T, margin, shape_type, pattern, user_hole_size, open_area)
        return True

    def reject(self):
        FreeCADGui.Control.closeDialog()
        return True

    def get_base_hole_wire(self, shape_type, radius):
        """Creates a single template hole at origin (0,0) to save memory."""
        if shape_type == "Circle":
            circ = Part.Circle(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), radius)
            wire = Part.Wire(Part.Edge(circ))
        elif shape_type == "Square":
            p1 = FreeCAD.Vector(-radius, -radius, 0)
            p2 = FreeCAD.Vector(radius, -radius, 0)
            p3 = FreeCAD.Vector(radius, radius, 0)
            p4 = FreeCAD.Vector(-radius, radius, 0)
            wire = Part.Wire(Part.makePolygon([p1, p2, p3, p4, p1]))
        elif shape_type == "Hexagon":
            pts = []
            for i in range(7):
                angle = math.radians(60 * i) 
                pts.append(FreeCAD.Vector(radius * math.cos(angle), radius * math.sin(angle), 0))
            wire = Part.Wire(Part.makePolygon(pts))
            
        wire.reverse() 
        return wire

    def generate_perforated_sheet(self, L, W, T, margin, shape_type, pattern, user_hole_size, open_area):
        doc = FreeCAD.ActiveDocument
        
        # --- ALGEBRAIC SOLVER: High-Speed TPA Optimization ---
        target_total_area = L * W * (open_area / 100.0)
        workable_L = L - (2 * margin)
        workable_W = W - (2 * margin)
        workable_area = workable_L * workable_W
        
        if workable_area <= 0 or target_total_area >= workable_area:
            QtWidgets.QMessageBox.critical(None, "Geometry Error", "Margins are too large to achieve this Target Perforated Area.")
            return

        pattern_ratio = target_total_area / workable_area
        
        best_hole_size = user_hole_size
        best_pitch = 0
        best_apa = -1
        min_diff = float('inf')

        # Guard max candidate size against both workable dimensions
        max_search_mm = min(workable_L / 2.0, workable_W / 2.0)

        # Search a window centered on the user's guess (±50% of guess, min 2mm window)
        # This respects the user's intent while still allowing fine APA tuning via 0.5mm steps
        window = max(2.0, user_hole_size * 0.5)
        search_min = max(0.5, round(round((user_hole_size - window) * 2) * 0.5, 1))
        search_max = min(max_search_mm, round(round((user_hole_size + window) * 2) * 0.5, 1))

        # Build candidates in 0.5mm steps within the window around user's guess
        # Sorted by proximity to user's guess so the first equally-good hit wins
        raw = [round(x * 0.5, 1) for x in range(
            int(search_min / 0.5),
            int(search_max / 0.5) + 1
        ) if 0.5 <= round(x * 0.5, 1) <= max_search_mm]
        candidates = sorted(raw, key=lambda s: abs(s - user_hole_size))

        for hs in candidates:
            radius = hs / 2.0
            
            if shape_type == "Circle":
                h_area = math.pi * (radius ** 2)
            elif shape_type == "Square":
                h_area = 4 * (radius ** 2)
            elif shape_type == "Hexagon":
                h_area = (3 * math.sqrt(3) / 2) * (radius ** 2)
                
            if pattern == "Straight Grid":
                pitch = math.sqrt(h_area / pattern_ratio)
            else:
                pitch = math.sqrt(h_area / (pattern_ratio * math.sin(math.radians(60))))
                
            if pitch <= hs:
                continue

            # Per-candidate boundary limits accounting for radius
            cx_min = margin + radius
            cx_max = L - margin - radius
            cy_min = margin + radius
            cy_max = W - margin - radius

            N = 0
            if cx_min <= cx_max and cy_min <= cy_max:
                if pattern == "Straight Grid":
                    cols = max(1, int(workable_L / pitch))
                    rows = max(1, int(workable_W / pitch))
                    x_offset = (L - (cols - 1) * pitch) / 2.0
                    y_offset = (W - (rows - 1) * pitch) / 2.0
                    
                    min_i = math.ceil(round((cx_min - x_offset) / pitch, 6))
                    max_i = math.floor(round((cx_max - x_offset) / pitch, 6))
                    min_j = math.ceil(round((cy_min - y_offset) / pitch, 6))
                    max_j = math.floor(round((cy_max - y_offset) / pitch, 6))
                    
                    valid_i = max(0, min(cols - 1, max_i) - max(0, min_i) + 1)
                    valid_j = max(0, min(rows - 1, max_j) - max(0, min_j) + 1)
                    N = valid_i * valid_j
                    
                else:  # Staggered (60°) — FIX 1: Fully algebraic, no inner row loop
                    row_height = pitch * math.sin(math.radians(60))
                    cols = max(1, int(workable_L / pitch))
                    rows = max(1, int(workable_W / row_height))
                    x_offset = (L - (cols - 1) * pitch) / 2.0
                    y_offset = (W - (rows - 1) * row_height) / 2.0

                    min_j = math.ceil(round((cy_min - y_offset) / row_height, 6))
                    max_j = math.floor(round((cy_max - y_offset) / row_height, 6))
                    start_j = max(0, min_j)
                    end_j   = min(rows - 1, max_j)

                    if start_j <= end_j:
                        total_rows_in_range = end_j - start_j + 1

                        # Count even and odd rows algebraically — O(1), no loop needed
                        even_count = (end_j // 2) - ((start_j - 1) // 2)
                        odd_count  = total_rows_in_range - even_count

                        # Even rows: no x-shift, full cols
                        x_off_even = x_offset
                        min_i_e = math.ceil(round((cx_min - x_off_even) / pitch, 6))
                        max_i_e = math.floor(round((cx_max - x_off_even) / pitch, 6))
                        valid_i_even = max(0, min(cols - 1, max_i_e) - max(0, min_i_e) + 1)

                        # Odd rows: shifted by pitch/2, max col index is cols-2
                        x_off_odd = x_offset + pitch / 2.0
                        min_i_o = math.ceil(round((cx_min - x_off_odd) / pitch, 6))
                        max_i_o = math.floor(round((cx_max - x_off_odd) / pitch, 6))
                        valid_i_odd = max(0, min(cols - 2, max_i_o) - max(0, min_i_o) + 1)

                        N = even_count * valid_i_even + odd_count * valid_i_odd
                        
            # Calculate APA
            actual_area = N * h_area
            apa = (actual_area / (L * W)) * 100.0
            diff = abs(apa - open_area)
            
            # Candidates are pre-sorted by proximity to user's guess, so strict < is sufficient
            # — on an APA tie, the first candidate seen (closest to guess) already wins
            if diff < min_diff:
                min_diff = diff
                best_hole_size = hs
                best_pitch = pitch
                best_apa = apa

        if best_apa == -1:
            QtWidgets.QMessageBox.critical(None, "Geometry Error", "Could not find a valid hole size that prevents overlapping. Try lowering the target percentage.")
            return

        hole_size = float(best_hole_size)
        pitch = best_pitch
        radius = hole_size / 2.0
        # --- END OF SOLVER ---

        # 1. Base Outer Rectangle
        p1 = FreeCAD.Vector(0, 0, 0)
        p2 = FreeCAD.Vector(L, 0, 0)
        p3 = FreeCAD.Vector(L, W, 0)
        p4 = FreeCAD.Vector(0, W, 0)
        outer_wire = Part.Wire(Part.makePolygon([p1, p2, p3, p4, p1]))
        
        wires = [outer_wire] 
        base_hole = self.get_base_hole_wire(shape_type, radius)
        
        # 2. Final Generation Loop using optimal values
        #    FIX 4: Pre-compute valid index ranges to avoid per-hole boundary checks
        if pattern == "Straight Grid":
            cols = max(1, int(workable_L / pitch))
            rows = max(1, int(workable_W / pitch))
            x_offset = (L - (cols - 1) * pitch) / 2.0
            y_offset = (W - (rows - 1) * pitch) / 2.0

            cx_min = margin + radius
            cx_max = L - margin - radius
            cy_min = margin + radius
            cy_max = W - margin - radius

            i_start = max(0, math.ceil(round((cx_min - x_offset) / pitch, 6)))
            i_end   = min(cols - 1, math.floor(round((cx_max - x_offset) / pitch, 6)))
            j_start = max(0, math.ceil(round((cy_min - y_offset) / pitch, 6)))
            j_end   = min(rows - 1, math.floor(round((cy_max - y_offset) / pitch, 6)))

            for i in range(i_start, i_end + 1):
                for j in range(j_start, j_end + 1):
                    cx = x_offset + i * pitch
                    cy = y_offset + j * pitch
                    new_hole = base_hole.copy()
                    new_hole.translate(FreeCAD.Vector(cx, cy, 0))
                    wires.append(new_hole)
                    
        else:  # Staggered (60°)
            row_height = pitch * math.sin(math.radians(60))
            cols = max(1, int(workable_L / pitch))
            rows = max(1, int(workable_W / row_height))
            x_offset = (L - (cols - 1) * pitch) / 2.0
            y_offset = (W - (rows - 1) * row_height) / 2.0

            cx_min = margin + radius
            cx_max = L - margin - radius
            cy_min = margin + radius
            cy_max = W - margin - radius

            j_start = max(0, math.ceil(round((cy_min - y_offset) / row_height, 6)))
            j_end   = min(rows - 1, math.floor(round((cy_max - y_offset) / row_height, 6)))

            for j in range(j_start, j_end + 1):
                row_x_offset = x_offset + (pitch / 2.0 if j % 2 != 0 else 0.0)
                row_cols     = cols - 1 if j % 2 != 0 else cols

                # Pre-compute valid i range per row — no per-hole check needed
                i_start = max(0, math.ceil(round((cx_min - row_x_offset) / pitch, 6)))
                i_end   = min(row_cols - 1, math.floor(round((cx_max - row_x_offset) / pitch, 6)))

                for i in range(i_start, i_end + 1):
                    cx = row_x_offset + i * pitch
                    cy = y_offset + j * row_height
                    new_hole = base_hole.copy()
                    new_hole.translate(FreeCAD.Vector(cx, cy, 0))
                    wires.append(new_hole)

        # 3. Super Fast Face Extrusion
        try:
            face = Part.Face(wires)
            solid = face.extrude(FreeCAD.Vector(0, 0, T))
            top_face_area = face.Area 
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Generation Error", f"Geometry calculation failed.\n\nError: {e}")
            return

        # --- UNDO TRANSACTION START ---
        doc.openTransaction("Create Perforated Sheet")
        try:
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
                raw_sheet = doc.addObject("Part::Feature", "Raw_Perf_Data")
                raw_sheet.Shape = solid
                raw_sheet.ViewObject.Visibility = False 
                
                obj = parent_container.newObject("PartDesign::FeatureBase", "Perforated_Sheet")
                obj.BaseFeature = raw_sheet
            else:
                obj = doc.addObject("Part::Feature", "Perforated_Sheet")
                obj.Shape = solid
                if parent_container:
                    parent_container.addObject(obj)

            try:
                obj.addProperty("App::PropertyLength", "SheetLength", "PerfData", "Length of the sheet")
                obj.addProperty("App::PropertyLength", "SheetWidth", "PerfData", "Width of the sheet")
                obj.addProperty("App::PropertyString", "HoleShape", "PerfData", "Shape of holes")
                obj.addProperty("App::PropertyLength", "AdjustedHoleSize", "PerfData", "Optimized hole size")
                obj.addProperty("App::PropertyLength", "CalculatedPitch", "PerfData", "Center-to-Center spacing")
                
                obj.addProperty("App::PropertyString", "TargetOpenArea", "PerfData_Output", "Requested open area of the hole pattern")
                obj.addProperty("App::PropertyString", "ActualSheetOpenArea", "PerfData_Output", "Final achieved open area of the total sheet")
                obj.addProperty("App::PropertyString", "NetSolidTopArea", "PerfData_Output", "Surface area of the top metal face")

                obj.SheetLength = L
                obj.SheetWidth = W
                obj.HoleShape = shape_type
                obj.AdjustedHoleSize = hole_size 
                obj.CalculatedPitch = pitch
                
                obj.TargetOpenArea = f"{open_area:.1f} %"
                obj.ActualSheetOpenArea = f"{best_apa:.2f} %"
                
                area_cm2 = top_face_area / 100.0 
                obj.NetSolidTopArea = f"{area_cm2:.2f} cm\u00b2" 
                
            except: pass

            obj.ViewObject.ShapeColor = (0.25, 0.25, 0.25) 
            
            if hasattr(obj, "Refine"):
                obj.Refine = True   
            
            doc.recompute()
            doc.commitTransaction()
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Error", f"Failed to generate sheet.\n\n{e}")
        # --- UNDO TRANSACTION END ---

import ComfacUtils

class CreatePerforatedSheet:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('Perforated_Sheet.svg'), 
            'MenuText': "Create Perforated Surface",
            'ToolTip': "Generates parametric server rack grilles and perforated tiles"
        }

    def Activated(self):
        panel = PerforatedSheetTaskPanel()
        FreeCADGui.Control.showDialog(panel)

FreeCADGui.addCommand('CreatePerforatedSheet', CreatePerforatedSheet())