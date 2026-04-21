import FreeCADGui
import FreeCAD as App
import ComfacUtils

class CustomNewPartBody:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('Workbench_PartDesign.svg'), 
            'MenuText': "Create Body",
            'ToolTip': "Create a new body without leaving the workbench"
        }

    def Activated(self):
        doc = App.activeDocument()
        if not doc:
            return
        # Use return value of addObject to avoid naming collisions
        new_body = doc.addObject('PartDesign::Body','Body')
        new_body.Label = 'Body'
        doc.recompute()

FreeCADGui.addCommand('Custom_NewPartBody', CustomNewPartBody())
