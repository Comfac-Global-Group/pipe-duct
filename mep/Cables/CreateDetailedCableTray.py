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
# GEOMETRY ENGINE (CABLE TRAY)
# ==========================================
class CableTrayGeometryEngine:
    def calculate_offset_pts(self, pts, offset):
        normals = []
        for i in range(len(pts)-1):
            v = pts[i+1] - pts[i]
            if v.Length > 0.001: v.normalize()
            normals.append(App.Vector(-v.y, v.x, 0))
            
        offset_pts = []
        for i in range(len(pts)):
            if i == 0:
                offset_pts.append(pts[i] + normals[0] * offset)
            elif i == len(pts) - 1:
                offset_pts.append(pts[i] + normals[-1] * offset)
            else:
                n1 = normals[i-1]; n2 = normals[i]
                n_bisect = n1 + n2
                if n_bisect.Length < 0.001: n_miter = n1
                else:
                    n_bisect.normalize()
                    dot = n1.dot(n_bisect)
                    if dot < 0.001: dot = 1.0
                    n_miter = n_bisect * (1.0 / dot)
                offset_pts.append(pts[i] + n_miter * offset)
        return offset_pts

    def get_dynamic_elbow_2d(self, theta_rad, w, d, t):
        v1 = App.Vector(1, 0, 0)
        v2 = App.Vector(math.cos(theta_rad), math.sin(theta_rad), 0)
        
        p1 = v1 * 150.0
        p2 = App.Vector(0,0,0)
        p3 = v2 * 150.0
        path_pts = [p1, p2, p3]
        
        left_pts = self.calculate_offset_pts(path_pts, w/2)
        right_pts = self.calculate_offset_pts(path_pts, -w/2)
        
        lip = 12.0; tray = None
        for i in range(len(path_pts)-1):
            p_wall = [left_pts[i], right_pts[i], right_pts[i+1], left_pts[i+1], left_pts[i]]
            f = Part.Face(Part.makePolygon(p_wall)).extrude(App.Vector(0,0,t))
            tray = f if tray is None else tray.fuse(f)
            
        wl = self.make_continuous_walls(left_pts, d, t, lip, invert=False)
        wr = self.make_continuous_walls(right_pts, d, t, lip, invert=True)
        
        if wl: tray = tray.fuse(wl)
        if wr: tray = tray.fuse(wr)
        
        return tray, 150.0

    def get_centered_fitting(self, f_type, w, d, t):
        if f_type == "END":
            shape = self.make_end_cap(w, d, t)
            return shape, t, App.Vector(-w/2, -t, 0)
        elif f_type == "90":
            shape = self.make_90_elbow(w, d, t)
            return shape, 150.0 + w/2, App.Vector(-w/2, -w/2, 0)
        elif f_type == "TEE":
            shape = self.make_tee(w, d, t)
            return shape, 200.0 + w/2, App.Vector(-(w+400.0)/2, -w/2, 0)
        elif f_type == "CROSS":
            shape = self.make_connector(w, d, t)
            return shape, 150.0 + w/2, App.Vector(0, 0, 0)
        return None, 0, App.Vector(0,0,0)

    def get_routing_placement(self, X_dir, Z_dir, target_pt, offset_vec=App.Vector(0,0,0)):
        X_dir = App.Vector(X_dir.x, X_dir.y, X_dir.z)
        if X_dir.Length < 0.001: X_dir = App.Vector(1,0,0)
        else: X_dir.normalize()
        
        Z_dir = App.Vector(Z_dir.x, Z_dir.y, Z_dir.z)
        if Z_dir.Length < 0.001: Z_dir = App.Vector(0,0,1)
        else: Z_dir.normalize()
        
        Y_dir = Z_dir.cross(X_dir)
        if Y_dir.Length < 0.001: 
            Y_dir = App.Vector(0,1,0).cross(X_dir)
            if Y_dir.Length < 0.001:
                Y_dir = App.Vector(1,0,0).cross(X_dir)
                
        Y_dir.normalize()
        Z_dir = X_dir.cross(Y_dir).normalize()
        Y_dir = Z_dir.cross(X_dir).normalize()
        
        m = App.Matrix()
        m.A11 = X_dir.x; m.A12 = Y_dir.x; m.A13 = Z_dir.x; m.A14 = target_pt.x
        m.A21 = X_dir.y; m.A22 = Y_dir.y; m.A23 = Z_dir.y; m.A24 = target_pt.y
        m.A31 = X_dir.z; m.A32 = Y_dir.z; m.A33 = Z_dir.z; m.A34 = target_pt.z
        
        route_plm = App.Placement(m)
        base_m = App.Matrix()
        base_m.move(offset_vec)
        base_plm = App.Placement(base_m)
        
        return route_plm.multiply(base_plm)

    def make_continuous_walls(self, inner_pts, d, t, lip, invert=False):
        n_sign = -1 if invert else 1
        normals = []
        for i in range(len(inner_pts)-1):
            v = inner_pts[i+1] - inner_pts[i]
            if v.Length > 0.001: v.normalize()
            normals.append(App.Vector(-v.y * n_sign, v.x * n_sign, 0))
            
        outer_pts = []; lip_pts = []
        for i in range(len(inner_pts)):
            if i == 0:
                outer_pts.append(inner_pts[i] - normals[0] * t)
                lip_pts.append(inner_pts[i] - normals[0] * lip)
            elif i == len(inner_pts) - 1:
                outer_pts.append(inner_pts[i] - normals[-1] * t)
                lip_pts.append(inner_pts[i] - normals[-1] * lip)
            else:
                n1 = normals[i-1]; n2 = normals[i]
                n_bisect = n1 + n2
                if n_bisect.Length < 0.001: n_miter = n1
                else:
                    n_bisect.normalize()
                    dot = n1.dot(n_bisect)
                    if dot < 0.001: dot = 1.0
                    n_miter = n_bisect * (1.0 / dot)
                outer_pts.append(inner_pts[i] - n_miter * t)
                lip_pts.append(inner_pts[i] - n_miter * lip)
                
        result = None
        for i in range(len(inner_pts)-1):
            p_wall = [inner_pts[i], outer_pts[i], outer_pts[i+1], inner_pts[i+1], inner_pts[i]]
            wall = Part.Face(Part.makePolygon(p_wall)).extrude(App.Vector(0,0,d))
            p_lip = [inner_pts[i], lip_pts[i], lip_pts[i+1], inner_pts[i+1], inner_pts[i]]
            lip_ext = Part.Face(Part.makePolygon(p_lip)).extrude(App.Vector(0,0,t))
            lip_ext.translate(App.Vector(0,0,d-t))
            seg = wall.fuse(lip_ext)
            result = seg if result is None else result.fuse(seg)
            
        return result

    def make_wall_with_lip(self, length, d, t, lip_width, invert_lip=False):
        wall = Part.makeBox(length, t, d)
        lip_y = -lip_width + t if invert_lip else 0
        lip = Part.makeBox(length, lip_width, t, App.Vector(0, lip_y, d - t))
        return wall.fuse(lip)

    def make_slot_tool(self, l, w, t):
        c1 = Part.makeCylinder(w/2, t, App.Vector(-l/2, 0, 0))
        c2 = Part.makeCylinder(w/2, t, App.Vector(l/2, 0, 0))
        b = Part.makeBox(l, w, t, App.Vector(-l/2, -w/2, 0))
        return b.fuse([c1, c2])

    def make_straight_tray(self, l, w, d, t):
        lip = 12.0
        tray = Part.makeBox(l, w, t, App.Vector(0, -w/2, 0))
        wl = self.make_wall_with_lip(l, d, t, lip, invert_lip=False)
        wl.translate(App.Vector(0, -w/2, 0))
        wr = self.make_wall_with_lip(l, d, t, lip, invert_lip=True)
        wr.translate(App.Vector(0, w/2 - t, 0))
        tray = tray.fuse([wl, wr])
        
        slot = self.make_slot_tool(25, 8, t*3)
        slot.rotate(App.Vector(0,0,0), App.Vector(0,0,1), 90)
        slot.translate(App.Vector(0, 0, -t))
        num_slots = int(l / 100.0)
        if num_slots > 0:
            spacing = l / (num_slots + 1)
            for i in range(1, num_slots + 1):
                sx = slot.copy()
                sx.translate(App.Vector(i * spacing, 0, 0))
                tray = tray.cut(sx)
        return tray

    def make_90_elbow(self, w, d, t):
        L = w + 150.0; chamf = 100.0; lip = 12.0
        pts = [
            App.Vector(0,0,0), App.Vector(L,0,0), App.Vector(L,w,0), 
            App.Vector(w+chamf, w, 0), App.Vector(w, w+chamf, 0), 
            App.Vector(w, L, 0), App.Vector(0, L, 0), App.Vector(0,0,0)
        ]
        base = Part.Face(Part.makePolygon(pts)).extrude(App.Vector(0, 0, t))
        ow_pts = [App.Vector(L, 0, 0), App.Vector(0, 0, 0), App.Vector(0, L, 0)]
        ow = self.make_continuous_walls(ow_pts, d, t, lip, invert=False)
        iw_pts = [App.Vector(L, w, 0), App.Vector(w+chamf, w, 0), App.Vector(w, w+chamf, 0), App.Vector(w, L, 0)]
        iw = self.make_continuous_walls(iw_pts, d, t, lip, invert=True)
        tray = base.fuse([ow, iw])
        
        slot = self.make_slot_tool(25, 8, t*3)
        slot.translate(App.Vector(0, 0, -t)) 
        for i in range(1, 4):
            sx = slot.copy(); sx.translate(App.Vector(w/2, w + 35*i, 0))
            sy = slot.copy(); sy.rotate(App.Vector(0,0,0), App.Vector(0,0,1), 90)
            sy.translate(App.Vector(w + 35*i, w/2, 0))
            tray = tray.cut(sx).cut(sy)
        sm = slot.copy(); sm.rotate(App.Vector(0,0,0), App.Vector(0,0,1), 45)
        sm.translate(App.Vector(w/2 + 25, w/2 + 25, 0))
        return tray.cut(sm)

    def make_tee(self, w, d, t):
        M = w + 400.0; B = 200.0; R = 75.0; cx = M / 2; lip = 12.0
        pts = [
            App.Vector(0,0,0), App.Vector(M,0,0), App.Vector(M,w,0),
            App.Vector(cx+w/2+R, w, 0), App.Vector(cx+w/2, w+R, 0), App.Vector(cx+w/2, w+B, 0),
            App.Vector(cx-w/2, w+B, 0), App.Vector(cx-w/2, w+R, 0), App.Vector(cx-w/2-R, w, 0),
            App.Vector(0,w,0), App.Vector(0,0,0)
        ]
        base = Part.Face(Part.makePolygon(pts)).extrude(App.Vector(0,0,t))
        w_back = self.make_continuous_walls([App.Vector(M, 0, 0), App.Vector(0, 0, 0)], d, t, lip, invert=False)
        w_front_r = self.make_continuous_walls([App.Vector(M, w, 0), App.Vector(cx+w/2+R, w, 0), App.Vector(cx+w/2, w+R, 0), App.Vector(cx+w/2, w+B, 0)], d, t, lip, invert=True)
        w_front_l = self.make_continuous_walls([App.Vector(cx-w/2, w+B, 0), App.Vector(cx-w/2, w+R, 0), App.Vector(cx-w/2-R, w, 0), App.Vector(0, w, 0)], d, t, lip, invert=True)
        return base.fuse([w_back, w_front_r, w_front_l])

    def make_connector(self, w, d, t):
        B = 100.0; chamf = 50.0; lip = 12.0; L = B + w/2 + chamf
        pts = [
            App.Vector(w/2, L, 0), App.Vector(w/2, w/2 + chamf, 0), App.Vector(w/2 + chamf, w/2, 0),
            App.Vector(L, w/2, 0), App.Vector(L, -w/2, 0), App.Vector(w/2 + chamf, -w/2, 0),
            App.Vector(w/2, -w/2 - chamf, 0), App.Vector(w/2, -L, 0), App.Vector(-w/2, -L, 0),
            App.Vector(-w/2, -w/2 - chamf, 0), App.Vector(-w/2 - chamf, -w/2, 0), App.Vector(-L, -w/2, 0),
            App.Vector(-L, w/2, 0), App.Vector(-w/2 - chamf, w/2, 0), App.Vector(-w/2, w/2 + chamf, 0),
            App.Vector(-w/2, L, 0), App.Vector(w/2, L, 0)
        ]
        base_face = Part.Face(Part.makePolygon(pts))
        tray = base_face.extrude(App.Vector(0, 0, t))
        quad_pts = [App.Vector(w/2, L, 0), App.Vector(w/2, w/2 + chamf, 0), App.Vector(w/2 + chamf, w/2, 0), App.Vector(L, w/2, 0)]
        w_quad = self.make_continuous_walls(quad_pts, d, t, lip, invert=False)
        walls = []
        for angle in [0, 90, 180, 270]:
            w_rot = w_quad.copy()
            w_rot.rotate(App.Vector(0,0,0), App.Vector(0,0,1), angle)
            walls.append(w_rot)
        for w_shape in walls: tray = tray.fuse(w_shape)
        bolt_hole = Part.makeCylinder(4, t*6) 
        bolt_hole.rotate(App.Vector(0,0,0), App.Vector(0,1,0), 90)
        bolt_hole.translate(App.Vector(-t*3, 0, 0)) 
        for angle in [0, 90, 180, 270]:
            for h in [20, 50, 80]:
                if h > B: continue 
                y_pos = L - h 
                bh1 = bolt_hole.copy()
                bh1.translate(App.Vector(w/2, y_pos, d/2))
                bh1.rotate(App.Vector(0,0,0), App.Vector(0,0,1), angle)
                tray = tray.cut(bh1)
                bh2 = bolt_hole.copy()
                bh2.translate(App.Vector(-w/2, y_pos, d/2))
                bh2.rotate(App.Vector(0,0,0), App.Vector(0,0,1), angle)
                tray = tray.cut(bh2)
        return tray

    def make_end_cap(self, w, d, t):
        plate = Part.makeBox(w, t, d)
        fl_l = Part.makeBox(t, 20.0, d-t*2, App.Vector(0, t, t))
        fl_r = Part.makeBox(t, 20.0, d-t*2, App.Vector(w-t, t, t))
        fl_b = Part.makeBox(w, 20.0, t, App.Vector(0, t, 0))
        return plate.fuse([fl_l, fl_r, fl_b])

    def calculate_system_components(self, sketch, w, d, t):
        if not hasattr(sketch, "Shape"):
            raise ValueError("Invalid Object: The selected item does not have a shape. Please ensure you selected a Sketch.")

        Z_up = App.Vector(0,0,1)
        if hasattr(sketch, "Placement"):
            Z_up = sketch.Placement.Rotation.multVec(App.Vector(0,0,1))

        edges = sketch.Shape.Edges
        raw_lines = []
        for edge in edges:
            if hasattr(edge, "Curve") and 'Line' in str(type(edge.Curve).__name__):
                p1 = edge.Vertexes[0].Point
                p2 = edge.Vertexes[-1].Point
                raw_lines.append((p1, p2))
                
        split_lines = []
        for p1, p2 in raw_lines:
            points_on_line = [p1, p2]
            v_line = p2 - p1
            l_sq = v_line.Length**2
            if l_sq > 0.001:
                for op1, op2 in raw_lines:
                    for pt in (op1, op2):
                        v_pt = pt - p1
                        t_val = v_pt.dot(v_line) / l_sq
                        if 0.001 < t_val < 0.999:
                            if (p1 + v_line * t_val - pt).Length < 0.1:
                                points_on_line.append(pt)
            points_on_line.sort(key=lambda pt: (pt - p1).Length)
            for i in range(len(points_on_line) - 1):
                if (points_on_line[i+1] - points_on_line[i]).Length > 0.1:
                    split_lines.append((points_on_line[i], points_on_line[i+1]))

        vertices = {}
        for p1, p2 in split_lines:
            k1 = (round(p1.x, 2), round(p1.y, 2), round(p1.z, 2))
            k2 = (round(p2.x, 2), round(p2.y, 2), round(p2.z, 2))
            if k1 not in vertices: vertices[k1] = []
            if k2 not in vertices: vertices[k2] = []
            v1 = App.Vector(p2.x - p1.x, p2.y - p1.y, p2.z - p1.z); v1.normalize()
            v2 = App.Vector(p1.x - p2.x, p1.y - p2.y, p1.z - p2.z); v2.normalize()
            vertices[k1].append(v1)
            vertices[k2].append(v2)

        components = {
            "Straight_Trays": [], "Elbows": [], "Tees": [], "Crosses": [], "End_Caps": []
        }
        vertex_allowances = {}

        for pt_key, vectors in vertices.items():
            degree = len(vectors)
            pt = App.Vector(pt_key[0], pt_key[1], pt_key[2])
            allowance = 0
            
            if degree > 2:
                for i in range(degree):
                    for j in range(i + 1, degree):
                        dot_val = vectors[i].dot(vectors[j])
                        angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, dot_val))))
                        is_90 = abs(angle_deg - 90.0) < 5.0
                        is_180 = abs(angle_deg - 180.0) < 5.0
                        if not (is_90 or is_180):
                            raise ValueError(f"Invalid Intersection! Tees and Crosses require 90° connections. Found an angle of {angle_deg:.1f}°.")
            elif degree == 2:
                dot_val = vectors[0].dot(vectors[1])
                angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, dot_val))))
                is_90 = abs(angle_deg - 90.0) < 5.0
                is_180 = abs(angle_deg - 180.0) < 5.0
                if not (is_90 or is_180):
                    raise ValueError(f"Invalid Elbow Angle ({angle_deg:.1f}°)! Cable trays can only bend at exactly 90°.")
            
            if degree == 1:
                shape, allowance, offset = self.get_centered_fitting("END", w, d, t)
                X_dir = vectors[0].cross(Z_up)
                if X_dir.Length < 0.001: X_dir = App.Vector(1,0,0)
                placement = self.get_routing_placement(X_dir, Z_up, pt, offset)
                components["End_Caps"].append((shape, placement))
            elif degree == 2:
                v1, v2 = vectors[0], vectors[1]
                if abs(v1.dot(v2) + 1.0) < 0.1: allowance = 0 
                else:
                    cross_val = v1.cross(v2).dot(Z_up)
                    if cross_val > 0: X_dir = v1; theta_v = v2
                    else: X_dir = v2; theta_v = v1
                    if abs(abs(v1.dot(v2))) < 0.05: 
                        shape, allowance, offset = self.get_centered_fitting("90", w, d, t)
                        placement = self.get_routing_placement(X_dir, Z_up, pt, offset)
                    else:
                        theta_rad = math.acos(max(-1.0, min(1.0, X_dir.dot(theta_v))))
                        shape, allowance = self.get_dynamic_elbow_2d(theta_rad, w, d, t)
                        placement = self.get_routing_placement(X_dir, Z_up, pt, App.Vector(0,0,0))
                    components["Elbows"].append((shape, placement))
            elif degree == 3:
                shape, allowance, offset = self.get_centered_fitting("TEE", w, d, t)
                v_branch = vectors[0]; v_straight = []
                for v in vectors:
                    has_opp = False
                    for other in vectors:
                        if v != other and abs(v.dot(other) + 1.0) < 0.1: has_opp = True
                    if not has_opp: v_branch = v
                    else: v_straight.append(v)
                if len(v_straight) > 0:
                    X_dir = v_branch.cross(Z_up)
                    if X_dir.Length < 0.001: X_dir = App.Vector(1,0,0)
                    placement = self.get_routing_placement(X_dir, Z_up, pt, offset)
                    components["Tees"].append((shape, placement))
            elif degree == 4:
                shape, allowance, offset = self.get_centered_fitting("CROSS", w, d, t)
                placement = self.get_routing_placement(vectors[0], Z_up, pt, offset)
                components["Crosses"].append((shape, placement))
            vertex_allowances[pt_key] = allowance

        for p1, p2 in split_lines:
            v_dir = p2 - p1
            total_len = v_dir.Length
            v_norm = App.Vector(v_dir.x, v_dir.y, v_dir.z); v_norm.normalize()
            k1 = (round(p1.x, 2), round(p1.y, 2), round(p1.z, 2))
            k2 = (round(p2.x, 2), round(p2.y, 2), round(p2.z, 2))
            a1 = vertex_allowances.get(k1, 0)
            a2 = vertex_allowances.get(k2, 0)
            
            if total_len < (a1 + a2 + 2.0): 
                shortfall = (a1 + a2 + 2.0) - total_len
                raise ValueError(f"Sketch segment too short! Length: {total_len:.1f}mm. Min required for fittings: {a1+a2+2.0:.1f}mm. Try moving points further apart by at least {shortfall:.1f}mm.")
            
            actual_len = total_len - a1 - a2
            if actual_len > 0.1:
                start_pt = p1 + (v_norm * a1)
                tray = self.make_straight_tray(actual_len, w, d, t)
                placement = self.get_routing_placement(v_norm, Z_up, start_pt, App.Vector(0,0,0))
                components["Straight_Trays"].append((tray, placement))
        return components

    def calculate_system_shape(self, sketch, w, d, t):
        components = self.calculate_system_components(sketch, w, d, t)
        all_shapes = []
        for folder_items in components.values():
            for s, p in folder_items:
                placed_shape = s.copy()
                placed_shape.Placement = p
                all_shapes.append(placed_shape.removeSplitter())
        if not all_shapes: return None
        return Part.makeCompound(all_shapes)


