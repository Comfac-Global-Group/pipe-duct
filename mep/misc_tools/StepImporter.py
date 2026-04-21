import FreeCAD
import FreeCADGui
import Part
import math
import Import
import ComfacUtils
from compat import QtWidgets, QtCore, QtGui

class StepImporter:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path("Import.svg"), 
            'MenuText': "Universal Importer",
            'ToolTip': "Imports STEP files. Auto-aligns to a selected line if provided."
        }

    def Activated(self):
        sel = FreeCADGui.Selection.getSelectionEx()
        
        has_alignment = False
        mid_point = FreeCAD.Vector(0, 0, 0)
        tangent = FreeCAD.Vector(1, 0, 0)

        # 1. Check if the user selected a valid line to align to
        if sel and sel[0].Object.isDerivedFrom("Sketcher::SketchObject") and sel[0].SubObjects:
            selected_edge = sel[0].SubObjects[0]
            if isinstance(selected_edge, Part.Edge):
                try:
                    # Calculate center and orientation of the selected line
                    mid_param = (selected_edge.FirstParameter + selected_edge.LastParameter) / 2.0
                    mid_point = selected_edge.valueAt(mid_param)
                    tangent = selected_edge.tangentAt(mid_param).normalize()
                    has_alignment = True
                except Exception as e:
                    FreeCAD.Console.PrintWarning(f"Could not calculate alignment from selection: {e}\n")

        # 2. Setup the File Dialog for universal formats
        param = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/PipingsAutomation")
        last_path = param.GetString("LastSensorPath", "")
        
        file_filters = (
            "Supported CAD Files (*.step *.stp *.dwg *.dxf *.iges *.igs *.brep *.brp);;"
            "STEP Files (*.step *.stp);;"
            "AutoCAD 2D/3D (*.dwg *.dxf);;"
            "IGES Files (*.iges *.igs);;"
            "All Files (*.*)"
        )
        
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Select File to Import", last_path, file_filters)
        if not file_path:
            return 

        param.SetString("LastSensorPath", file_path) 

        doc = FreeCAD.ActiveDocument
        if not doc:
            doc = FreeCAD.newDocument("Imported_Data")

        existing_objs = set(doc.Objects)
        
        # 3. Import the file using FreeCAD's native format handler
        try:
            Import.insert(file_path, doc.Name)
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Import Error", f"Failed to import file:\n{str(e)}")
            return
            
        new_objs = list(set(doc.Objects) - existing_objs)
        if not new_objs: 
            return
            
        # 4. Group the imported objects cleanly into an App::Part container
        sensor_part = doc.addObject("App::Part", "Imported_Assembly")
        for obj in new_objs:
            try:
                sensor_part.addObject(obj)
            except:
                pass

        # 5. Apply the 3D alignment ONLY if a line was selected
        if has_alignment:
            rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), tangent)
            sensor_part.Placement = FreeCAD.Placement(mid_point, rotation)
        
        doc.recompute()

FreeCADGui.addCommand('StepImporter', StepImporter())