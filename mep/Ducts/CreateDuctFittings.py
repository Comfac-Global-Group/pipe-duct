import FreeCAD
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui
import Ducts.DuctGeometryUtils as DuctGeometryUtils

try:
    import ComfacUtils
except ImportError:
    pass

class DuctFittingTaskPanel:
    def __init__(self, target_folder):
        self.target_obj = target_folder
        self.props = self.get_duct_props(target_folder)
        
        if not self.props:
            raise ValueError("Invalid Target for Fittings")

        self.sketch = FreeCAD.ActiveDocument.getObject(self.props["sketch_name"])

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        self.duct_w = self.props["w"]
        self.duct_h = self.props["h"]
        self.duct_r = self.props["r"]
        self.duct_th = self.props["th"]

        self.detected_w = QtWidgets.QLabel(f"{self.duct_w:.2f} mm")
        self.detected_h = QtWidgets.QLabel(f"{self.duct_h:.2f} mm")
        self.detected_th = QtWidgets.QLabel(f"{self.duct_th:.2f} mm")

        self.clearance_input = QtWidgets.QDoubleSpinBox()
        self.clearance_input.setRange(0.0, 50.0)
        self.clearance_input.setValue(0.0)
        self.clearance_input.setDecimals(2)
        self.clearance_input.setSuffix(" mm")

        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.1, 500.0)
        self.thick_input.setValue(2.0)
        self.thick_input.setDecimals(2)
        self.thick_input.setSuffix(" mm")

        self.length_input = QtWidgets.QDoubleSpinBox()
        self.length_input.setRange(1.0, 1000.0)
        self.length_input.setValue(50.0)
        self.length_input.setDecimals(2)
        self.length_input.setSuffix(" mm")

        self.layout.addRow("Base Duct Width:", self.detected_w)
        self.layout.addRow("Base Duct Height:", self.detected_h)
        self.layout.addRow("Detected Duct Wall:", self.detected_th)
        self.layout.addRow(QtWidgets.QLabel(""))
        self.layout.addRow("Slip-Fit Clearance Gap:", self.clearance_input)
        self.layout.addRow("Fitting Wall Thickness:", self.thick_input)
        self.layout.addRow("Collar Depth (Overlap):", self.length_input)

        self.preview = ComfacUtils.PreviewManager(FreeCAD.ActiveDocument, "DuctFitting_Preview") if 'ComfacUtils' in globals() else None
        
        self.clearance_input.valueChanged.connect(self.trigger_preview)
        self.thick_input.valueChanged.connect(self.trigger_preview)
        self.length_input.valueChanged.connect(self.trigger_preview)
        self.trigger_preview()

    def get_duct_props(self, obj):
        """Extracts unified properties from Hollow or Solid Smart Folders."""
        if hasattr(obj, "DuctWidth"):
            return {
                "w": float(obj.DuctWidth),
                "h": float(getattr(obj, 'DuctHeight', getattr(obj, 'DuctDepth', obj.DuctWidth))),
                "r": float(getattr(obj, 'DuctRadius', 0.0)),
                "th": float(getattr(obj, 'DuctThickness', 2.0)),
                "profile": getattr(obj, "DuctProfileType", "Rectangular"),
                "corner": getattr(obj, "DuctCornerType", "Rounded"),
                "align": getattr(obj, "DuctAlignment", "Center"),
                "sketch_name": getattr(obj, "LinkedDuctSketchName", getattr(obj, "SketchName", ""))
            }
        elif hasattr(obj, "SolidWidth"):
            return {
                "w": float(obj.SolidWidth),
                "h": float(getattr(obj, 'SolidDepth', obj.SolidWidth)),
                "r": float(getattr(obj, 'SolidRadius', 0.0)),
                "th": 0.0, # CFD domains are solid
                "profile": getattr(obj, "SolidProfileType", "Rectangular"),
                "corner": getattr(obj, "SolidCornerType", "Rounded"),
                "align": getattr(obj, "SolidAlignment", "Center"),
                "sketch_name": getattr(obj, "LinkedSolidSketchName", "")
            }
        return None

    def trigger_preview(self):
        if not self.preview: return
        try:
            fit_thick = self.thick_input.value()
            sock_len = self.length_input.value()
            clearance = self.clearance_input.value()

            fit_in_w = self.duct_w + (2 * self.duct_th) + (2 * clearance)
            fit_in_h = self.duct_h + (2 * self.duct_th) + (2 * clearance)
            fit_in_r = self.duct_r + self.duct_th + clearance

            fit_out_w = fit_in_w + (2 * fit_thick)
            fit_out_h = fit_in_h + (2 * fit_thick)
            fit_out_r = fit_in_r + fit_thick

            ghost_shape = self.build_fitting_geometry(fit_out_w, fit_out_h, fit_out_r, fit_in_w, fit_in_h, fit_in_r, sock_len)
            if ghost_shape:
                self.preview.update(ghost_shape, color=(0.4, 0.4, 0.4))
        except: pass

    def build_fitting_geometry(self, fit_out_w, fit_out_h, fit_out_r, fit_in_w, fit_in_h, fit_in_r, sock_len):
        outer_shapes, inner_shapes = [], []

        sketch_normal = self.sketch.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        profile_type = self.props["profile"]
        corner_type = self.props["corner"]
        alignment = self.props["align"]

        calc_inner_rad = self.duct_h * 0.5
        offset_val = 0.0
        if alignment == "Inner": offset_val = -(self.duct_w / 2.0)
        elif alignment == "Outer": offset_val = (self.duct_w / 2.0)

        edges = [e for e in self.sketch.Shape.Edges if e.Length > 0.001]
        junctions = self.get_junction_points(edges)
        simple_paths = self.build_simple_paths(edges, junctions)

        valid_edges = []
        for path_edges in simple_paths:
            if corner_type == "Rounded":
                proc_edges = self.fillet_wire_path(path_edges, sketch_normal, self.duct_w, offset_val, calc_inner_rad)
            else:
                proc_edges = path_edges
            
            for edge in proc_edges:
                if edge.Length > 0.001: 
                    e_tangent = edge.tangentAt(edge.FirstParameter).normalize()
                    cur_x_dir = sketch_normal.cross(e_tangent).normalize()
                    valid_edges.append((edge, cur_x_dir))

        def is_straight_edge(e):
            try: return hasattr(e.Curve, 'TypeId') and e.Curve.TypeId == 'Part::GeomLine'
            except: return False

        def has_arc_at(pt):
            for e, xd in valid_edges:
                if e.distToShape(Part.Vertex(pt))[0] < 0.001 and not is_straight_edge(e): return True
            return False

        all_endpoints = []
        for edge, xd in valid_edges:
            all_endpoints.append(edge.valueAt(edge.FirstParameter))
            all_endpoints.append(edge.valueAt(edge.LastParameter))

        intersection_points = []
        for pt in all_endpoints:
            deg = 0
            for edge, xd in valid_edges:
                if edge.distToShape(Part.Vertex(pt))[0] < 0.001:
                    is_start = edge.valueAt(edge.FirstParameter).isEqual(pt, 0.001)
                    is_end = edge.valueAt(edge.LastParameter).isEqual(pt, 0.001)
                    deg += 1 if (is_start or is_end) else 2
            
            if deg > 1 and not any(pt.isEqual(ipt, 0.001) for ipt in intersection_points):
                intersection_points.append(pt)

        for pt in intersection_points:
            if not has_arc_at(pt):
                raw_dirs = []
                unique_offsets = []
                for edge, true_x_dir in valid_edges:
                    if is_straight_edge(edge) and edge.distToShape(Part.Vertex(pt))[0] < 0.01:
                        p_start = edge.valueAt(edge.FirstParameter)
                        p_end = edge.valueAt(edge.LastParameter)
                        
                        dist_s = (p_start - pt).Length
                        dist_e = (p_end - pt).Length
                        
                        v_off = true_x_dir * offset_val
                        if not any((uo - v_off).Length < 1.0 for uo in unique_offsets):
                            unique_offsets.append(v_off)
                        
                        if dist_s < 1.0: 
                            swp_dir = (p_end - p_start).normalize()
                            raw_dirs.append((swp_dir, true_x_dir))
                        elif dist_e < 1.0: 
                            swp_dir = (p_start - p_end).normalize()
                            raw_dirs.append((swp_dir, true_x_dir))
                        else: 
                            vec1 = (p_end - pt).normalize()
                            vec2 = (p_start - pt).normalize()
                            raw_dirs.append((vec1, true_x_dir))
                            raw_dirs.append((vec2, true_x_dir))

                v_combined = FreeCAD.Vector(0,0,0)
                for vo in unique_offsets: v_combined += vo
                shifted_pt = pt + v_combined

                unique_dirs = []
                for swp_dir, x_dir in raw_dirs:
                    if not any((ud[0] - swp_dir).Length < 0.01 for ud in unique_dirs):
                        unique_dirs.append((swp_dir, x_dir))

                for swp_dir, true_x_dir in unique_dirs:
                    p0_out = shifted_pt - swp_dir * (max(fit_out_w, fit_out_h) / 2.0)
                    p1_out = shifted_pt + swp_dir * sock_len
                    edge_out = Part.makeLine(p0_out, p1_out)
                    
                    prof_out = self.create_profile(fit_out_w, fit_out_h, fit_out_r, p0_out, swp_dir, sketch_normal, profile_type, offset_val=0.0)
                    outer_shapes.append(Part.Wire([edge_out]).makePipeShell([prof_out], True, False, 2))
                    
                    p0_in = shifted_pt - swp_dir * (max(fit_in_w, fit_in_h) / 2.0)
                    p1_in = shifted_pt + swp_dir * (sock_len + 10.0)
                    edge_in = Part.makeLine(p0_in, p1_in)
                    
                    prof_in = self.create_profile(fit_in_w, fit_in_h, fit_in_r, p0_in, swp_dir, sketch_normal, profile_type, offset_val=0.0)
                    inner_shapes.append(Part.Wire([edge_in]).makePipeShell([prof_in], True, False, 2))

        for edge, cur_x_dir in valid_edges:
            if not is_straight_edge(edge):
                p_start = edge.valueAt(edge.FirstParameter)
                p_end = edge.valueAt(edge.LastParameter)
                tangent_s = edge.tangentAt(edge.FirstParameter).normalize()
                tangent_e = edge.tangentAt(edge.LastParameter).normalize()
                
                prof_out = self.create_profile(fit_out_w, fit_out_h, fit_out_r, p_start, tangent_s, sketch_normal, profile_type, offset_val=offset_val)
                outer_shapes.append(Part.Wire([edge]).makePipeShell([prof_out], True, True, 2))
                
                prof_in = self.create_profile(fit_in_w, fit_in_h, fit_in_r, p_start, tangent_s, sketch_normal, profile_type, offset_val=offset_val)
                inner_shapes.append(Part.Wire([edge]).makePipeShell([prof_in], True, True, 2))
                
                edge_in_s = Part.makeLine(p_start - tangent_s * 10.0, p_start + tangent_s * 5.0)
                prof_in_s = self.create_profile(fit_in_w, fit_in_h, fit_in_r, p_start - tangent_s * 10.0, tangent_s, sketch_normal, profile_type, offset_val=offset_val)
                inner_shapes.append(Part.Wire([edge_in_s]).makePipeShell([prof_in_s], True, False, 2))
                
                edge_in_e = Part.makeLine(p_end - tangent_e * 5.0, p_end + tangent_e * 10.0)
                prof_in_e = self.create_profile(fit_in_w, fit_in_h, fit_in_r, p_end - tangent_e * 5.0, tangent_e, sketch_normal, profile_type, offset_val=offset_val)
                inner_shapes.append(Part.Wire([edge_in_e]).makePipeShell([prof_in_e], True, False, 2))

        if not outer_shapes: return None

        master_outer = outer_shapes[0]
        for shape in outer_shapes[1:]: master_outer = master_outer.fuse(shape)
        
        master_inner = inner_shapes[0]
        for shape in inner_shapes[1:]: master_inner = master_inner.fuse(shape)
        
        return master_outer.cut(master_inner).removeSplitter()

    def accept(self):
        fit_thick = self.thick_input.value()
        sock_len = self.length_input.value()
        clearance = self.clearance_input.value()

        fit_in_w = self.duct_w + (2 * self.duct_th) + (2 * clearance)
        fit_in_h = self.duct_h + (2 * self.duct_th) + (2 * clearance)
        fit_in_r = self.duct_r + self.duct_th + clearance

        fit_out_w = fit_in_w + (2 * fit_thick)
        fit_out_h = fit_in_h + (2 * fit_thick)
        fit_out_r = fit_in_r + fit_thick

        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()

        progress = QtWidgets.QProgressDialog("Generating Duct Fittings...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Computing Geometry")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            final_shape = self.build_fitting_geometry(fit_out_w, fit_out_h, fit_out_r, fit_in_w, fit_in_h, fit_in_r, sock_len)
            if final_shape:
                self.commit_fittings(final_shape)
        finally:
            progress.close()

    def reject(self):
        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def commit_fittings(self, final_shape):
        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Add Duct Fittings")
        try:
            parent_container = None
            is_body = False
            for parent in self.target_obj.InList:
                if parent.isDerivedFrom("PartDesign::Body"):
                    parent_container = parent; is_body = True; break
                elif parent.isDerivedFrom("App::Part") or parent.isDerivedFrom("App::DocumentObjectGroup"):
                    parent_container = parent

            if is_body:
                raw_fit = doc.addObject("Part::Feature", "Raw_Duct_Fittings")
                raw_fit.Shape = final_shape; raw_fit.ViewObject.Visibility = False 
                obj = parent_container.newObject("PartDesign::FeatureBase", "Duct_Fittings")
                obj.BaseFeature = raw_fit
            else:
                obj = doc.addObject("Part::Feature", "Duct_Fittings")
                obj.Shape = final_shape
                if parent_container: 
                    parent_container.addObject(obj)
                else:
                    if self.target_obj.isDerivedFrom("App::DocumentObjectGroup"):
                        self.target_obj.addObject(obj)

            obj.ViewObject.ShapeColor = (0.4, 0.4, 0.4)
            if hasattr(obj, "Refine"): obj.Refine = True
            doc.recompute()
            doc.commitTransaction()
            
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Error", f"Failed to generate fittings.\n\nError: {e}")

    # ========================================================
    # PRESERVED INTERNAL GEOMETRY METHODS
    # ========================================================
    def get_junction_points(self, edges):
        endpoints = []
        for e in edges:
            endpoints.append(e.valueAt(e.FirstParameter))
            endpoints.append(e.valueAt(e.LastParameter))
        unique_pts = []
        for pt in endpoints:
            if not any(pt.isEqual(u, 0.001) for u in unique_pts): unique_pts.append(pt)
        junctions = []
        for pt in unique_pts:
            if sum(1 for p in endpoints if pt.isEqual(p, 0.001)) > 2: junctions.append(pt)
        return junctions

    def build_simple_paths(self, edges, junctions):
        broken_edges = []
        for e in edges:
            if not hasattr(e.Curve, 'TypeId') or e.Curve.TypeId != 'Part::GeomLine':
                broken_edges.append(e); continue
            p_s = e.valueAt(e.FirstParameter); p_e = e.valueAt(e.LastParameter)
            splits = []
            for jp in junctions:
                if e.distToShape(Part.Vertex(jp))[0] < 0.001 and not jp.isEqual(p_s, 0.001) and not jp.isEqual(p_e, 0.001):
                    splits.append(jp)
            if not splits:
                broken_edges.append(e)
            else:
                splits.sort(key=lambda p: (p - p_s).Length)
                curr_p = p_s
                for sp in splits:
                    broken_edges.append(Part.makeLine(curr_p, sp))
                    curr_p = sp
                broken_edges.append(Part.makeLine(curr_p, p_e))

        paths, unprocessed = [], broken_edges[:]
        while unprocessed:
            path = [unprocessed.pop(0)]
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

    def fillet_wire_path(self, edges, sketch_normal, w, offset_val, calc_inner_rad):
        if len(edges) < 2: return edges
        pts = [edges[0].valueAt(edges[0].FirstParameter)]
        for e in edges: pts.append(e.valueAt(e.LastParameter))
        
        final_edges = []
        p_start_node = pts[0]
        
        for i in range(1, len(pts)-1):
            p_corner = pts[i]; p_next = pts[i+1]
            
            v1 = (pts[i-1] - p_corner).normalize()
            v2 = (p_next - p_corner).normalize()
            angle = v1.getAngle(v2)
            
            if angle < 0.01 or angle > 3.13:
                if (p_corner - p_start_node).Length > 0.001: final_edges.append(Part.makeLine(p_start_node, p_corner))
                p_start_node = p_corner
                continue
                
            v_in = -v1
            turn_axis = v_in.cross(v2)
            is_left_turn = turn_axis.dot(sketch_normal) > 0
            
            if is_left_turn: actual_path_radius = calc_inner_rad + (w / 2.0) + offset_val
            else: actual_path_radius = calc_inner_rad + (w / 2.0) - offset_val
            actual_path_radius = max(0.1, actual_path_radius)

            bisector = (v1 + v2).normalize()
            deflection = math.pi - angle
            T_req = actual_path_radius * math.tan(deflection / 2.0)
            
            p_tan1 = p_corner + v1 * T_req
            p_tan2 = p_corner + v2 * T_req
            
            if (p_tan1 - p_start_node).Length > 0.001: final_edges.append(Part.makeLine(p_start_node, p_tan1))
                
            O = p_corner + bisector * (T_req / math.sin(deflection / 2.0))
            mid_arc_pt = O - bisector * actual_path_radius
            final_edges.append(Part.Arc(p_tan1, mid_arc_pt, p_tan2).toShape())
            p_start_node = p_tan2
            
        if (pts[-1] - p_start_node).Length > 0.001: final_edges.append(Part.makeLine(p_start_node, pts[-1]))
        return final_edges

    def create_profile(self, w, h, radius, start_pt, tangent, sketch_normal, shape_type, offset_val=0.0):
        Z_new = tangent.normalize()
        Y_new = sketch_normal.normalize()
        X_new = Y_new.cross(Z_new).normalize()
        if X_new.Length < 0.0001:
            Y_new = FreeCAD.Vector(1, 0, 0) if abs(Z_new.x) < 0.9 else FreeCAD.Vector(0, 1, 0)
            X_new = Y_new.cross(Z_new).normalize()

        mat = FreeCAD.Matrix(X_new.x, Y_new.x, Z_new.x, start_pt.x, X_new.y, Y_new.y, Z_new.y, start_pt.y, X_new.z, Y_new.z, Z_new.z, start_pt.z, 0, 0, 0, 1)

        if shape_type == "Round":
            circ = Part.Circle(FreeCAD.Vector(offset_val,0,0), FreeCAD.Vector(0,0,1), w/2.0)
            wire = Part.Wire([Part.Edge(circ)])
            wire.Placement = FreeCAD.Placement(mat)
            return wire
            
        if shape_type == "Rectangular": radius = 0.001 

        if radius <= 0.001:
            p1 = FreeCAD.Vector(-w/2 + offset_val, -h/2, 0)
            p2 = FreeCAD.Vector(w/2 + offset_val, -h/2, 0)
            p3 = FreeCAD.Vector(w/2 + offset_val, h/2, 0)
            p4 = FreeCAD.Vector(-w/2 + offset_val, h/2, 0)
            wire = Part.Wire(Part.makePolygon([p1, p2, p3, p4, p1]))
        else:
            r = min(radius, (w/2.0) - 0.001, (h/2.0) - 0.001)
            cx1 = -w/2 + r + offset_val; cy1 = -h/2 + r
            cx2 =  w/2 - r + offset_val; cy2 = -h/2 + r
            cx3 =  w/2 - r + offset_val; cy3 =  h/2 - r
            cx4 = -w/2 + r + offset_val; cy4 =  h/2 - r
            
            Z_dir = FreeCAD.Vector(0, 0, 1)
            arc1 = Part.Edge(Part.Circle(FreeCAD.Vector(cx1, cy1, 0), Z_dir, r), math.radians(180), math.radians(270))
            arc2 = Part.Edge(Part.Circle(FreeCAD.Vector(cx2, cy2, 0), Z_dir, r), math.radians(270), math.radians(360))
            arc3 = Part.Edge(Part.Circle(FreeCAD.Vector(cx3, cy3, 0), Z_dir, r), math.radians(0), math.radians(90))
            arc4 = Part.Edge(Part.Circle(FreeCAD.Vector(cx4, cy4, 0), Z_dir, r), math.radians(90), math.radians(180))
            
            edge1 = Part.makeLine(FreeCAD.Vector(cx1, -h/2, 0), FreeCAD.Vector(cx2, -h/2, 0))
            edge2 = Part.makeLine(FreeCAD.Vector(w/2 + offset_val, cy2, 0), FreeCAD.Vector(w/2 + offset_val, cy3, 0))
            edge3 = Part.makeLine(FreeCAD.Vector(cx3, h/2, 0), FreeCAD.Vector(cx4, h/2, 0))
            edge4 = Part.makeLine(FreeCAD.Vector(-w/2 + offset_val, cy4, 0), FreeCAD.Vector(-w/2 + offset_val, cy1, 0))
            
            wire = Part.Wire([arc1, edge1, arc2, edge2, arc3, edge3, arc4, edge4])
            
        wire.Placement = FreeCAD.Placement(mat)
        return wire

class CreateDuctFittings:
    def GetResources(self):
        return {'Pixmap': ComfacUtils.get_icon_path('Duct_Fittings.svg') if 'ComfacUtils' in globals() else "", 'MenuText': "Add Duct Fittings"}
        
    def extract_folder(self, obj):
        if hasattr(obj, "DuctWidth") or hasattr(obj, "SolidWidth"): return obj
        for p in obj.InList:
            if hasattr(p, "DuctWidth") or hasattr(p, "SolidWidth"): return p
        return None

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        if not sel:
            QtWidgets.QMessageBox.warning(None, "Selection Error", "Please select a Smart Duct Folder or Solid CFD Folder.")
            return
            
        target_folder = self.extract_folder(sel[0])
        if not target_folder:
            QtWidgets.QMessageBox.warning(None, "Selection Error", "Invalid selection. Please select a Duct or Solid Folder.")
            return

        progress = QtWidgets.QProgressDialog("Launching Fittings Tool...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Loading")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            panel = DuctFittingTaskPanel(target_folder)
            FreeCADGui.Control.showDialog(panel)
        finally:
            progress.close()

try:
    FreeCADGui.addCommand('CreateDuctFittings', CreateDuctFittings()) 
except Exception:
    pass