# ==========================================
# ZERO-LAG BACKGROUND OBSERVER
# ==========================================
class CableTrayLiveObserver:
    def __init__(self):
        self.pending_sketches = set()
        self.pending_groups = set()
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.check_and_process_rebuilds)

    def trigger_rebuild_manually(self, group, force_now=False):
        self.pending_groups.add(group)
        if force_now:
            self.process_rebuilds()
        else:
            self.check_and_process_rebuilds()

    def slotChangedObject(self, obj, prop):
        # FAST REGISTRATION: Zero loops. This completely fixes the lag while dragging lines.
        if obj.isDerivedFrom("Sketcher::SketchObject") and prop in ["Shape", "Placement"]:
            self.pending_sketches.add(obj)
            self.timer.start(800)
                
        elif hasattr(obj, "IsCableTraySystem") and getattr(obj, "IsCableTraySystem"):
            if prop in ["TrayWidth", "TrayDepth", "TrayThickness"]:
                self.pending_groups.add(obj)
                self.timer.start(800)

    def check_and_process_rebuilds(self):
        # 1. Do not process while the user is actively inside the sketch editor
        if FreeCADGui.ActiveDocument and FreeCADGui.ActiveDocument.getInEdit():
            self.timer.start(1000)
            return

        # 2. Gather groups that need processing
        groups_to_process = set(self.pending_groups)
        
        if self.pending_sketches:
            for doc in App.listDocuments().values():
                for doc_obj in doc.Objects:
                    if hasattr(doc_obj, "IsCableTraySystem") and getattr(doc_obj, "IsCableTraySystem"):
                        if getattr(doc_obj, "LinkedSketch", None) in self.pending_sketches:
                            groups_to_process.add(doc_obj)
        
        self.pending_sketches.clear()
        self.pending_groups.clear()

        valid_groups = [g for g in groups_to_process if g.Document]
        if not valid_groups: return

        self.groups_to_build = valid_groups
        self.process_rebuilds()

    def process_rebuilds(self):
        # Progress dialog only fires when we actually have things to build after closing the sketch
        if not hasattr(self, 'groups_to_build') or not self.groups_to_build:
            return

        progress = QtWidgets.QProgressDialog("Generating Cable Tray System...\nPlease Wait.", None, 0, 0)
        progress.setWindowTitle("Processing")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            for group in self.groups_to_build:
                if group.Document: 
                    self.rebuild_folder(group)
        except Exception as e:
            App.Console.PrintError(f"Cable Tray Observer Error: {str(e)}\n")
        finally:
            progress.close()
            self.groups_to_build = []

    def rebuild_folder(self, group):
        doc = group.Document
        sketch = getattr(group, "LinkedSketch", None)
        if not sketch: return
        
        w_prop = getattr(group, "TrayWidth", 300.0)
        d_prop = getattr(group, "TrayDepth", 100.0)
        t_prop = getattr(group, "TrayThickness", 2.0)
        
        w = w_prop.Value if hasattr(w_prop, 'Value') else float(w_prop)
        d = d_prop.Value if hasattr(d_prop, 'Value') else float(d_prop)
        t = t_prop.Value if hasattr(t_prop, 'Value') else float(t_prop)
        
        engine = CableTrayGeometryEngine()
        
        def gather_items(grp):
            items = []
            for child in grp.Group:
                if child != sketch:
                    items.append(child)
                    if child.isDerivedFrom("App::DocumentObjectGroup"):
                        items.extend(gather_items(child))
            return items

        try:
            components = engine.calculate_system_components(sketch, w, d, t)
        except ValueError as ve:
            # SILENT FAIL FOR BACKGROUND OBSERVERS: No modal popups interrupting workflow!
            error_msg = str(ve)
            for item in reversed(gather_items(group)):
                doc.removeObject(item.Name)
            doc.recompute()
            App.Console.PrintWarning(f"[CABLE TRAY] Removed geometry due to invalid sketch layout: {error_msg}\n")
            return

        for item in reversed(gather_items(group)):
            doc.removeObject(item.Name)

        def get_or_create_subgroup(parent_group, name):
            for obj in parent_group.Group:
                if obj.Name == name or obj.Label == name: return obj
            sub = doc.addObject("App::DocumentObjectGroup", name)
            parent_group.addObject(sub)
            return sub

        color = (0.8, 0.8, 0.85)
        for folder_name, items in components.items():
            if not items: continue 
            target_folder = get_or_create_subgroup(group, folder_name)
            base_name = folder_name[:-1] if folder_name.endswith('s') else folder_name
            for i, (shape, placement) in enumerate(items):
                obj = doc.addObject("Part::Feature", f"{base_name}_{i+1}")
                obj.Shape = shape.removeSplitter()
                obj.Placement = placement
                if hasattr(obj, "ViewObject") and obj.ViewObject:
                    obj.ViewObject.ShapeColor = color
                target_folder.addObject(obj)

        doc.recompute()

