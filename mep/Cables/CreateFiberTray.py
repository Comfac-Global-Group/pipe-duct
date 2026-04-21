import FreeCAD as App
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui

# Safely import ComfacUtils
try:
    import ComfacUtils
except ImportError:
    ComfacUtils = None

# ==========================================
# GEOMETRY & MATH ENGINE (FIBER TRAY)
# ==========================================
class TrayGeom:
    @staticmethod
    def get_routing_placement(X_dir, target_pt, offset_vec=App.Vector(0,0,0)):
        """STRICT LOCAL 2D MATRIX. FreeCAD handles the 3D Sketch mapping natively."""
        Z_dir = App.Vector(0, 0, 1)
        X_dir = App.Vector(X_dir.x, X_dir.y, 0)
        
        if X_dir.Length < 0.001: X_dir = App.Vector(1,0,0)
        else: X_dir.normalize()
        
        Y_dir = Z_dir.cross(X_dir).normalize()
        
        m = App.Matrix()
        m.A11 = X_dir.x; m.A12 = Y_dir.x; m.A13 = Z_dir.x; m.A14 = target_pt.x
        m.A21 = X_dir.y; m.A22 = Y_dir.y; m.A23 = Z_dir.y; m.A24 = target_pt.y
        m.A31 = X_dir.z; m.A32 = Y_dir.z; m.A33 = Z_dir.z; m.A34 = target_pt.z
        
        route_plm = App.Placement(m)
        base_m = App.Matrix()
        base_m.move(offset_vec)
        return route_plm.multiply(App.Placement(base_m))

    @staticmethod
    def extrude_polygon(points, length):
        length = max(length, 0.1)
        if points[0] != points[-1]: points.append(points[0])
        wire = Part.Wire([Part.makeLine(points[i], points[i+1]) for i in range(len(points)-1)])
        return Part.Face(wire).extrude(App.Vector(length, 0, 0)).removeSplitter()

    @staticmethod
    def get_tray_profile(w, d, t):
        w = max(w, 20.0); d = max(d, 20.0); t = max(t, 1.0)
        pts = [
            App.Vector(0, -w/2+t, d), App.Vector(0, -w/2, d),
            App.Vector(0, -w/2, d-10), App.Vector(0, -w/2-8, d-10),
            App.Vector(0, -w/2-8, d-14), App.Vector(0, -w/2, d-14),
            App.Vector(0, -w/2, d-22), App.Vector(0, -w/2-8, d-22),
            App.Vector(0, -w/2-8, d-26), App.Vector(0, -w/2, d-26),
            App.Vector(0, -w/2, 8), App.Vector(0, -w/2+8, 0),
            App.Vector(0, w/2-8, 0), App.Vector(0, w/2, 8),
            App.Vector(0, w/2, d-26), App.Vector(0, w/2+8, d-26),
            App.Vector(0, w/2+8, d-22), App.Vector(0, w/2, d-22),
            App.Vector(0, w/2, d-14), App.Vector(0, w/2+8, d-14),
            App.Vector(0, w/2+8, d-10), App.Vector(0, w/2, d-10),
            App.Vector(0, w/2, d), App.Vector(0, w/2-t, d),
            App.Vector(0, w/2-t, t+8), App.Vector(0, w/2-t-8, t), 
            App.Vector(0, -w/2+t+8, t), App.Vector(0, -w/2+t, t+8) 
        ]
        if pts[0] != pts[-1]: pts.append(pts[0])
        return Part.Face(Part.Wire([Part.makeLine(pts[i], pts[i+1]) for i in range(len(pts)-1)]))

    @staticmethod
    def get_cover_profile(w, d, t):
        w = max(w, 20.0); d = max(d, 20.0); t = max(t, 1.0)
        pts = [
            App.Vector(0, -w/2-10, -5), App.Vector(0, -w/2-10, 0),
            App.Vector(0, -w/2-t, t), App.Vector(0, -w/2+20, t),
            App.Vector(0, -w/2+22, t+3), App.Vector(0, -w/2+25, t+3), 
            App.Vector(0, -w/2+27, t), App.Vector(0, w/2-27, t),
            App.Vector(0, w/2-25, t+3), App.Vector(0, w/2-22, t+3), 
            App.Vector(0, w/2-20, t), App.Vector(0, w/2+t, t),
            App.Vector(0, w/2+10, 0), App.Vector(0, w/2+10, -5),
            App.Vector(0, w/2+10-t, -5), App.Vector(0, w/2+10-t, -t),
            App.Vector(0, w/2, 0), App.Vector(0, -w/2, 0)
        ]
        if pts[0] != pts[-1]: pts.append(pts[0])
        face = Part.Face(Part.Wire([Part.makeLine(pts[i], pts[i+1]) for i in range(len(pts)-1)]))
        face.translate(App.Vector(0, 0, d)) 
        return face

    @staticmethod
    def make_straight_tray(l, w, d, t):
        l = max(l, 0.1)
        return TrayGeom.get_tray_profile(w, d, t).extrude(App.Vector(l, 0, 0)).removeSplitter()

    @staticmethod
    def make_straight_cover(l, w, d, t):
        l = max(l, 0.1)
        return TrayGeom.get_cover_profile(w, d, t).extrude(App.Vector(l, 0, 0)).removeSplitter()

    @staticmethod
    def make_elbow(w, d, t, is_cover=False):
        R = w/2 + 100.0 
        face = TrayGeom.get_cover_profile(w, d, t) if is_cover else TrayGeom.get_tray_profile(w, d, t)
        mat = App.Matrix()
        mat.rotateZ(-math.pi/2)
        mat.move(App.Vector(0, R, 0))
        curve = face.copy().transformGeometry(mat).revolve(App.Vector(R, R, 0), App.Vector(0, 0, 1), 90).removeSplitter()
        t1 = face.copy().translate(App.Vector(R, 0, 0)).extrude(App.Vector(50, 0, 0)).removeSplitter()
        mat2 = App.Matrix()
        mat2.rotateZ(math.pi/2)
        mat2.move(App.Vector(0, R, 0))
        t2 = face.copy().transformGeometry(mat2).extrude(App.Vector(0, 50, 0)).removeSplitter()
        return curve.fuse([t1, t2]).removeSplitter()

    @staticmethod
    def make_rounded_tee_solid(w_outer, port_dist, R, h):
        w_outer = max(w_outer, 1.0); h = max(h, 0.1)
        b1 = Part.makeBox(port_dist * 2, w_outer, h, App.Vector(-port_dist, -w_outer/2, 0))
        b2 = Part.makeBox(w_outer, port_dist + w_outer/2, h, App.Vector(-w_outer/2, -w_outer/2, 0))
        solid = b1.fuse(b2).removeSplitter() 
        corner1 = Part.makeBox(R, R, h, App.Vector(w_outer/2, w_outer/2, 0))
        cyl1 = Part.makeCylinder(R, h, App.Vector(w_outer/2 + R, w_outer/2 + R, 0))
        solid = solid.fuse(corner1).cut(cyl1).removeSplitter()
        corner2 = Part.makeBox(R, R, h, App.Vector(-w_outer/2 - R, w_outer/2, 0))
        cyl2 = Part.makeCylinder(R, h, App.Vector(-w_outer/2 - R, w_outer/2 + R, 0))
        return solid.fuse(corner2).cut(cyl2).removeSplitter()

    @staticmethod
    def make_tee(w, d, t, is_cover=False):
        R = 100.0; port_dist = w/2 + R + 50.0 
        if is_cover:
            top = TrayGeom.make_rounded_tee_solid(w+20, port_dist, R-10, t).translate(App.Vector(0,0,d))
            l_out = TrayGeom.make_rounded_tee_solid(w+20, port_dist, R-10, 5).translate(App.Vector(0,0,d-5))
            l_in = TrayGeom.make_rounded_tee_solid(w+2*t, port_dist+5, R-t, 7).translate(App.Vector(0,0,d-6))
            cover = top.fuse(l_out.cut(l_in)).removeSplitter()
            ridge_out = TrayGeom.make_rounded_tee_solid(w-44, port_dist, R+22, 3)
            ridge_in = TrayGeom.make_rounded_tee_solid(w-50, port_dist+5, R+25, 5).translate(App.Vector(0,0,-1))
            ridges = ridge_out.cut(ridge_in).translate(App.Vector(0, 0, d + t)).removeSplitter()
            return cover.fuse(ridges).removeSplitter()
        else:
            outer = TrayGeom.make_rounded_tee_solid(w, port_dist, R, d)
            inner = TrayGeom.make_rounded_tee_solid(w-2*t, port_dist+5, R+t, d).translate(App.Vector(0,0,t))
            shell = outer.cut(inner).removeSplitter()
            rail_out = TrayGeom.make_rounded_tee_solid(w+16, port_dist, R-8, 4)
            rail_in = TrayGeom.make_rounded_tee_solid(w, port_dist+5, R, 6).translate(App.Vector(0,0,-1))
            r_base = rail_out.cut(rail_in).removeSplitter()
            return shell.fuse([r_base.copy().translate(App.Vector(0,0,d-14)), 
                               r_base.copy().translate(App.Vector(0,0,d-26))]).removeSplitter()

    @staticmethod
    def make_swept_cross_solid(w_outer, port_dist, R, h):
        w_outer = max(w_outer, 1.0); h = max(h, 0.1)
        b1 = Part.makeBox(port_dist * 2, w_outer, h, App.Vector(-port_dist, -w_outer/2, 0))
        b2 = Part.makeBox(w_outer, port_dist * 2, h, App.Vector(-w_outer/2, -port_dist, 0))
        solid = b1.fuse(b2).removeSplitter()
        for cx, cy in [(1, 1), (-1, 1), (-1, -1), (1, -1)]:
            corner = Part.makeBox(R, R, h, App.Vector(cx*(w_outer/2), cy*(w_outer/2), 0) if cx > 0 and cy > 0 else 
                                         App.Vector(cx*(w_outer/2+R), cy*(w_outer/2), 0) if cx < 0 and cy > 0 else
                                         App.Vector(cx*(w_outer/2+R), cy*(w_outer/2+R), 0) if cx < 0 and cy < 0 else
                                         App.Vector(cx*(w_outer/2), cy*(w_outer/2+R), 0))
            cyl = Part.makeCylinder(R, h, App.Vector(cx*(w_outer/2+R), cy*(w_outer/2+R), 0))
            solid = solid.fuse(corner).cut(cyl).removeSplitter()
        return solid

    @staticmethod
    def make_cross(w, d, t, is_cover=False):
        R = 100.0; port_dist = w/2 + R + 50.0 
        if is_cover:
            top = TrayGeom.make_swept_cross_solid(w+20, port_dist, R-10, t).translate(App.Vector(0,0,d))
            l_out = TrayGeom.make_swept_cross_solid(w+20, port_dist, R-10, 5).translate(App.Vector(0,0,d-5))
            l_in = TrayGeom.make_swept_cross_solid(w+2*t, port_dist+5, R-t, 7).translate(App.Vector(0,0,d-6))
            cover = top.fuse(l_out.cut(l_in)).removeSplitter()
            ridge_out = TrayGeom.make_swept_cross_solid(w-44, port_dist, R+22, 3)
            ridge_in = TrayGeom.make_swept_cross_solid(w-50, port_dist+5, R+25, 5).translate(App.Vector(0,0,-1))
            ridges = ridge_out.cut(ridge_in).translate(App.Vector(0, 0, d + t)).removeSplitter()
            return cover.fuse(ridges).removeSplitter()
        else:
            outer = TrayGeom.make_swept_cross_solid(w, port_dist, R, d)
            inner = TrayGeom.make_swept_cross_solid(w-2*t, port_dist+5, R+t, d).translate(App.Vector(0,0,t))
            shell = outer.cut(inner).removeSplitter()
            rail_out = TrayGeom.make_swept_cross_solid(w+16, port_dist, R-8, 4)
            rail_in = TrayGeom.make_swept_cross_solid(w, port_dist+5, R, 6).translate(App.Vector(0,0,-1))
            r_base = rail_out.cut(rail_in).removeSplitter()
            return shell.fuse([r_base.copy().translate(App.Vector(0,0,d-14)), 
                               r_base.copy().translate(App.Vector(0,0,d-26))]).removeSplitter()

    @staticmethod
    def make_connector(w, d, t):
        L = 80.0
        outer = Part.makeBox(L, w + 36, d + 10, App.Vector(-L/2, -w/2 - 18, -t - 2))
        inner = Part.makeBox(L + 2, w + 4, d + 15, App.Vector(-L/2 - 1, -w/2 - 2, 0))
        conn = outer.cut(inner).removeSplitter()
        pocket1 = Part.makeBox(20, w + 40, d + 15, App.Vector(-L/2 + 10, -w/2 - 20, -t))
        pocket2 = Part.makeBox(20, w + 40, d + 15, App.Vector(L/2 - 30, -w/2 - 20, -t))
        conn = conn.cut(pocket1).cut(pocket2).removeSplitter()
        lip1 = Part.makeBox(L, 10, 4, App.Vector(-L/2, -w/2 - 12, d - 10))
        lip2 = Part.makeBox(L, 10, 4, App.Vector(-L/2, w/2 + 2, d - 10))
        return conn.fuse([lip1, lip2]).removeSplitter()

    @staticmethod
    def get_centered_fitting(f_type, w, d, t):
        if f_type == "90": return TrayGeom.make_elbow(w, d, t), 150.0 + w/2, App.Vector(0, 0, 0)
        elif f_type == "TEE": return TrayGeom.make_tee(w, d, t), 150.0 + w/2, App.Vector(0, 0, 0)
        elif f_type == "CROSS": return TrayGeom.make_cross(w, d, t), 150.0 + w/2, App.Vector(0, 0, 0)

    @staticmethod
    def calculate_routing(sketch, w, d, t, gen_covers):
        trays, fittings, covers, connectors = [], [], [], []
        edges = [geom for geom in sketch.Geometry if type(geom).__name__ == 'LineSegment']
        
        vertices = {}
        for edge in edges:
            p1 = (round(edge.StartPoint.x, 2), round(edge.StartPoint.y, 2), 0.0)
            p2 = (round(edge.EndPoint.x, 2), round(edge.EndPoint.y, 2), 0.0)
            if p1 not in vertices: vertices[p1] = []
            if p2 not in vertices: vertices[p2] = []
            
            v1 = App.Vector(p2[0]-p1[0], p2[1]-p1[1], 0).normalize()
            v2 = App.Vector(p1[0]-p2[0], p1[1]-p2[1], 0).normalize()
            vertices[p1].append(v1)
            vertices[p2].append(v2)

        R_elbow = w/2 + 150.0 
        port_dist_tee = w/2 + 150.0
        vertex_allowances = {} 

        for pt_tuple, vectors in vertices.items():
            degree = len(vectors)
            pt = App.Vector(pt_tuple[0], pt_tuple[1], 0)
            shape = None; c_shape = None; allowance = 0; base_v = vectors[0]
            
            if degree > 2:
                for i in range(degree):
                    for j in range(i + 1, degree):
                        dot_val = vectors[i].dot(vectors[j])
                        angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, dot_val))))
                        if not (abs(angle_deg - 90.0) < 5.0 or abs(angle_deg - 180.0) < 5.0):
                            raise ValueError(f"Invalid Intersection! Tees and Crosses require 90° connections. Found an angle of {angle_deg:.1f}°.")
            elif degree == 2:
                dot_val = vectors[0].dot(vectors[1])
                angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, dot_val))))
                if not (abs(angle_deg - 90.0) < 5.0 or abs(angle_deg - 180.0) < 5.0):
                    raise ValueError(f"Invalid Elbow Angle ({angle_deg:.1f}°)! Fiber trays can only bend at exactly 90°.")

            if degree == 1: allowance = 0
            elif degree == 2:
                if abs(vectors[0].dot(vectors[1])) < 0.1: 
                    v1, v2 = vectors[0], vectors[1]
                    if App.Vector(0,0,1).cross(v1).dot(v2) > 0: base_v = v1
                    else: base_v = v2
                    shape = TrayGeom.make_elbow(w, d, t)
                    if gen_covers: c_shape = TrayGeom.make_elbow(w, d, t, is_cover=True)
                    allowance = R_elbow
                else: allowance = 0 
            elif degree == 3:
                v_branch = vectors[0]; v_straight = []
                for v in vectors:
                    if any(abs(v.dot(u) + 1.0) < 0.1 for u in vectors): v_straight.append(v)
                    else: v_branch = v
                    
                if len(v_straight) >= 2:
                    base_v = v_straight[0]
                    # Ensures branch points correctly without rotating the entire TEE out of alignment
                    if App.Vector(0,0,1).cross(base_v).dot(v_branch) < 0: base_v = v_straight[1]
                    
                shape = TrayGeom.make_tee(w, d, t)
                if gen_covers: c_shape = TrayGeom.make_tee(w, d, t, is_cover=True)
                allowance = port_dist_tee
            elif degree == 4:
                base_v = vectors[0]
                shape = TrayGeom.make_cross(w, d, t)
                if gen_covers: c_shape = TrayGeom.make_cross(w, d, t, is_cover=True)
                allowance = port_dist_tee

            vertex_allowances[pt_tuple] = allowance
            
            if shape:
                X_dir = base_v
                # We simply let the base_v control the orientation natively. Removed the bad 90-deg override.
                
                local_plm = TrayGeom.get_routing_placement(X_dir, pt, App.Vector(0,0,0))
                s_copy = shape.copy()
                s_copy.Placement = sketch.Placement.multiply(local_plm)
                fittings.append(s_copy)
                
                if c_shape:
                    c_copy = c_shape.copy()
                    c_copy.Placement = sketch.Placement.multiply(local_plm)
                    covers.append(c_copy)

            if degree > 1:
                if degree == 2 and allowance == 0:
                    c_plm = TrayGeom.get_routing_placement(vectors[0], pt)
                    conn_shape = TrayGeom.make_connector(w, d, t)
                    conn_shape.Placement = sketch.Placement.multiply(c_plm)
                    connectors.append(conn_shape)
                else:
                    for v in vectors:
                        seam_pos = pt + v * allowance
                        c_plm = TrayGeom.get_routing_placement(v, seam_pos)
                        conn_shape = TrayGeom.make_connector(w, d, t)
                        conn_shape.Placement = sketch.Placement.multiply(c_plm)
                        connectors.append(conn_shape)

        for edge in edges:
            p1 = (round(edge.StartPoint.x, 2), round(edge.StartPoint.y, 2), 0.0)
            p2 = (round(edge.EndPoint.x, 2), round(edge.EndPoint.y, 2), 0.0)
            v_dir = App.Vector(p2[0]-p1[0], p2[1]-p1[1], 0)
            total_length = v_dir.Length
            
            a1 = vertex_allowances.get(p1, 0)
            a2 = vertex_allowances.get(p2, 0)
            
            if total_length + 0.1 < (a1 + a2 + 2.0):
                shortfall = (a1 + a2 + 2.0) - total_length
                raise ValueError(f"Sketch Line too short! Length: {total_length:.1f}mm, require {a1+a2:.1f}mm space.\nPlease lengthen by {shortfall:.1f}mm.")

        for edge in edges:
            p1 = (round(edge.StartPoint.x, 2), round(edge.StartPoint.y, 2), 0.0)
            p2 = (round(edge.EndPoint.x, 2), round(edge.EndPoint.y, 2), 0.0)
            v_dir = App.Vector(p2[0]-p1[0], p2[1]-p1[1], 0)
            total_length = v_dir.Length
            v_dir.normalize()
            
            a1 = vertex_allowances.get(p1, 0)
            a2 = vertex_allowances.get(p2, 0)
            actual_length = total_length - a1 - a2
            
            if actual_length > 0.1:
                start_pos = App.Vector(p1[0], p1[1], 0) + v_dir * a1
                local_plm = TrayGeom.get_routing_placement(v_dir, start_pos)
                
                shape = TrayGeom.make_straight_tray(actual_length, w, d, t)
                shape.Placement = sketch.Placement.multiply(local_plm)
                trays.append(shape)
                
                if gen_covers:
                    c_shape = TrayGeom.make_straight_cover(actual_length, w, d, t)
                    c_shape.Placement = sketch.Placement.multiply(local_plm)
                    covers.append(c_shape)

        return trays, fittings, covers, connectors

