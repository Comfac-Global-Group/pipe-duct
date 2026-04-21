import FreeCAD
import FreeCADGui
from compat import QtWidgets, QtCore, QtGui

import ComfacUtils

class CustomNewSketch:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('Workbench_Sketcher.svg'), 
            'MenuText': "Create Body & Sketch",
            'ToolTip': "Creates a sketch in the active Body, or creates a new Body if none is active"
        }

    def Activated(self):
        # 1. Safety check: Create a new document if one doesn't exist
        if FreeCAD.ActiveDocument is None:
            FreeCAD.newDocument()

        needs_new_body = True
        
        # 2. SMART CHECK A: Is there already an active Body in the tree? (Bold blue stairs)
        try:
            active_body = FreeCADGui.ActiveDocument.ActiveView.getActiveObject("pdbody")
            if active_body is not None:
                needs_new_body = False
        except:
            pass
            
        # 3. SMART CHECK B: Did the user single-click select a Body in the tree?
        sel = FreeCADGui.Selection.getSelection()
        for obj in sel:
            if obj.isDerivedFrom("PartDesign::Body"):
                needs_new_body = False
                break

        # 4. Only generate a new Body if we actually need one
        if needs_new_body:
            FreeCADGui.runCommand('PartDesign_Body')
            # FORCE FREECAD TO CATCH UP: Let the GUI finish building the Body before moving on
            QtCore.QCoreApplication.processEvents()
        
        # 5. Trigger the Sketcher (it will automatically attach to the active/selected Body)
        FreeCADGui.runCommand('PartDesign_NewSketch')

FreeCADGui.addCommand('Custom_NewSketch', CustomNewSketch())