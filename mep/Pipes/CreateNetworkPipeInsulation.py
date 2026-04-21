import FreeCAD as App
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils

class PipeInsulationTaskPanel:
    def __init__(self, folder_obj):
        self.folder_obj = folder_obj
        
        # 1. Extract Intelligence from the Smart Folder
        self.sketches = getattr(folder_obj, "LinkedSketches", [])
        
        # Extract Universal Pipe OD safely
        raw_od = getattr(folder_obj, "PipeOuterDiameter", None)
        if raw_od is None:
            for child in folder_obj.Group:
                if hasattr(child, "PipeOuter"):
                    raw_od = child.PipeOuter
                    break
                elif hasattr(child, "PipeOuterDiameter"):
                    raw_od = child.PipeOuterDiameter
                    break
                    
        try:
            self.pipe_od = raw_od.Value if hasattr(raw_od, 'Value') else float(raw_od)
            if self.pipe_od <= 0: self.pipe_od = 50.0
        except:
            self.pipe_od = 50.0

        # 2. Gather all 3D objects for counts and hollow cutouts
        self.system_shapes = []
        def gather_shapes(grp):
            for child in grp.Group:
                if child not in self.sketches:
                    if child.isDerivedFrom("Part::Feature") and child.Shape and not child.Shape.isNull():
                        if "insulation" not in child.Name.lower() and "preview" not in child.Name.lower():
                            self.system_shapes.append(child)
                    elif child.isDerivedFrom("App::DocumentObjectGroup"):
                        gather_shapes(child)
        
        gather_shapes(self.folder_obj)

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        pipe_text = f"Network OD: {self.pipe_od:.1f} mm"
        fit_text = f"{len(self.system_shapes)} parts to be covered"

        self.detected_pipes = QtWidgets.QLabel(pipe_text)
        self.detected_fit = QtWidgets.QLabel(fit_text)

        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.1, 500.0)
        self.thick_input.setValue(25.0)
        self.thick_input.setDecimals(2)
        self.thick_input.setSuffix(" mm")

        self.layout.addRow("System Data:", self.detected_pipes)
        self.layout.addRow("Fittings Detected:", self.detected_fit)
        self.layout.addRow("Insulation Thickness:", self.thick_input)

        self.preview = ComfacUtils.PreviewManager(App.ActiveDocument, "PipeInsulation_Preview")
        self.thick_input.valueChanged.connect(self.trigger_preview)
        self.trigger_preview()

    def trigger_preview(self):
        insul_thick = self.thick_input.value()
        ghost_shape = self.build_insulation_shape(insul_thick, is_preview=True)
        
        if ghost_shape:
            self.preview.update(ghost_shape, color=(0.8, 0.8, 0.8))
        else:
            self.preview.clear()

    def accept(self):
        insul_thick = self.thick_input.value()
        final_shape = self.build_insulation_shape(insul_thick, is_preview=False)
        
        if not final_shape:
            return 

        self.preview.clear()
        FreeCADGui.Control.closeDialog()
        self.commit_insulation(final_shape)

    def reject(self):
        self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def build_insulation_shape(self, thick, is_preview=False):
        all_outer_shapes = []
        all_inner_shapes = []

        try:
            # FIX: Add a tiny 0.2mm clearance offset so it never z-fights "inside" the pipe
            insul_id = self.pipe_od + 0.2
            insul_od = insul_id + (2 * thick)

            for sketch in self.sketches:
                if not sketch.Shape: continue
                valid_edges = [edge for edge in sketch.Shape.Edges if edge.Length > 0.001]

                for edge in valid_edges:
                    start_param = edge.FirstParameter
                    start_pt = edge.valueAt(start_param)
                    tangent = edge.tangentAt(start_param)
                    
                    circ_out = Part.Circle(start_pt, tangent, insul_od/2.0)
                    prof_out = Part.Wire([circ_out.toShape()])
                    all_outer_shapes.append(Part.Wire([edge]).makePipeShell([prof_out], True, True))
                    
                    circ_in = Part.Circle(start_pt, tangent, insul_id/2.0)
                    prof_in = Part.Wire([circ_in.toShape()])
                    all_inner_shapes.append(Part.Wire([edge]).makePipeShell([prof_in], True, True))

                endpoints = []
                for edge in valid_edges:
                    endpoints.append(edge.Vertexes[0].Point)
                    endpoints.append(edge.Vertexes[-1].Point)

                intersection_points = []
                for pt in endpoints:
                    count = sum(1 for p in endpoints if pt.isEqual(p, 0.001))
                    if count > 1 and not any(pt.isEqual(ipt, 0.001) for ipt in intersection_points):
                        intersection_points.append(pt)

                for pt in intersection_points:
                    all_outer_shapes.append(Part.makeSphere(insul_od/2.0, pt))
                    all_inner_shapes.append(Part.makeSphere(insul_id/2.0, pt))

            if not all_outer_shapes: 
                return None

            # Safely fuse outer boundaries
            master_outer = ComfacUtils.fuse_shapes(all_outer_shapes)
            
            # FIX: Gather the generic sweeps AND the actual 3D fittings so the foam perfectly hugs the elbows
            inner_components = list(all_inner_shapes)
            for sys_obj in self.system_shapes:
                if hasattr(sys_obj, "Shape") and not sys_obj.Shape.isNull():
                    inner_components.append(sys_obj.Shape)
            
            master_inner = ComfacUtils.fuse_shapes(inner_components)
            
            if not master_outer or not master_inner:
                return None
                
            # Cut the exact pipe geometry (and fittings) out of the outer insulation shell
            final_cut = master_outer.cut(master_inner).removeSplitter()
            return final_cut
            
        except Exception as e:
            if not is_preview: App.Console.PrintError(f"Insulation build failed: {e}\n")
            return None

    def commit_insulation(self, final_shape):
        doc = App.ActiveDocument
        doc.openTransaction("Add System Insulation")
        
        try:
            obj = doc.addObject("Part::Feature", "System_Insulation")
            obj.Shape = final_shape
            self.folder_obj.addObject(obj)

            if hasattr(obj.ViewObject, "Transparency"):
                obj.ViewObject.Transparency = 60
                obj.ViewObject.ShapeColor = (0.8, 0.8, 0.8)
                
            if hasattr(obj, "Refine"):
                obj.Refine = True
            
            doc.recompute()
            doc.commitTransaction()
            
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Error", f"Failed to place insulation.\n\n{e}")