# ==========================================
# LIVE BACKGROUND OBSERVER
# ==========================================
class FiberTrayLiveObserver:
    def __init__(self):
        self.pending_rebuilds = set()
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.process_rebuilds)
        self.is_generating = False
        self.last_error = ""

    def trigger_rebuild_manually(self, group):
        self.pending_rebuilds.add(group)
        self.process_rebuilds()

    def slotChangedObject(self, obj, prop):
        if self.is_generating: return
        needs_rebuild = False
        
        if obj.isDerivedFrom("Sketcher::SketchObject") and prop in ["Shape", "Placement"]:
            if obj.Document:
                for doc_obj in obj.Document.Objects:
                    if doc_obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(doc_obj, "LinkedFiberSketchName"):
                        if doc_obj.LinkedFiberSketchName == obj.Name:
                            self.pending_rebuilds.add(doc_obj)
                            needs_rebuild = True

        if obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(obj, "LinkedFiberSketchName"):
            if prop in ["FiberWidth", "FiberDepth", "FiberThickness", "FiberGenerateCovers"]:
                self.pending_rebuilds.add(obj)
                needs_rebuild = True
                
        if needs_rebuild:
            self.timer.start(500)

    def process_rebuilds(self):
        if FreeCADGui.ActiveDocument and FreeCADGui.ActiveDocument.getInEdit():
            self.timer.start(1000)
            return

        self.is_generating = True
        try:
            for group in list(self.pending_rebuilds):
                if group.Document: 
                    self.rebuild_folder(group)
        finally:
            self.pending_rebuilds.clear()
            self.is_generating = False

    def rebuild_folder(self, group):
        doc = group.Document
        sketch_name = getattr(group, "LinkedFiberSketchName", "")
        sketch = doc.getObject(sketch_name) if sketch_name else None
        if not sketch: return
        
        w_prop = getattr(group, "FiberWidth", 300.0)
        d_prop = getattr(group, "FiberDepth", 100.0)
        t_prop = getattr(group, "FiberThickness", 3.0)
        covers_prop = getattr(group, "FiberGenerateCovers", True)
        
        w = w_prop.Value if hasattr(w_prop, 'Value') else float(w_prop)
        d = d_prop.Value if hasattr(d_prop, 'Value') else float(d_prop)
        t = t_prop.Value if hasattr(t_prop, 'Value') else float(t_prop)
        gen_covers = covers_prop.Value if hasattr(covers_prop, 'Value') else bool(covers_prop)
        
        def gather_items(grp):
            items = []
            for child in grp.Group:
                if child != sketch:
                    items.append(child)
                    if child.isDerivedFrom("App::DocumentObjectGroup"):
                        items.extend(gather_items(child))
            return items

        # --- PROGRESS DIALOG TRIGGER ---
        progress = QtWidgets.QProgressDialog("Calculating Fiber Tray geometry...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Generating 3D Models")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            trays, fittings, covers, connectors = TrayGeom.calculate_routing(sketch, w, d, t, gen_covers)
            self.last_error = ""
        except ValueError as ve:
            error_msg = str(ve)
            for item in reversed(gather_items(group)): doc.removeObject(item.Name)
            doc.recompute()
            if self.last_error != error_msg:
                self.last_error = error_msg
                App.Console.PrintError(f"\n[FIBER TRAY ROUTING ERROR] {error_msg}\n")
                QtWidgets.QMessageBox.critical(None, "Routing Error", error_msg)
            return
        finally:
            progress.close()
        
        for item in reversed(gather_items(group)): doc.removeObject(item.Name)
            
        def get_or_create_subgroup(parent_group, name):
            for obj in parent_group.Group:
                if obj.Name == name or obj.Label == name: return obj
            sub = doc.addObject("App::DocumentObjectGroup", name)
            parent_group.addObject(sub)
            return sub
            
        color = (1.0, 0.82, 0.1) # Solid Yellow Plastic
        
        if fittings:
            fit_grp = get_or_create_subgroup(group, "Fittings")
            for i, s in enumerate(fittings):
                obj = doc.addObject("Part::Feature", f"Auto_Fitting_{i+1}")
                obj.Shape = s
                if hasattr(obj, "ViewObject") and obj.ViewObject: obj.ViewObject.ShapeColor = color
                fit_grp.addObject(obj)
                
        if connectors:
            conn_grp = get_or_create_subgroup(group, "Connectors")
            for i, s in enumerate(connectors):
                obj = doc.addObject("Part::Feature", f"Auto_Connector_{i+1}")
                obj.Shape = s
                if hasattr(obj, "ViewObject") and obj.ViewObject: obj.ViewObject.ShapeColor = color
                conn_grp.addObject(obj)
                
        if trays:
            tray_grp = get_or_create_subgroup(group, "Straight_Trays")
            for i, s in enumerate(trays):
                obj = doc.addObject("Part::Feature", f"Straight_Tray_{i+1}")
                obj.Shape = s
                if hasattr(obj, "ViewObject") and obj.ViewObject: obj.ViewObject.ShapeColor = color
                tray_grp.addObject(obj)
                
        if covers:
            cov_grp = get_or_create_subgroup(group, "Covers")
            for i, s in enumerate(covers):
                obj = doc.addObject("Part::Feature", f"Cover_{i+1}")
                obj.Shape = s
                if hasattr(obj, "ViewObject") and obj.ViewObject: obj.ViewObject.ShapeColor = color
                cov_grp.addObject(obj)
            
        doc.recompute()

