import os
import json
import FreeCAD
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils
# ==========================================================
# 2. 3D FLEXIBLE CONDUIT 
# ==========================================================
class FlexConduitTaskPanel:
    def __init__(self, sketch):
        self.sketch = sketch
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.preview = ComfacUtils.PreviewManager(FreeCAD.ActiveDocument, "FlexConduit_Preview")
        
        self.pipe_data = {}
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "PipeFlexConduitData.json")
        try:
            with open(data_path, 'r') as f:
                self.pipe_data = json.load(f)
        except: pass
        
        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(list(self.pipe_data.keys()))
        
        self.size_cb = QtWidgets.QComboBox()
        
        self.r_outer_spin = QtWidgets.QDoubleSpinBox()
        self.r_outer_spin.setRange(0.1, 1000.0)
        self.r_outer_spin.setDecimals(2)
        self.r_outer_spin.setSuffix(" mm")
        
        self.r_inner_spin = QtWidgets.QDoubleSpinBox()
        self.r_inner_spin.setRange(0.1, 1000.0)
        self.r_inner_spin.setDecimals(2)
        self.r_inner_spin.setSuffix(" mm")
        
        self.bend_radius_spin = QtWidgets.QDoubleSpinBox()
        self.bend_radius_spin.setRange(0.0, 5000.0)
        self.bend_radius_spin.setDecimals(2)
        self.bend_radius_spin.setSuffix(" mm")
        self.bend_radius_spin.setEnabled(False) 
        
        self.layout.addRow("Conduit Type:", self.type_cb)
        self.layout.addRow("Trade Size:", self.size_cb)
        self.layout.addRow("Outer Radius:", self.r_outer_spin)
        self.layout.addRow("Inner Radius:", self.r_inner_spin)
        self.layout.addRow("Calculated Bend Radius:", self.bend_radius_spin)
        
        self.type_cb.currentTextChanged.connect(self.update_sizes_dropdown)
        self.size_cb.currentTextChanged.connect(self.update_radius_inputs)
        self.r_outer_spin.valueChanged.connect(self.trigger_preview)
        self.r_inner_spin.valueChanged.connect(self.trigger_preview)
        self.bend_radius_spin.valueChanged.connect(self.trigger_preview)

        if self.type_cb.currentText():
            self.update_sizes_dropdown(self.type_cb.currentText())

    def trigger_preview(self):
        try:
            ptype = self.type_cb.currentText()
            psize = self.size_cb.currentText()
            if not ptype or not psize:
                return
            r_outer = self.r_outer_spin.value()
            r_inner = self.r_inner_spin.value()
            bend_radius = self.bend_radius_spin.value()
            
            if r_inner >= r_outer:
                self.preview.clear()
                return
                
            ghost_shape = self.build_geometry(r_outer, r_inner, bend_radius, ptype, psize, is_preview=True)
            if ghost_shape:
                color = (0.55, 0.57, 0.60) if "Liquid Tight" in ptype else (0.75, 0.78, 0.80)
                self.preview.update(ghost_shape, color=color)
        except:
            pass

    def update_sizes_dropdown(self, val_type):
        self.size_cb.blockSignals(True)
        self.size_cb.clear()
        if val_type in self.pipe_data:
            self.size_cb.addItems(list(self.pipe_data[val_type].keys()))
        self.size_cb.blockSignals(False)
        
        if self.size_cb.currentText():
            self.update_radius_inputs(self.size_cb.currentText())

    def update_radius_inputs(self, val_size):
        ptype = self.type_cb.currentText()
        if ptype and val_size and ptype in self.pipe_data and val_size in self.pipe_data[ptype]:
            pipe_od, pipe_wt = self.pipe_data[ptype][val_size]
            r_out = pipe_od / 2.0
            r_in = r_out - pipe_wt
            self.r_outer_spin.setValue(r_out)
            self.r_inner_spin.setValue(r_in)
            self.bend_radius_spin.setValue(pipe_od * 5.0)

    # --- ROUTING ENGINE LOGIC ---
    def get_junction_points(self, edges):
        endpoints = []
        for e in edges:
            endpoints.append(e.valueAt(e.FirstParameter))
            endpoints.append(e.valueAt(e.LastParameter))
        unique_pts = []
        for pt in endpoints:
            if not any(pt.isEqual(u, 0.001) for u in unique_pts):
                unique_pts.append(pt)
        junctions, abs_ends = [], []
        for pt in unique_pts:
            count = sum(1 for p in endpoints if pt.isEqual(p, 0.001))
            if count > 2: junctions.append(pt)
            elif count == 1: abs_ends.append(pt)
        return junctions, abs_ends

    def build_simple_paths(self, edges, junctions):
        broken_edges = []
        for e in edges:
            if not hasattr(e.Curve, 'TypeId') or e.Curve.TypeId != 'Part::GeomLine':
                broken_edges.append(e)
                continue
            
            p_s, p_e = e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)
            splits = [jp for jp in junctions if e.distToShape(Part.Vertex(jp))[0] < 0.001 and not jp.isEqual(p_s, 0.001) and not jp.isEqual(p_e, 0.001)]
            
            if not splits: broken_edges.append(e)
            else:
                splits.sort(key=lambda p: (p - p_s).Length)
                curr_p = p_s
                for sp in splits:
                    broken_edges.append(Part.makeLine(curr_p, sp))
                    curr_p = sp
                broken_edges.append(Part.makeLine(curr_p, p_e))

        paths, unprocessed = [], broken_edges[:]
        while unprocessed:
            e = unprocessed.pop(0)
            path = [e]
            while True:
                p_end = path[-1].valueAt(path[-1].LastParameter)
                if any(p_end.isEqual(jp, 0.001) for jp in junctions): break
                found = False
                for i, nxt in enumerate(unprocessed):
                    if nxt.valueAt(nxt.FirstParameter).isEqual(p_end, 0.001):
                        path.append(nxt); unprocessed.pop(i); found = True; break
                    elif nxt.valueAt(nxt.LastParameter).isEqual(p_end, 0.001):
                        path.append(Part.makeLine(nxt.valueAt(nxt.LastParameter), nxt.valueAt(nxt.FirstParameter)))
                        unprocessed.pop(i); found = True; break
                if not found: break
                
            while True:
                p_start = path[0].valueAt(path[0].FirstParameter)
                if any(p_start.isEqual(jp, 0.001) for jp in junctions): break
                found = False
                for i, prv in enumerate(unprocessed):
                    if prv.valueAt(prv.LastParameter).isEqual(p_start, 0.001):
                        path.insert(0, prv); unprocessed.pop(i); found = True; break
                    elif prv.valueAt(prv.FirstParameter).isEqual(p_start, 0.001):
                        path.insert(0, Part.makeLine(prv.valueAt(prv.LastParameter), prv.valueAt(prv.FirstParameter)))
                        unprocessed.pop(i); found = True; break
                if not found: break
            paths.append(path)
        return paths

    def fillet_wire_path(self, edges, bend_radius):
        if len(edges) < 2: return edges
        pts = [edges[0].valueAt(edges[0].FirstParameter)]
        for e in edges: pts.append(e.valueAt(e.LastParameter))
        
        final_edges = []
        p_start_node = pts[0]
        
        for i in range(1, len(pts)-1):
            p_corner, p_next = pts[i], pts[i+1]
            v1, v2 = (pts[i-1] - p_corner).normalize(), (p_next - p_corner).normalize()
            angle = v1.getAngle(v2)
            
            if angle < 0.01 or angle > 3.13:
                if (p_corner - p_start_node).Length > 0.001: final_edges.append(Part.makeLine(p_start_node, p_corner))
                p_start_node = p_corner
                continue
                
            actual_path_radius = max(0.1, bend_radius)
            bisector, deflection = (v1 + v2).normalize(), math.pi - angle
            T_required = actual_path_radius * math.tan(deflection / 2.0)
            
            L1, L2 = (p_corner - p_start_node).Length, (p_next - p_corner).Length
            if T_required > min(L1, L2) * 0.49:
                T_required = min(L1, L2) * 0.49
                actual_path_radius = T_required / math.tan(deflection / 2.0)
                
            p_tan1, p_tan2 = p_corner + v1 * T_required, p_corner + v2 * T_required
            if (p_tan1 - p_start_node).Length > 0.001: final_edges.append(Part.makeLine(p_start_node, p_tan1))
                
            dist_O = T_required / math.sin(deflection / 2.0)
            O = p_corner + bisector * dist_O
            mid_arc_pt = O - bisector * actual_path_radius
            
            try: final_edges.append(Part.Arc(p_tan1, mid_arc_pt, p_tan2).toShape())
            except Exception: final_edges.append(Part.makeLine(p_tan1, p_tan2))
            p_start_node = p_tan2
            
        if (pts[-1] - p_start_node).Length > 0.001: final_edges.append(Part.makeLine(p_start_node, pts[-1]))
        return final_edges

    def accept(self):
        ptype, psize = self.type_cb.currentText(), self.size_cb.currentText()
        r_outer, r_inner = self.r_outer_spin.value(), self.r_inner_spin.value()
        bend_radius = self.bend_radius_spin.value()

        if not ptype or not psize:
            self.preview.clear()
            FreeCADGui.Control.closeDialog()
            return True
            
        if r_inner >= r_outer:
            QtWidgets.QMessageBox.warning(None, "Error", "Inner Radius must be smaller than Outer Radius.")
            return False 

        final_shape = self.build_geometry(r_outer, r_inner, bend_radius, ptype, psize, is_preview=False)
        if not final_shape:
            return False

        self.preview.clear()
        FreeCADGui.Control.closeDialog()
        self.commit_flex_pipe(final_shape, ptype, psize, r_outer, r_inner, bend_radius)
        return True

    def reject(self):
        self.preview.clear()
        FreeCADGui.Control.closeDialog()
        return True

    def build_geometry(self, r_outer, r_inner, bend_radius, ptype, psize, is_preview=False):
        """PURE MATH: Returns the booleaned flex shape without modifying the FreeCAD Tree."""
        pipe_od = r_outer * 2.0
        pipe_wt = r_outer - r_inner
        is_lfmc = "Liquid Tight" in ptype
        target_metal_pitch = max(3.5, pipe_od * 0.15)

        r_metal_peak = r_inner + (pipe_wt * 0.5) if is_lfmc else r_outer
        r_metal_base = r_inner + (pipe_wt * 0.1) if is_lfmc else r_inner + (pipe_wt * 0.3)

        def robust_fuse(shape_list):
            if not shape_list: return None
            if len(shape_list) == 1: return shape_list[0].removeSplitter()
            try:
                master = shape_list[0].multiFuse(shape_list[1:])
                return master.removeSplitter()
            except:
                master = shape_list[0]
                for s in shape_list[1:]: master = master.fuse(s)
                return master.removeSplitter()

        def build_straight_tube(r_in, r_base, r_peak, target_len, style):
            if target_len < 0.001: return None
            num_ribs = max(1, round(target_len / target_metal_pitch))
            pitch = target_len / num_ribs 
            pts = [FreeCAD.Vector(r_in, 0, 0)]
            
            for i in range(num_ribs):
                z = i * pitch
                if style == "Metal":
                    if i == 0: pts.append(FreeCAD.Vector(r_peak, 0, z))
                    pts.append(FreeCAD.Vector(r_base, 0, z + pitch * 0.5))
                    pts.append(FreeCAD.Vector(r_peak, 0, z + pitch))
                else:
                    if i == 0: pts.append(FreeCAD.Vector(r_peak, 0, z))
                    pts.append(FreeCAD.Vector(r_peak, 0, z + pitch * 0.4))
                    pts.append(FreeCAD.Vector(r_base, 0, z + pitch * 0.5))
                    pts.append(FreeCAD.Vector(r_peak, 0, z + pitch * 0.6))
                    pts.append(FreeCAD.Vector(r_peak, 0, z + pitch))

            pts.append(FreeCAD.Vector(r_in, 0, target_len))
            pts.append(FreeCAD.Vector(r_in, 0, 0))
            return Part.Face(Part.Wire(Part.makePolygon(pts))).revolve(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), 360)

        def make_straight_segment(target_len, strip_start, strip_end):
            final_metal = build_straight_tube(r_inner, r_metal_base, r_metal_peak, target_len, "Metal")
            if is_lfmc:
                strip_len = min(30.0, target_len * 0.15) 
                z_offset = strip_len if strip_start else 0.0
                jacket_len = target_len - (strip_len if strip_start else 0.0) - (strip_len if strip_end else 0.0)
                
                if jacket_len > 0:
                    final_jacket = build_straight_tube(r_metal_peak - 0.05, r_metal_peak + (pipe_wt * 0.1), r_outer, jacket_len, "PVC")
                    if final_jacket:
                        final_jacket.transformShape(FreeCAD.Placement(FreeCAD.Vector(0, 0, z_offset), FreeCAD.Rotation()).toMatrix())
                        return final_metal.fuse(final_jacket).removeSplitter()
            return final_metal

        def make_curved_segment(edge, strip_start, strip_end):
            arc_len = edge.Length
            if arc_len < 0.001: return None
            
            num_ribs = max(1, round(arc_len / target_metal_pitch))
            pitch = arc_len / num_ribs 
            strip_len = min(30.0, arc_len * 0.15) if is_lfmc else 0.0
            
            def sweep_solid(e, r):
                w = Part.Wire(Part.makeCircle(r))
                v_start = e.valueAt(e.FirstParameter)
                tan = e.tangentAt(e.FirstParameter).normalize()
                z_axis = FreeCAD.Vector(0,0,1)
                rot = FreeCAD.Rotation() if tan.isEqual(z_axis, 1e-5) else (FreeCAD.Rotation(FreeCAD.Vector(1,0,0), 180) if tan.isEqual(FreeCAD.Vector(0,0,-1), 1e-5) else FreeCAD.Rotation(z_axis.cross(tan), math.degrees(z_axis.getAngle(tan))))
                w.transformShape(FreeCAD.Placement(v_start, rot).toMatrix())
                return Part.Wire(e).makePipeShell([w], True, True)

            if not is_lfmc:
                base_pipe = sweep_solid(edge, r_metal_peak)
            else:
                base_parts = []
                t_start = strip_len / arc_len if strip_start else 0.0
                t_end = (arc_len - strip_len) / arc_len if strip_end else 1.0
                
                if t_start > 0:
                    base_parts.append(sweep_solid(Part.Edge(edge.Curve, edge.FirstParameter, edge.FirstParameter + (edge.LastParameter - edge.FirstParameter)*t_start), r_metal_peak))
                if t_end > t_start:
                    base_parts.append(sweep_solid(Part.Edge(edge.Curve, edge.FirstParameter + (edge.LastParameter - edge.FirstParameter)*t_start, edge.FirstParameter + (edge.LastParameter - edge.FirstParameter)*t_end), r_outer))
                if t_end < 1.0:
                    base_parts.append(sweep_solid(Part.Edge(edge.Curve, edge.FirstParameter + (edge.LastParameter - edge.FirstParameter)*t_end, edge.LastParameter), r_metal_peak))
                    
                base_pipe = robust_fuse(base_parts)

            cutters = []
            r_max_cut = r_outer * 1.5
            
            def make_v_cutter(r_clear, r_surf, r_bot, w_surf, pt, tan):
                if r_surf - r_bot < 0.001: w_max = w_surf
                else: w_max = w_surf + (w_surf / (r_surf - r_bot)) * (r_clear - r_surf)
                
                p1 = FreeCAD.Vector(r_clear, 0, -w_max/2.0)
                p2 = FreeCAD.Vector(r_bot, 0, 0)
                p3 = FreeCAD.Vector(r_clear, 0, w_max/2.0)
                face = Part.Face(Part.Wire(Part.makePolygon([p1, p2, p3, p1])))
                cutter = face.revolve(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), 360)
                
                z_axis = FreeCAD.Vector(0,0,1)
                rot = FreeCAD.Rotation() if tan.isEqual(z_axis, 1e-5) else (FreeCAD.Rotation(FreeCAD.Vector(1,0,0), 180) if tan.isEqual(FreeCAD.Vector(0,0,-1), 1e-5) else FreeCAD.Rotation(z_axis.cross(tan), math.degrees(z_axis.getAngle(tan))))
                cutter.transformShape(FreeCAD.Placement(pt, rot).toMatrix())
                return cutter

            for i in range(num_ribs):
                dist = i * pitch
                is_stripped = False
                if is_lfmc:
                    if strip_start and dist < strip_len: is_stripped = True
                    if strip_end and dist > (arc_len - strip_len): is_stripped = True
                
                center_dist = dist + pitch * 0.5
                if center_dist > arc_len: break
                
                param = edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) * (center_dist / arc_len)
                pt = edge.valueAt(param)
                tan = edge.tangentAt(param).normalize()
                
                if not is_lfmc or is_stripped:
                    cutters.append(make_v_cutter(r_max_cut, r_metal_peak, r_metal_base, pitch, pt, tan))
                else:
                    r_pvc_base = r_metal_peak + (pipe_wt * 0.1)
                    cutters.append(make_v_cutter(r_max_cut, r_outer, r_pvc_base, pitch * 0.2, pt, tan))
                    
            inner_hole = sweep_solid(edge, r_inner)
            
            if cutters:
                chunk_size = 50
                corrugated = base_pipe
                for i in range(0, len(cutters), chunk_size):
                    chunk = Part.Compound(cutters[i:i+chunk_size])
                    corrugated = corrugated.cut(chunk)
            else:
                corrugated = base_pipe
                
            return corrugated.cut(inner_hole).removeSplitter()

        try:
            sketch_mat = self.sketch.getGlobalPlacement().toMatrix() if hasattr(self.sketch, 'getGlobalPlacement') else self.sketch.Placement.toMatrix()
            global_shape = self.sketch.Shape.copy()
            global_shape.transformShape(sketch_mat)
            
            edges = [e for e in global_shape.Edges if e.Length > 0.001]
            junctions, abs_ends = self.get_junction_points(edges)

            if len(junctions) > 0:
                if not is_preview:
                    raise ValueError(
                        "T-Junction or Branching Path Detected!\n\n"
                        "Flexible conduit is a single continuous tube and cannot branch "
                        "into multiple directions without a solid junction box.\n\n"
                        "Please edit your sketch to be a single, unbroken line path."
                    )
                return None

            simple_paths = self.build_simple_paths(edges, junctions)
            shapes_to_fuse = []

            for path_edges in simple_paths:
                processed_edges = self.fillet_wire_path(path_edges, bend_radius)
                
                for edge in processed_edges:
                    v1, v2 = edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)
                    strip_start = any((v1 - ep).Length < 0.001 for ep in abs_ends)
                    strip_end = any((v2 - ep).Length < 0.001 for ep in abs_ends)
                    
                    if isinstance(edge.Curve, Part.Line):
                        d_vec = (v2 - v1).normalize()
                        z_axis = FreeCAD.Vector(0,0,1)
                        rot = FreeCAD.Rotation() if d_vec.isEqual(z_axis, 1e-5) else (FreeCAD.Rotation(FreeCAD.Vector(1,0,0), 180) if d_vec.isEqual(FreeCAD.Vector(0,0,-1), 1e-5) else FreeCAD.Rotation(z_axis.cross(d_vec), math.degrees(z_axis.getAngle(d_vec))))
                            
                        seg = make_straight_segment(edge.Length, strip_start, strip_end)
                        if seg:
                            seg.transformShape(FreeCAD.Placement(v1, rot).toMatrix())
                            shapes_to_fuse.append(seg)
                    else:
                        seg = make_curved_segment(edge, strip_start, strip_end)
                        if seg:
                            shapes_to_fuse.append(seg)

            if not shapes_to_fuse: 
                return None
                
            return robust_fuse(shapes_to_fuse)
        except:
            return None

    def commit_flex_pipe(self, final_shape, ptype, psize, r_outer, r_inner, bend_radius):
        """TREE COMMIT: Adds the final shape to the document."""
        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Create Flex Conduit")
        try:
            is_lfmc = "Liquid Tight" in ptype
            color = (0.55, 0.57, 0.60) if is_lfmc else (0.75, 0.78, 0.80)
            feature_name = "LFMC_Conduit" if is_lfmc else "FMC_Conduit"

            obj = doc.addObject("Part::Feature", feature_name)
            obj.Shape = final_shape

            try:
                obj.addProperty("App::PropertyString", "Standard", "ConduitData", "Conduit Type").Standard = ptype
                obj.addProperty("App::PropertyString", "Size", "ConduitData", "Trade Size").Size = psize
                obj.addProperty("App::PropertyLength", "OuterRadius", "ConduitData", "Outer Radius").OuterRadius = r_outer
                obj.addProperty("App::PropertyLength", "InnerRadius", "ConduitData", "Inner Radius").InnerRadius = r_inner
                obj.addProperty("App::PropertyLength", "BendRadius", "ConduitData", "Bend Radius").BendRadius = bend_radius
            except: pass

            if hasattr(obj, "ViewObject"): obj.ViewObject.ShapeColor = color
            if hasattr(obj, "Refine"): obj.Refine = True
                
            doc.recompute()
            FreeCADGui.updateGui()
            doc.commitTransaction()
            
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Error", f"Failed to generate flex conduit.\n\n{e}")

class CreateFlexConduitCommand:
    def GetResources(self):
        try:
            icon_path = ComfacUtils.get_icon_path('FlexPipe.svg')
        except:
            icon_path = "" 
        return {
            'Pixmap': icon_path, 
            'MenuText': "Generate 3D Flex Conduit",
            'ToolTip': "Generates seamless flex conduit with active sketch error prevention."
        }

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        if not sel or not hasattr(sel[0], "Shape") or len(sel[0].Shape.Edges) == 0:
            QtWidgets.QMessageBox.warning(None, "Error", "Select a valid 3D route or Sketch in the tree first!")
            return
            
        panel = FlexConduitTaskPanel(sel[0])
        FreeCADGui.Control.showDialog(panel)

FreeCADGui.addCommand('CreateFlexConduit', CreateFlexConduitCommand())