class CreatePipeInsulation:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('Pipe_Insulation.svg'), 
            'MenuText': "Add Pipe Insulation",
            'ToolTip': "Select a Pipe System folder (or any pipe inside it) to add insulation"
        }

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        
        if not sel:
            QtWidgets.QMessageBox.warning(None, "Selection Error", "Please select a Pipe System folder (or any pipe inside it) in the tree or 3D view!")
            return
            
        obj = sel[0]
        folder = None

        if obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(obj, "LinkedSketches"):
            folder = obj
        else:
            for parent in obj.InList:
                if parent.isDerivedFrom("App::DocumentObjectGroup") and hasattr(parent, "LinkedSketches"):
                    folder = parent
                    break
                for grand_parent in parent.InList:
                    if grand_parent.isDerivedFrom("App::DocumentObjectGroup") and hasattr(grand_parent, "LinkedSketches"):
                        folder = grand_parent
                        break

        if not folder:
            QtWidgets.QMessageBox.warning(None, "Selection Error", "Could not find the master Smart Folder.\n\nPlease make sure you are selecting a pipe system generated by the Pipe Libraries or Pipe Network tool.")
            return

        panel = PipeInsulationTaskPanel(folder)
        FreeCADGui.Control.showDialog(panel)

try:
    FreeCADGui.addCommand('CreateNetworkPipeInsulation', CreatePipeInsulation())
except:
    pass