# Global Observer Registration
if not hasattr(App, "GlobalCableObserver"):
    App.GlobalCableObserver = CableTrayLiveObserver()
    App.addDocumentObserver(App.GlobalCableObserver)


# ==========================================
# UI CONTROLLER & PREVIEW MANAGER
# ==========================================
class DetailedCableTrayTaskPanel:
    def __init__(self, selected_sketch=None):
        self.selected_sketch = selected_sketch
        self.doc = App.ActiveDocument
        self.last_error = ""
        
        self.preview_manager = None
        if ComfacUtils and hasattr(ComfacUtils, 'PreviewManager'):
            self.preview_manager = ComfacUtils.PreviewManager(self.doc, "Cable_Tray_Preview")
        else:
            self.preview_obj = None 
            
        self.widths = [50, 75, 100, 125, 150, 200, 300]
        self.depths = [50, 100, 150]
        self.fittings = [
            "CABLE TRAY", "CABLE TRAY 90 DEGREE ELBOW", "CABLE TRAY TEE CONNECTOR",
            "CABLE TRAY CONNECTOR", "CABLE TRAY END CAP"
        ]
        
        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        if self.selected_sketch:
            self.mode_label = QtWidgets.QLabel("<b>Live Folder Mode Active</b><br>Will automatically route Cable Trays.")
            self.layout.addRow(self.mode_label)
        else:
            self.mode_label = QtWidgets.QLabel("<b>Manual Generation Mode</b><br>Select a Sketch to activate Smart Folders.")
            self.layout.addRow(self.mode_label)

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(self.fittings)
        if self.selected_sketch: self.type_cb.setEnabled(False)
        
        self.length_input = QtWidgets.QDoubleSpinBox()
        self.length_input.setRange(10.0, 10000.0)
        self.length_input.setValue(2400.0)
        self.length_input.setSuffix(" mm")
        if self.selected_sketch: self.length_input.setEnabled(False)

        self.width_cb = QtWidgets.QComboBox()
        self.width_cb.addItems([f"{w} MM" for w in self.widths])
        
        self.depth_cb = QtWidgets.QComboBox()
        self.depth_cb.addItems([f"{d} MM" for d in self.depths])

        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(1.0, 10.0); self.thick_input.setValue(2.0); self.thick_input.setSuffix(" mm")

        self.layout.addRow("Fitting Type:", self.type_cb)
        self.layout.addRow("Tray Length:", self.length_input)
        self.layout.addRow("Tray Width:", self.width_cb)
        self.layout.addRow("Tray Depth:", self.depth_cb)
        self.layout.addRow("Material Thick:", self.thick_input)

        self.type_cb.currentIndexChanged.connect(self.update_ui)
        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.length_input.valueChanged.connect(self.trigger_preview)
        self.width_cb.currentIndexChanged.connect(self.trigger_preview)
        self.depth_cb.currentIndexChanged.connect(self.trigger_preview)
        self.thick_input.valueChanged.connect(self.trigger_preview)
        
        self.update_ui()
        self.trigger_preview()

    def update_ui(self):
        is_straight = (self.type_cb.currentText() == "CABLE TRAY")
        if not self.selected_sketch: 
            self.length_input.setEnabled(is_straight)

    def trigger_preview(self):
        w_val = float(self.width_cb.currentText().replace(" MM", ""))
        d_val = float(self.depth_cb.currentText().replace(" MM", ""))
        t_val = self.thick_input.value()
        engine = CableTrayGeometryEngine()
        
        if not self.preview_manager and self.doc:
            existing_ghost = self.doc.getObject("Preview_Ghost")
            if existing_ghost:
                self.doc.removeObject(existing_ghost.Name)
                self.doc.recompute()

        try:
            if self.selected_sketch:
                shape = engine.calculate_system_shape(self.selected_sketch, w_val, d_val, t_val)
                placement = App.Placement()
            else:
                f_type = self.type_cb.currentText()
                if f_type == "CABLE TRAY":
                    shape = engine.make_straight_tray(self.length_input.value(), w_val, d_val, t_val)
                    placement = App.Placement()
                else:
                    fit_code = {"CABLE TRAY 90 DEGREE ELBOW": "90", "CABLE TRAY TEE CONNECTOR": "TEE", "CABLE TRAY CONNECTOR": "CROSS", "CABLE TRAY END CAP": "END"}[f_type]
                    shape, _, offset = engine.get_centered_fitting(fit_code, w_val, d_val, t_val)
                    m = App.Matrix()
                    if f_type == "CABLE TRAY END CAP": m.rotateZ(math.radians(-90))
                    m.move(offset); placement = App.Placement(m)

            if not shape: return
            self.last_error = "" 
            
            if self.preview_manager:
                shape_copy = shape.copy()
                shape_copy.Placement = placement
                self.preview_manager.update(shape_copy, color=(0.2, 0.8, 0.2))
            elif self.doc:
                self.preview_obj = self.doc.addObject("Part::Feature", "Preview_Ghost")
                self.preview_obj.Shape = shape.removeSplitter()
                self.preview_obj.Placement = placement
                if hasattr(self.preview_obj, "ViewObject") and self.preview_obj.ViewObject:
                    self.preview_obj.ViewObject.ShapeColor = (0.2, 0.8, 0.2)
                    self.preview_obj.ViewObject.Transparency = 70
                self.doc.recompute()
            
        except ValueError as e:
            error_msg = str(e)
            if self.preview_manager:
                self.preview_manager.clear()
            elif self.preview_obj and self.preview_obj.Name in self.doc.Objects:
                self.doc.removeObject(self.preview_obj.Name)
                self.preview_obj = None
                self.doc.recompute()
                
            if getattr(self, 'last_error', None) != error_msg:
                self.last_error = error_msg
                # Task panel popups are fine, background ones are bad.
                QtWidgets.QMessageBox.warning(self.form, "Preview Error", error_msg)
        except Exception: pass

    def get_or_create_group(self, doc, parent, folder_name):
        for obj in parent.Group:
            if obj.Name == folder_name or obj.Label == folder_name: return obj
        sub_group = doc.addObject("App::DocumentObjectGroup", folder_name)
        parent.addObject(sub_group); return sub_group

    def setup_smart_folder(self, w, d, t):
        doc = App.ActiveDocument
        folder_name = f"{self.selected_sketch.Name}_CableSystem"
        group = doc.getObject(folder_name)
        
        if not group:
            group = doc.addObject("App::DocumentObjectGroup", folder_name)
            
        if not hasattr(group, "IsCableTraySystem"):
            group.addProperty("App::PropertyBool", "IsCableTraySystem", "System Core", "Identifies group as Cable Tray")
        if not hasattr(group, "TrayWidth"):
            group.addProperty("App::PropertyLength", "TrayWidth", "Live Parameters", "Tray Width")
        if not hasattr(group, "TrayDepth"):
            group.addProperty("App::PropertyLength", "TrayDepth", "Live Parameters", "Tray Depth")
        if not hasattr(group, "TrayThickness"):
            group.addProperty("App::PropertyLength", "TrayThickness", "Live Parameters", "Material Thickness")
        if not hasattr(group, "LinkedSketch"):
            group.addProperty("App::PropertyLink", "LinkedSketch", "System Core", "Linked Sketch")
            
        group.IsCableTraySystem = True
        group.TrayWidth = w
        group.TrayDepth = d
        group.TrayThickness = t
        group.LinkedSketch = self.selected_sketch
            
        App.GlobalCableObserver.trigger_rebuild_manually(group, force_now=True)

    def generate_manual(self, w, d, t):
        doc = App.ActiveDocument or App.newDocument("Cable_Tray_System")
        doc.openTransaction("Generate Manual Cable Tray")
        
        progress = QtWidgets.QProgressDialog("Generating Manual Cable Tray...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Generating 3D Models")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            main_group = doc.getObject("Cable_Tray_System") or doc.addObject("App::DocumentObjectGroup", "Cable_Tray_System")
            
            f_type = self.type_cb.currentText()
            folder = {"CABLE TRAY": "Straight_Trays", "CABLE TRAY 90 DEGREE ELBOW": "Elbows", "CABLE TRAY TEE CONNECTOR": "Tees", "CABLE TRAY CONNECTOR": "Crosses", "CABLE TRAY END CAP": "End_Caps"}[f_type]
            target = self.get_or_create_group(doc, main_group, folder)
            engine = CableTrayGeometryEngine()
            
            if f_type == "CABLE TRAY":
                shape = engine.make_straight_tray(self.length_input.value(), w, d, t); placement = App.Placement()
            else:
                fit_code = {"CABLE TRAY 90 DEGREE ELBOW": "90", "CABLE TRAY TEE CONNECTOR": "TEE", "CABLE TRAY CONNECTOR": "CROSS", "CABLE TRAY END CAP": "END"}[f_type]
                shape, _, offset = engine.get_centered_fitting(fit_code, w, d, t)
                m = App.Matrix()
                if f_type == "CABLE TRAY END CAP": m.rotateZ(math.radians(-90))
                m.move(offset); placement = App.Placement(m)
            
            obj = doc.addObject("Part::Feature", f_type.title().replace(" ", "_"))
            obj.Shape = shape.removeSplitter(); obj.Placement = placement
            target.addObject(obj)
            
            doc.recompute(); doc.commitTransaction(); FreeCADGui.SendMsgToActiveView("ViewFit")
        except Exception as e:
            doc.abortTransaction()
            App.Console.PrintError(f"Error: {str(e)}\n")
        finally:
            progress.close()

    def accept(self):
        w = float(self.width_cb.currentText().replace(" MM", ""))
        d = float(self.depth_cb.currentText().replace(" MM", ""))
        t = self.thick_input.value()
        
        if self.preview_manager: self.preview_manager.clear()
        elif self.doc and self.doc.getObject("Preview_Ghost"): 
            self.doc.removeObject("Preview_Ghost")
            self.doc.recompute()
            
        FreeCADGui.Control.closeDialog()

        if self.selected_sketch:
            self.setup_smart_folder(w, d, t)
        else:
            self.generate_manual(w, d, t)

    def reject(self):
        if self.preview_manager: self.preview_manager.clear()
        elif self.doc and self.doc.getObject("Preview_Ghost"): 
            self.doc.removeObject("Preview_Ghost")
            self.doc.recompute()
        FreeCADGui.Control.closeDialog()