if not hasattr(App, "GlobalFiberObserver"):
    App.GlobalFiberObserver = FiberTrayLiveObserver()
    App.addDocumentObserver(App.GlobalFiberObserver)

# ==========================================
# UI CONTROLLER & PREVIEW MANAGER
# ==========================================
class FiberTrayTaskPanel:
    def __init__(self, selected_sketch=None):
        self.selected_sketch = selected_sketch
        self.doc = App.ActiveDocument
        self.last_error = ""
        
        self.preview_manager = None
        if ComfacUtils and hasattr(ComfacUtils, 'PreviewManager'):
            self.preview_manager = ComfacUtils.PreviewManager(self.doc, "Fiber_Tray_Preview")

        self.widths = [120, 300, 360]
        self.depths = [100, 120]
        self.fittings = ["STRAIGHT TRAY", "90 DEGREE ELBOW", "TEE CONNECTOR", "CROSS CONNECTOR", "TRAY CONNECTOR"]

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        if self.selected_sketch:
            self.mode_label = QtWidgets.QLabel("<b>Live Folder Mode Active</b><br>Will automatically route Fiber Trays.")
            self.layout.addRow(self.mode_label)
        else:
            self.mode_label = QtWidgets.QLabel("<b>Manual Generation Mode</b><br>Select a Sketch to activate Smart Folders.")
            self.layout.addRow(self.mode_label)

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(self.fittings)
        if self.selected_sketch: self.type_cb.setEnabled(False)
        
        self.length_input = QtWidgets.QDoubleSpinBox()
        self.length_input.setRange(10.0, 10000.0)
        self.length_input.setValue(1000.0)
        self.length_input.setSuffix(" mm")
        if self.selected_sketch: self.length_input.setEnabled(False)

        self.width_cb = QtWidgets.QComboBox()
        self.width_cb.addItems([f"{w} MM" for w in self.widths])

        self.depth_cb = QtWidgets.QComboBox()
        self.depth_cb.addItems([f"{d} MM" for d in self.depths])

        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(1.0, 10.0)
        self.thick_input.setValue(3.0)
        self.thick_input.setSuffix(" mm")
        
        self.cover_cb = QtWidgets.QCheckBox("Generate Covers")
        self.cover_cb.setChecked(True)

        self.layout.addRow("Part Type (Manual):", self.type_cb)
        self.layout.addRow("Tray Length:", self.length_input)
        self.layout.addRow("Tray Width:", self.width_cb)
        self.layout.addRow("Tray Depth:", self.depth_cb)
        self.layout.addRow("Plastic Thickness:", self.thick_input)
        self.layout.addRow("", self.cover_cb)

        self.type_cb.currentIndexChanged.connect(self.update_ui)
        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.length_input.valueChanged.connect(self.trigger_preview)
        self.width_cb.currentIndexChanged.connect(self.trigger_preview)
        self.depth_cb.currentIndexChanged.connect(self.trigger_preview)
        self.thick_input.valueChanged.connect(self.trigger_preview)
        self.cover_cb.stateChanged.connect(self.trigger_preview)
        
        self.update_ui()
        self.trigger_preview()

    def update_ui(self):
        is_straight = (self.type_cb.currentText() == "STRAIGHT TRAY")
        if not self.selected_sketch:
            self.length_input.setEnabled(is_straight)

    def trigger_preview(self, *args):
        if not self.preview_manager: return
            
        w = float(self.width_cb.currentText().replace(" MM", ""))
        d = float(self.depth_cb.currentText().replace(" MM", ""))
        t = self.thick_input.value()
        gen_covers = self.cover_cb.isChecked()
        
        all_shapes = []
        try:
            if self.selected_sketch:
                trays, fittings, covers, connectors = TrayGeom.calculate_routing(self.selected_sketch, w, d, t, gen_covers)
                all_shapes = trays + fittings + covers + connectors
            else:
                f_type = self.type_cb.currentText()
                l = self.length_input.value()
                shape = self.get_manual_shape(f_type, l, w, d, t, False)
                if shape: all_shapes.append(shape)
                if gen_covers:
                    c_shape = self.get_manual_shape(f_type, l, w, d, t, True)
                    if c_shape: all_shapes.append(c_shape)
            self.last_error = "" 
        except ValueError as e:
            self.preview_manager.clear()
            error_msg = str(e)
            if getattr(self, 'last_error', None) != error_msg:
                self.last_error = error_msg
                QtWidgets.QMessageBox.warning(self.form, "Preview Error", error_msg)
            return
        
        if all_shapes:
            self.preview_manager.update(Part.makeCompound(all_shapes), color=(1.0, 0.82, 0.1))

    def get_manual_shape(self, f_type, l, w, d, t, is_cover):
        if f_type == "STRAIGHT TRAY": return TrayGeom.make_straight_cover(l, w, d, t) if is_cover else TrayGeom.make_straight_tray(l, w, d, t)
        elif f_type == "90 DEGREE ELBOW": return TrayGeom.make_elbow(w, d, t, is_cover)
        elif f_type == "TEE CONNECTOR": return TrayGeom.make_tee(w, d, t, is_cover)
        elif f_type == "CROSS CONNECTOR": return TrayGeom.make_cross(w, d, t, is_cover)
        elif f_type == "TRAY CONNECTOR": return None if is_cover else TrayGeom.make_connector(w, d, t)
        return None

    def accept(self):
        w = float(self.width_cb.currentText().replace(" MM", ""))
        d = float(self.depth_cb.currentText().replace(" MM", ""))
        t = self.thick_input.value()
        gen_covers = self.cover_cb.isChecked()
        
        if self.preview_manager: self.preview_manager.clear()
        FreeCADGui.Control.closeDialog()
        
        if self.selected_sketch: self.setup_smart_folder(w, d, t, gen_covers)
        else: self.generate_manual(w, d, t, gen_covers)

    def reject(self):
        if self.preview_manager: self.preview_manager.clear()
        FreeCADGui.Control.closeDialog()

    def setup_smart_folder(self, w, d, t, gen_covers):
        doc = App.ActiveDocument
        folder_name = f"{self.selected_sketch.Name}_FiberSystem"
        group = doc.getObject(folder_name)
        
        if not group:
            group = doc.addObject("App::DocumentObjectGroup", folder_name)
            
        if not hasattr(group, "FiberWidth"):
            group.addProperty("App::PropertyLength", "FiberWidth", "Live Parameters", "Tray Width")
        if not hasattr(group, "FiberDepth"):
            group.addProperty("App::PropertyLength", "FiberDepth", "Live Parameters", "Tray Depth")
        if not hasattr(group, "FiberThickness"):
            group.addProperty("App::PropertyLength", "FiberThickness", "Live Parameters", "Material Thickness")
        if not hasattr(group, "FiberGenerateCovers"):
            group.addProperty("App::PropertyBool", "FiberGenerateCovers", "Live Parameters", "Generate Covers")
        if not hasattr(group, "LinkedFiberSketchName"):
            group.addProperty("App::PropertyString", "LinkedFiberSketchName", "System Core", "Linked Sketch")
            
        group.FiberWidth = w
        group.FiberDepth = d
        group.FiberThickness = t
        group.FiberGenerateCovers = gen_covers
        group.LinkedFiberSketchName = self.selected_sketch.Name
            
        App.GlobalFiberObserver.trigger_rebuild_manually(group)

    def generate_manual(self, w, d, t, gen_covers):
        doc = App.ActiveDocument or App.newDocument("Fiber_Tray_System")
        doc.openTransaction("Create Manual Fitting")
        
        # --- PROGRESS DIALOG TRIGGER ---
        progress = QtWidgets.QProgressDialog("Generating Manual Fiber Tray...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Generating 3D Models")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            main_group = doc.getObject("Fiber_Tray_System")
            if not main_group:
                main_group = doc.addObject("App::DocumentObjectGroup", "Fiber_Tray_System")

            f_type = self.type_cb.currentText()
            l = self.length_input.value()
            
            def get_or_create_subgroup(parent_group, name):
                for obj in parent_group.Group:
                    if obj.Name == name or obj.Label == name: return obj
                sub = doc.addObject("App::DocumentObjectGroup", name)
                parent_group.addObject(sub)
                return sub

            folder_name = "Straight_Trays" if f_type == "STRAIGHT TRAY" else \
                          "Connectors" if "CONNECTOR" in f_type else "Fittings"
            
            target_folder = get_or_create_subgroup(main_group, folder_name)
            
            shape = self.get_manual_shape(f_type, l, w, d, t, False)
            if shape:
                base_m = App.Matrix()
                if f_type != "STRAIGHT TRAY":
                    _, _, offset = TrayGeom.get_centered_fitting("90" if "90" in f_type else "TEE" if "TEE" in f_type else "CROSS", w, d, t)
                    base_m.move(offset)
                
                obj = doc.addObject("Part::Feature", f_type.replace(" ", "_"))
                obj.Shape = shape.removeSplitter()
                obj.Placement = App.Placement(base_m)
                if hasattr(obj, "ViewObject") and obj.ViewObject: obj.ViewObject.ShapeColor = (1.0, 0.82, 0.1)
                target_folder.addObject(obj)

            if gen_covers:
                c_shape = self.get_manual_shape(f_type, l, w, d, t, True)
                if c_shape:
                    cov_folder = get_or_create_subgroup(main_group, "Covers")
                    c_obj = doc.addObject("Part::Feature", f_type.replace(" ", "_") + "_Cover")
                    c_obj.Shape = c_shape.removeSplitter()
                    c_obj.Placement = App.Placement(base_m)
                    if hasattr(c_obj, "ViewObject") and c_obj.ViewObject: c_obj.ViewObject.ShapeColor = (1.0, 0.82, 0.1)
                    cov_folder.addObject(c_obj)
                
            doc.recompute()
            doc.commitTransaction()
            FreeCADGui.SendMsgToActiveView("ViewFit")
        except Exception as e:
            doc.abortTransaction()
            App.Console.PrintError(f"Generation Error: {str(e)}\n")
        finally:
            progress.close()

