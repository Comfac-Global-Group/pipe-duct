import FreeCAD as App
import FreeCADGui
import Part
import csv
import os
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils

class BOMDashboard(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Bill of Materials (BOM)")
        self.resize(800, 500)
        
        self.layout = QtWidgets.QVBoxLayout(self.setLayout(self.layout))
        
        # BOM Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Category", "Description", "Specifications", "Qty / Length", "Unit"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.layout.addWidget(self.table)
        
        # Buttons
        self.btn_layout = QtWidgets.QHBoxLayout()
        
        self.btn_refresh = QtWidgets.QPushButton("Refresh BOM")
        self.btn_export = QtWidgets.QPushButton("Export to CSV")
        self.btn_close = QtWidgets.QPushButton("Close")
        
        self.btn_layout.addWidget(self.btn_refresh)
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.btn_export)
        self.btn_layout.addWidget(self.btn_close)
        
        self.layout.addLayout(self.btn_layout)
        
        # Connections
        self.btn_refresh.clicked.connect(self.generate_bom)
        self.btn_export.clicked.connect(self.export_csv)
        self.btn_close.clicked.connect(self.reject)
        
        # Run initially
        self.generate_bom()

    def add_row(self, category, desc, specs, qty, unit):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(category))
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(desc))
        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(specs))
        
        qty_item = QtWidgets.QTableWidgetItem(str(qty))
        qty_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.table.setItem(row, 3, qty_item)
        
        self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(unit))

    def get_wire_length(self, shape):
        """Calculates total running length of a swept/extruded shape based on its longest wires."""
        if not shape or shape.isNull(): return 0.0
        total_len = 0.0
        # A rough heuristic: the bounding box diagonal or the sum of edges.
        # For swept pipes, dividing total edge length by number of cross-section edges gives a good approximation.
        edges = [e for e in shape.Edges if hasattr(e.Curve, 'TypeId') and 'Line' in e.Curve.TypeId]
        if not edges: return shape.BoundBox.DiagonalLength
        
        # Get the longest continuous path
        edges.sort(key=lambda e: e.Length, reverse=True)
        return sum(e.Length for e in edges[:int(len(edges)/4) or 1])

    def generate_bom(self):
        self.table.setRowCount(0)
        doc = App.ActiveDocument
        if not doc: return

        bom_data = {}

        for obj in doc.Objects:
            if not hasattr(obj, "Shape") or obj.Shape.isNull(): continue
            
            # --- 1. WALLS ---
            if hasattr(obj, "WallHeight") and hasattr(obj, "WallThickness"):
                cat = "Architecture"
                desc = "Parametric Wall"
                specs = f"H: {obj.WallHeight:.1f}mm, Thk: {obj.WallThickness:.1f}mm"
                
                # Calculate running length using the base sketch if available
                length = 0.0
                if hasattr(obj, "BaseSketch") and obj.BaseSketch:
                    length = sum(e.Length for e in obj.BaseSketch.Shape.Edges)
                else:
                    length = obj.Shape.BoundBox.DiagonalLength # Fallback
                
                key = (cat, desc, specs)
                bom_data[key] = bom_data.get(key, 0.0) + (length / 1000.0) # Convert to Meters

            # --- 2. DUCTS ---
            elif hasattr(obj, "DuctWidth") and hasattr(obj, "DuctHeight"):
                cat = "HVAC"
                desc = f"Duct - {getattr(obj, 'ProfileType', 'Rectangular')}"
                specs = f"{obj.DuctWidth:.1f} x {obj.DuctHeight:.1f} mm"
                
                length = 0.0
                if hasattr(obj, "SketchName") and doc.getObject(obj.SketchName):
                    length = sum(e.Length for e in doc.getObject(obj.SketchName).Shape.Edges)
                else:
                    length = self.get_wire_length(obj.Shape)
                    
                key = (cat, desc, specs)
                bom_data[key] = bom_data.get(key, 0.0) + (length / 1000.0)

            # --- 3. FLEX CONDUITS ---
            elif hasattr(obj, "Standard") and hasattr(obj, "Size"):
                cat = "Electrical"
                desc = f"Flex Conduit ({obj.Standard})"
                specs = f"Size: {obj.Size}"
                
                length = self.get_wire_length(obj.Shape)
                key = (cat, desc, specs)
                bom_data[key] = bom_data.get(key, 0.0) + (length / 1000.0)

            # --- 4. FASTENERS & SADDLES (Arrays) ---
            elif "Array" in obj.Name or "Saddle" in obj.Name or "Fastener" in obj.Name:
                cat = "Hardware"
                desc = obj.Label.replace("_", " ")
                
                # Count the actual solid bodies inside the compound!
                qty = len(obj.Shape.Solids)
                if qty == 0: qty = 1 # Fallback for single objects
                
                # Try to extract material color to guess the type
                specs = "Galvanized / Steel"
                if hasattr(obj.ViewObject, "ShapeColor"):
                    c = obj.ViewObject.ShapeColor
                    if c[0] > 0.7 and c[1] < 0.5: specs = "Copper"
                    elif c[0] < 0.4: specs = "PVC"
                
                key = (cat, desc, specs)
                bom_data[key] = bom_data.get(key, 0) + qty

            # --- 5. COUPLINGS & END CAPS ---
            elif "Coupling" in obj.Name or "EndCap" in obj.Name:
                cat = "Fittings"
                desc = obj.Label.replace("_", " ")
                specs = "Standard"
                
                key = (cat, desc, specs)
                bom_data[key] = bom_data.get(key, 0) + 1

            # --- 6. INSULATION ---
            elif "Insulation" in obj.Name:
                cat = "Insulation"
                desc = "Foam Jacket"
                specs = f"Volume: {(obj.Shape.Volume / 1e9):.3f} m³"
                
                length = self.get_wire_length(obj.Shape)
                key = (cat, desc, specs)
                bom_data[key] = bom_data.get(key, 0.0) + (length / 1000.0)


        # Populate the Table
        for (cat, desc, specs), val in sorted(bom_data.items()):
            # Determine unit formatting based on category
            if cat in ["Hardware", "Fittings"]:
                qty_str = f"{int(val)}"
                unit = "pcs"
            else:
                qty_str = f"{val:.2f}"
                unit = "m" # Meters
                
            self.add_row(cat, desc, specs, qty_str, unit)

    def export_csv(self):
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.warning(self, "Export Error", "The BOM is empty!")
            return
            
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save BOM", "", "CSV Files (*.csv)")
        if not path: return
        
        try:
            with open(path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                # Write Headers
                headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
                writer.writerow(headers)
                
                # Write Data
                for row in range(self.table.rowCount()):
                    row_data = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
                    
            QtWidgets.QMessageBox.information(self, "Success", f"BOM successfully exported to:\n{path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", f"Failed to save CSV:\n{str(e)}")

class LaunchBOMCommand:
    def GetResources(self):
        return {
            'Pixmap': 'Std_Report', 
            'MenuText': "Project BOM Dashboard",
            'ToolTip': "Tally all Pipes, Ducts, Walls, and Hardware into a Bill of Materials"
        }

    def Activated(self):
        # We need to keep a reference to the dialog so it doesn't get garbage collected
        if not hasattr(self, "dialog") or not self.dialog.isVisible():
            self.dialog = BOMDashboard()
            self.dialog.show()
        else:
            self.dialog.raise_()
            self.dialog.activateWindow()

FreeCADGui.addCommand('BillOfMaterials', LaunchBOMCommand())