class CreateDetailedCableTrayCommand:
    def GetResources(self):
        return {'Pixmap': ComfacUtils.get_icon_path('CableTray.svg') if ComfacUtils else "", 'MenuText': "Generate Organized Cable Tray", 'ToolTip': "Create cable tray fittings organized in folders"}
    
    def Activated(self):
        doc = App.ActiveDocument
        if not doc: App.newDocument("Cable_Tray_System")
        sel = FreeCADGui.Selection.getSelectionEx()
        sketch = None
        
        if sel:
            obj = sel[0].Object
            if obj.isDerivedFrom("Sketcher::SketchObject"):
                sketch = obj
                
        progress = None
        if sketch:
            progress = QtWidgets.QProgressDialog("Launching Cable Tray Tool...\nPlease wait while geometry is calculated.", None, 0, 0)
            progress.setWindowTitle("Loading")
            progress.setWindowModality(QtCore.Qt.ApplicationModal)
            progress.setMinimumDuration(0)
            progress.show()
            QtWidgets.QApplication.processEvents()
            
        try:
            FreeCADGui.Control.showDialog(DetailedCableTrayTaskPanel(sketch))
        finally:
            if progress:
                progress.close()

try:
    FreeCADGui.addCommand('CreateDetailedCableTray', CreateDetailedCableTrayCommand())
except Exception: pass