class CreateFiberTrayCommand:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('FiberTray.svg') if ComfacUtils else "", 
            'MenuText': "Generate Fiber Tray System", 
            'ToolTip': "Select a Sketch to auto-route Fiber Trays"
        }
    
    def Activated(self):
        doc = App.ActiveDocument
        if not doc: App.newDocument("Fiber_Tray_System")
        sel_ex = FreeCADGui.Selection.getSelectionEx()
        sketch = None
        if sel_ex and hasattr(sel_ex[0].Object, "Geometry") and "Sketch" in type(sel_ex[0].Object).__name__:
            sketch = sel_ex[0].Object
            
        progress = None
        if sketch:
            progress = QtWidgets.QProgressDialog("Launching Fiber Tray Tool...\nPlease wait while geometry is calculated.", None, 0, 0)
            progress.setWindowTitle("Loading")
            progress.setWindowModality(QtCore.Qt.ApplicationModal)
            progress.setMinimumDuration(0)
            progress.show()
            QtWidgets.QApplication.processEvents()

        try:
            FreeCADGui.Control.showDialog(FiberTrayTaskPanel(sketch))
        finally:
            if progress:
                progress.close()

try:
    FreeCADGui.addCommand('CreateFiberTray', CreateFiberTrayCommand())
except Exception:
    pass