import FreeCAD as App
import FreeCADGui
import Part
import math
import time
from compat import QtWidgets, QtCore, QtGui

# Safely import ComfacUtils to grab the PreviewManager
try:
    import ComfacUtils
except ImportError:
    ComfacUtils = None

# ==========================================
# GEOMETRY ENGINE (Headless Math & Shapes)
# ==========================================
class CableLadderGeometryEngine:
    def safe_fuse(self, base_shape, shapes_to_fuse):
        """Safely fuses an array of shapes, ignoring None values to prevent crashes."""
        valid_shapes = [s for s in shapes_to_fuse if s is not None]
        if valid_shapes:
            return base_shape.fuse(valid_shapes)
        return base_shape

    def get_offset_pts(self, pts, dist):
        off_pts = []
        for i in range(len(pts)):
            if i == 0:
                v = pts[1] - pts[0]; v.normalize()
                n = App.Vector(-v.y, v.x, 0)
                off_pts.append(pts[0] + n * dist)
            elif i == len(pts) - 1:
                v = pts[-1] - pts[-2]; v.normalize()
                n = App.Vector(-v.y, v.x, 0)
                off_pts.append(pts[-1] + n * dist)
            else:
                v1 = pts[i] - pts[i-1]; v1.normalize()
                v2 = pts[i+1] - pts[i]; v2.normalize()
                n1 = App.Vector(-v1.y, v1.x, 0)
                n2 = App.Vector(-v2.y, v2.x, 0)
                n = (n1 + n2)
                if n.Length < 0.001: 
                    n = n1
                else:
                    n.normalize()
                    dot = n.dot(n1)
                    if dot > 0.001: n = n * (1.0 / dot)
                off_pts.append(pts[i] + n * dist)
        return off_pts

    def get_offset_pts_v(self, pts, dist):
        off_pts = []
        for i in range(len(pts)):
            if i == 0:
                v = pts[1] - pts[0]; v.normalize()
                n = App.Vector(-v.z, 0, v.x)
                off_pts.append(pts[0] + n * dist)
            elif i == len(pts) - 1:
                v = pts[-1] - pts[-2]; v.normalize()
                n = App.Vector(-v.z, 0, v.x)
                off_pts.append(pts[-1] + n * dist)
            else:
                v1 = pts[i] - pts[i-1]; v1.normalize()
                v2 = pts[i+1] - pts[i]; v2.normalize()
                n1 = App.Vector(-v1.z, 0, v1.x)
                n2 = App.Vector(-v2.z, 0, v2.x)
                n = (n1 + n2)
                if n.Length < 0.001: 
                    n = n1
                else:
                    n.normalize()
                    dot = n.dot(n1)
                    if dot > 0.001: n = n * (1.0 / dot)
                off_pts.append(pts[i] + n * dist)
        return off_pts

    def make_rail_h(self, pts, d, t, lip, inward_offset):
        web_out = self.get_offset_pts(pts, 0)
        web_in = self.get_offset_pts(pts, inward_offset * (t / abs(inward_offset)))
        web = Part.Face(Part.makePolygon(web_out + web_in[::-1] + [web_out[0]])).extrude(App.Vector(0,0,d))

        lip_in = self.get_offset_pts(pts, inward_offset)
        lip_base = Part.Face(Part.makePolygon(web_out + lip_in[::-1] + [web_out[0]]))
        lip_bot = lip_base.extrude(App.Vector(0,0,t))
        lip_top = lip_base.extrude(App.Vector(0,0,t)).translate(App.Vector(0,0,d-t))

        return web.fuse([lip_bot, lip_top])

    def make_rail_v(self, pts, y_pos, d, t, lip, flip_y):
        web_bot = self.get_offset_pts_v(pts, 0)
        web_top = self.get_offset_pts_v(pts, d)
        web = Part.Face(Part.makePolygon(web_bot + web_top[::-1] + [web_bot[0]])).extrude(App.Vector(0, t, 0))

        lip_bot_top = self.get_offset_pts_v(pts, t)
        lip_bot = Part.Face(Part.makePolygon(web_bot + lip_bot_top[::-1] + [web_bot[0]])).extrude(App.Vector(0, lip, 0))

        lip_top_bot = self.get_offset_pts_v(pts, d - t)
        lip_top = Part.Face(Part.makePolygon(lip_top_bot + web_top[::-1] + [lip_top_bot[0]])).extrude(App.Vector(0, lip, 0))

        rail = web.fuse([lip_bot, lip_top])
        if flip_y:
            rail = rail.mirror(App.Vector(0,0,0), App.Vector(0,1,0))
        rail.translate(App.Vector(0, y_pos, 0))
        return rail

    def make_rung_h(self, p1, p2, t):
        v = p2 - p1
        if v.Length < 1.0: return None
        angle = math.degrees(math.atan2(v.y, v.x))
        rung = Part.makeBox(v.Length, 20, 15, App.Vector(0, -10, 0))
        rung.rotate(App.Vector(0,0,0), App.Vector(0,0,1), angle)
        rung.translate(p1 + App.Vector(0, 0, t))
        return rung

    def make_rung_v(self, pos, dir_v, w, t):
        angle = math.degrees(math.atan2(-dir_v.z, dir_v.x))
        rung = Part.makeBox(20, w - 2*t, 15, App.Vector(-10, t, 0))
        rung.rotate(App.Vector(0,0,0), App.Vector(0,1,0), angle)
        n = App.Vector(-dir_v.z, 0, dir_v.x); n.normalize()
        rung.translate(pos + n * t)
        return rung

    def make_straight_ladder(self, l, w, d, t, rung_spacing=300.0):
        lip = 15.0
        path_l = [App.Vector(0, w/2, 0), App.Vector(l, w/2, 0)]
        path_r = [App.Vector(0, -w/2, 0), App.Vector(l, -w/2, 0)]
        
        rail_l = self.make_rail_h(path_l, d, t, lip, -lip)
        rail_r = self.make_rail_h(path_r, d, t, lip, lip)
        ladder = rail_l.fuse(rail_r)
        
        # Dynamic Rung Spacing applied here (No End Plates)
        rungs = []
        for x in range(int(rung_spacing / 2), int(l) - 50, int(rung_spacing)):
            rungs.append(self.make_rung_h(App.Vector(x, -w/2, 0), App.Vector(x, w/2, 0), t))
            
        ladder = self.safe_fuse(ladder, rungs)
        return ladder

    def make_90_elbow(self, l, w, d, t):
        R = 300.0; Ri = R - w/2; Ro = R + w/2
        E = max(l/2.0 - Ro, 100.0)
        lip = 15.0

        i_path = [App.Vector(-E, Ri, 0), App.Vector(Ri*0.4142, Ri, 0), App.Vector(Ri, Ri*0.4142, 0), App.Vector(Ri, -E, 0)]
        o_path = [App.Vector(-E, Ro, 0), App.Vector(Ro*0.4142, Ro, 0), App.Vector(Ro, Ro*0.4142, 0), App.Vector(Ro, -E, 0)]
        
        rail_in = self.make_rail_h(i_path, d, t, lip, inward_offset=lip)
        rail_out = self.make_rail_h(o_path, d, t, lip, inward_offset=-lip)
        ladder = rail_in.fuse(rail_out)

        ladder = self.safe_fuse(ladder, [
            self.make_rung_h(i_path[1], o_path[1], t),
            self.make_rung_h(i_path[2], o_path[2], t),
            self.make_rung_h((i_path[1]+i_path[2])*0.5, (o_path[1]+o_path[2])*0.5, t)
        ])
        
        rungs = []
        for x in range(300, int(E), 300):
            rungs.append(self.make_rung_h(App.Vector(-x, Ri, 0), App.Vector(-x, Ro, 0), t))
            rungs.append(self.make_rung_h(App.Vector(Ri, -x, 0), App.Vector(Ro, -x, 0), t))
        
        return self.safe_fuse(ladder, rungs)

    def make_tee(self, l, w, d, t, is_sketch=False):
        M = l; B = l/2.0; C = 150.0; lip = 15.0
        
        back_path = [App.Vector(-M/2, w/2, 0), App.Vector(M/2, w/2, 0)]
        front_mid = [App.Vector(-w/2 - C, -w/2, 0), App.Vector(w/2 + C, -w/2, 0)] 
        fl_path = [App.Vector(-M/2, -w/2, 0), App.Vector(-w/2 - C, -w/2, 0), App.Vector(-w/2, -w/2 - C, 0), App.Vector(-w/2, -B, 0)]
        fr_path = [App.Vector(w/2, -B, 0), App.Vector(w/2, -w/2 - C, 0), App.Vector(w/2 + C, -w/2, 0), App.Vector(M/2, -w/2, 0)]
        
        ladder = self.make_rail_h(back_path, d, t, lip, inward_offset=-lip)
        ladder = ladder.fuse(self.make_rail_h(front_mid, 18.0, t, lip, inward_offset=lip))
        ladder = ladder.fuse(self.make_rail_h(fl_path, d, t, lip, inward_offset=lip))
        ladder = ladder.fuse(self.make_rail_h(fr_path, d, t, lip, inward_offset=lip))
        
        rungs = []
        if is_sketch:
            rungs.append(self.make_rung_h(App.Vector(-w/4, -w/2, 0), App.Vector(-w/4, w/2, 0), t))
            rungs.append(self.make_rung_h(App.Vector(w/4, -w/2, 0), App.Vector(w/4, w/2, 0), t))
        else:
            for x in range(int(-M/2 + 150), int(M/2), 300):
                rungs.append(self.make_rung_h(App.Vector(x, -w/2, 0), App.Vector(x, w/2, 0), t))
            for y in range(int(-w/2 - C - 150), int(-B), -300):
                rungs.append(self.make_rung_h(App.Vector(-w/2, y, 0), App.Vector(w/2, y, 0), t))
            
        rungs.extend([
            self.make_rung_h(fl_path[1], App.Vector(fl_path[1].x, w/2, 0), t),
            self.make_rung_h(fr_path[2], App.Vector(fr_path[2].x, w/2, 0), t),
            self.make_rung_h(App.Vector(-w/2, -w/2 - C, 0), App.Vector(w/2, -w/2 - C, 0), t)
        ])
        return self.safe_fuse(ladder, rungs)

    def make_cross(self, l, w, d, t, is_sketch=False):
        M = l; C = 150.0; lip = 15.0
        paths = [
            ([App.Vector(-M/2, w/2, 0), App.Vector(-w/2 - C, w/2, 0), App.Vector(-w/2, w/2 + C, 0), App.Vector(-w/2, M/2, 0)], -lip),
            ([App.Vector(w/2, M/2, 0), App.Vector(w/2, w/2 + C, 0), App.Vector(w/2 + C, w/2, 0), App.Vector(M/2, w/2, 0)], -lip),
            ([App.Vector(M/2, -w/2, 0), App.Vector(w/2 + C, -w/2, 0), App.Vector(w/2, -w/2 - C, 0), App.Vector(w/2, -M/2, 0)], -lip),
            ([App.Vector(-w/2, -M/2, 0), App.Vector(-w/2, -w/2 - C, 0), App.Vector(-w/2 - C, -w/2, 0), App.Vector(-M/2, -w/2, 0)], -lip)
        ]

        top_mid = [App.Vector(-w/2 - C, w/2, 0), App.Vector(w/2 + C, w/2, 0)]
        bottom_mid = [App.Vector(-w/2 - C, -w/2, 0), App.Vector(w/2 + C, -w/2, 0)]

        ladder = self.make_rail_h(top_mid, 18.0, t, lip, inward_offset=-lip)
        ladder = ladder.fuse(self.make_rail_h(bottom_mid, 18.0, t, lip, inward_offset=lip))

        for p, offset in paths:
            rail = self.make_rail_h(p, d, t, lip, inward_offset=offset)
            ladder = ladder.fuse(rail)
            
        rungs = []
        if is_sketch:
            rungs.append(self.make_rung_h(App.Vector(-w/4, -w/2, 0), App.Vector(-w/4, w/2, 0), t))
            rungs.append(self.make_rung_h(App.Vector(w/4, -w/2, 0), App.Vector(w/4, w/2, 0), t))
        else:
            for x in range(int(-M/2 + 150), int(M/2), 300):
                rungs.append(self.make_rung_h(App.Vector(x, -w/2, 0), App.Vector(x, w/2, 0), t))
            for dist in range(int(w/2 + C + 150), int(M/2), 300):
                rungs.extend([
                    self.make_rung_h(App.Vector(-w/2, -dist, 0), App.Vector(w/2, -dist, 0), t),
                    self.make_rung_h(App.Vector(-w/2, dist, 0), App.Vector(w/2, dist, 0), t)
                ])
                
        rungs.extend([
            self.make_rung_h(paths[0][0][1], App.Vector(paths[0][0][1].x, -paths[0][0][1].y, 0), t),
            self.make_rung_h(paths[1][0][1], App.Vector(-paths[1][0][1].x, paths[1][0][1].y, 0), t),
            self.make_rung_h(paths[2][0][1], App.Vector(paths[2][0][1].x, -paths[2][0][1].y, 0), t),
            self.make_rung_h(paths[3][0][1], App.Vector(-paths[3][0][1].x, paths[3][0][1].y, 0), t)
        ])
        return self.safe_fuse(ladder, rungs)

    def make_vertical_elbow(self, l, w, d, t, direction="DOWN"):
        R = 300.0; E = max(l/2.0 - R, 100.0)
        lip = 15.0
        
        path = [
            App.Vector(-E, 0, 0), App.Vector(R*0.4142, 0, 0), 
            App.Vector(R, 0, -R + R*0.4142), App.Vector(R, 0, -E)
        ]
        
        rail_l = self.make_rail_v(path, 0, d, t, lip, flip_y=False)
        rail_r = self.make_rail_v(path, w, d, t, lip, flip_y=True)
        ladder = rail_l.fuse(rail_r)
        
        rungs = [
            self.make_rung_v(path[1], App.Vector(1, 0, 0), w, t),
            self.make_rung_v(path[2], App.Vector(0, 0, -1), w, t),
            self.make_rung_v((path[1]+path[2])*0.5, path[2] - path[1], w, t)
        ]
        
        for dist in range(300, int(E), 300):
            rungs.extend([
                self.make_rung_v(App.Vector(-dist, 0, 0), App.Vector(1, 0, 0), w, t),
                self.make_rung_v(App.Vector(R, 0, -dist), App.Vector(0, 0, -1), w, t)
            ])
            
        ladder = self.safe_fuse(ladder, rungs)
            
        if direction == "UP":
            ladder = ladder.mirror(App.Vector(0,0,0), App.Vector(0,0,1))
            
        return ladder

    def calculate_sketch_shapes(self, sketch, w, d, t, rung_spacing=300.0):
        """Analyzes the sketch and builds all ladders/fittings in memory, categorized."""
        ladders, fittings = [], []
        edges = [geom for geom in sketch.Geometry if type(geom).__name__ == 'LineSegment']
        
        raw_lines = []
        for edge in edges:
            p1 = App.Vector(edge.StartPoint.x, edge.StartPoint.y, 0)
            p2 = App.Vector(edge.EndPoint.x, edge.EndPoint.y, 0)
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
        for p1_v, p2_v in split_lines:
            p1 = (round(p1_v.x, 2), round(p1_v.y, 2), round(p1_v.z, 2))
            p2 = (round(p2_v.x, 2), round(p2_v.y, 2), round(p2_v.z, 2))
            
            if p1 not in vertices: vertices[p1] = []
            if p2 not in vertices: vertices[p2] = []
            
            v1 = (p2_v - p1_v).normalize()
            v2 = (p1_v - p2_v).normalize()
            
            vertices[p1].append(v1)
            vertices[p2].append(v2)

        allowance_dist = w/2 + 250.0 
        vertex_allowances = {} 

        for pt, vectors in vertices.items():
            degree = len(vectors)
            shape = None
            rot_angle = 0
            allowance = 0
            f_name = "Fitting"
            
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
                    raise ValueError(f"Invalid Elbow Angle ({angle_deg:.1f}°)! Cable Ladders can only bend at exactly 90°.")

            if degree == 2:
                if abs(vectors[0].dot(vectors[1])) < 0.1: 
                    v1, v2 = vectors[0], vectors[1]
                    if v1.x * v2.y - v1.y * v2.x > 0: base_v = v1
                    else: base_v = v2
                    rot_angle = math.degrees(math.atan2(base_v.y, base_v.x))
                    
                    allowance = 450.0 # FIXED OVERLAP BUG
                    l_elbow = (150 + 300 + w/2.0) * 2
                    shape = self.make_90_elbow(l_elbow, w, d, t)
                    f_name = "Elbow"
                    
                    mat = App.Matrix()
                    mat.move(App.Vector(-300.0, -300.0, 0))
                    mat.rotateZ(math.pi)
                    shape = shape.transformGeometry(mat)
                else:
                    allowance = 0
                    
            elif degree == 3:
                branch_v = vectors[0]
                for v in vectors:
                    has_opposite = any(abs(v.x + u.x) < 0.1 and abs(v.y + u.y) < 0.1 for u in vectors)
                    if not has_opposite:
                        branch_v = v
                        break
                rot_angle = math.degrees(math.atan2(branch_v.y, branch_v.x)) + 90
                shape = self.make_tee(allowance_dist*2, w, d, t, is_sketch=True)
                f_name = "Tee"
                allowance = allowance_dist
                
            elif degree == 4:
                shape = self.make_cross(allowance_dist*2, w, d, t, is_sketch=True)
                f_name = "Cross"
                allowance = allowance_dist

            vertex_allowances[pt] = allowance
            placement = App.Placement(App.Vector(pt[0], pt[1], pt[2]), App.Rotation(App.Vector(0,0,1), rot_angle))
            
            if shape:
                s_copy = shape.copy()
                s_copy.Placement = sketch.Placement.multiply(placement)
                fittings.append((f_name, s_copy)) # Store tuple for folder grouping

        for p1_v, p2_v in split_lines:
            p1 = (round(p1_v.x, 2), round(p1_v.y, 2), round(p1_v.z, 2))
            p2 = (round(p2_v.x, 2), round(p2_v.y, 2), round(p2_v.z, 2))
            
            v_dir = App.Vector(p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2])
            total_length = v_dir.Length
            v_dir.normalize()
            
            a1 = vertex_allowances.get(p1, 0)
            a2 = vertex_allowances.get(p2, 0)
            
            if total_length < (a1 + a2 + 2.0): 
                shortfall = (a1 + a2 + 2.0) - total_length
                raise ValueError(f"Sketch segment too short! Length: {total_length:.1f}mm. Min required for fittings: {a1+a2+2.0:.1f}mm. Try moving points further apart by at least {shortfall:.1f}mm.")
            
            actual_length = total_length - a1 - a2
            
            if actual_length > 0.1:
                start_pos = App.Vector(p1[0], p1[1], p1[2]) + v_dir * a1
                rot_angle = math.degrees(math.atan2(v_dir.y, v_dir.x))
                placement = App.Placement(start_pos, App.Rotation(App.Vector(0,0,1), rot_angle))
                
                shape = self.make_straight_ladder(actual_length, w, d, t, rung_spacing)
                s_copy = shape.copy()
                s_copy.Placement = sketch.Placement.multiply(placement)
                ladders.append(s_copy)

        return ladders, fittings


# ==========================================
# ZERO-LAG BACKGROUND OBSERVER
# ==========================================
class CableLadderLiveObserver:
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
        if obj.isDerivedFrom("Sketcher::SketchObject") and prop in ["Shape", "Placement"]:
            self.pending_sketches.add(obj)
            self.timer.start(800)

        elif hasattr(obj, "IsCableLadderSystem") and getattr(obj, "IsCableLadderSystem"):
            if prop in ["LadderWidth", "LadderDepth", "RailThickness", "RungSpacing"]:
                self.pending_groups.add(obj)
                self.timer.start(800)

    def check_and_process_rebuilds(self):
        if FreeCADGui.ActiveDocument and FreeCADGui.ActiveDocument.getInEdit():
            self.timer.start(1000)
            return

        groups_to_process = set(self.pending_groups)
        
        if self.pending_sketches:
            for doc in App.listDocuments().values():
                for doc_obj in doc.Objects:
                    if hasattr(doc_obj, "IsCableLadderSystem") and getattr(doc_obj, "IsCableLadderSystem"):
                        if getattr(doc_obj, "LinkedSketch", None) in self.pending_sketches:
                            groups_to_process.add(doc_obj)
        
        self.pending_sketches.clear()
        self.pending_groups.clear()

        valid_groups = [g for g in groups_to_process if g.Document]
        if not valid_groups: return

        self.groups_to_build = valid_groups
        self.process_rebuilds()

    def process_rebuilds(self):
        if not hasattr(self, 'groups_to_build') or not self.groups_to_build:
            return

        progress = QtWidgets.QProgressDialog("Generating Cable Ladder System...\nPlease Wait.", None, 0, 0)
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
            App.Console.PrintError(f"Cable Ladder Observer Error: {str(e)}\n")
        finally:
            progress.close()
            self.groups_to_build = []

    def rebuild_folder(self, group):
        doc = group.Document
        sketch = getattr(group, "LinkedSketch", None)
        if not sketch: return
        
        w_prop = getattr(group, "LadderWidth", 300.0)
        d_prop = getattr(group, "LadderDepth", 100.0)
        t_prop = getattr(group, "RailThickness", 2.0)
        rs_prop = getattr(group, "RungSpacing", 300.0)
        
        w = w_prop.Value if hasattr(w_prop, 'Value') else float(w_prop)
        d = d_prop.Value if hasattr(d_prop, 'Value') else float(d_prop)
        t = t_prop.Value if hasattr(t_prop, 'Value') else float(t_prop)
        rs = rs_prop.Value if hasattr(rs_prop, 'Value') else float(rs_prop)
        
        engine = CableLadderGeometryEngine()
        
        def gather_items(grp):
            items = []
            for child in grp.Group:
                if child != sketch:
                    items.append(child)
                    if child.isDerivedFrom("App::DocumentObjectGroup"):
                        items.extend(gather_items(child))
            return items

        try:
            ladders, fittings = engine.calculate_sketch_shapes(sketch, w, d, t, rs)
        except ValueError as ve:
            error_msg = str(ve)
            for item in reversed(gather_items(group)):
                doc.removeObject(item.Name)
            doc.recompute()
            App.Console.PrintWarning(f"[CABLE LADDER] Removed geometry due to invalid sketch layout: {error_msg}\n")
            return

        for item in reversed(gather_items(group)):
            doc.removeObject(item.Name)

        def get_or_create_subgroup(parent_group, name):
            for obj in parent_group.Group:
                if obj.Name == name or obj.Label == name: return obj
            sub = doc.addObject("App::DocumentObjectGroup", name)
            parent_group.addObject(sub)
            return sub

        if ladders:
            lad_grp = get_or_create_subgroup(group, "Straight_Ladders")
            for i, s in enumerate(ladders):
                obj = doc.addObject("Part::Feature", f"Straight_Ladder")
                obj.Shape = s.removeSplitter()
                if hasattr(obj, "ViewObject") and obj.ViewObject:
                    obj.ViewObject.ShapeColor = (0.85, 0.85, 0.86)
                    obj.ViewObject.LineColor = (0.2, 0.2, 0.2)
                lad_grp.addObject(obj)

        if fittings:
            for f_type, s in fittings:
                fit_grp = get_or_create_subgroup(group, f"{f_type}s")
                obj = doc.addObject("Part::Feature", f_type)
                obj.Shape = s.removeSplitter()
                if hasattr(obj, "ViewObject") and obj.ViewObject:
                    obj.ViewObject.ShapeColor = (0.85, 0.85, 0.86)
                    obj.ViewObject.LineColor = (0.2, 0.2, 0.2)
                fit_grp.addObject(obj)

        doc.recompute()

# Global Observer Registration
if not hasattr(App, "GlobalCableLadderObserver"):
    App.GlobalCableLadderObserver = CableLadderLiveObserver()
    App.addDocumentObserver(App.GlobalCableLadderObserver)


# ==========================================
# UI TASK PANEL
# ==========================================
class CableLadderFittingsTaskPanel:
    def __init__(self, selected_sketch=None, base_placement=None, snap_offset=None, snap_rotation=None):
        self.selected_sketch = selected_sketch
        self.base_placement = base_placement
        self.snap_offset = snap_offset or App.Vector(0, 0, 0)
        self.snap_rotation = snap_rotation or App.Rotation()
        self.doc = App.ActiveDocument
        self.engine = CableLadderGeometryEngine()
        self.last_error = ""
        
        self.preview_manager = None
        if ComfacUtils and hasattr(ComfacUtils, 'PreviewManager'):
            self.preview_manager = ComfacUtils.PreviewManager(self.doc) 
            if hasattr(self.preview_manager, 'init'):
                try:
                    self.preview_manager.init(self.doc, "Cable_Ladder_Preview")
                except TypeError:
                    self.preview_manager.init("Cable_Ladder_Preview")

        self.lengths = [2400]
        self.widths = [50, 75, 100, 125, 150, 200, 300]
        self.depths = [50, 100, 150]
        self.rung_spacings = [150, 300, 450, 600]
        
        self.fittings = [
            "CABLE LADDER STRAIGHT",
            "CABLE LADDER 90 HORIZONTAL ELBOW",
            "CABLE LADDER HORIZONTAL TEE CONNECTOR",
            "CABLE LADDER HORIZONTAL CROSS CONNECTOR",
            "CABLE LADDER VERTICAL DOWN ELBOW",
            "CABLE LADDER VERTICAL UP ELBOW"
        ]

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)
        
        if self.selected_sketch:
            self.mode_label = QtWidgets.QLabel("<b>Live Folder Mode Active</b><br>The tool will auto-generate all ladders and fittings.")
            self.layout.addRow(self.mode_label)
        else:
            self.mode_label = QtWidgets.QLabel("<b>Manual Auto-Snap Mode</b><br>Please select a Sketch before running to use Auto-Routing.")
            self.layout.addRow(self.mode_label)

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(self.fittings)
        if self.selected_sketch: self.type_cb.setEnabled(False)
        
        self.angle_cb = QtWidgets.QComboBox()
        self.angle_cb.addItems(["0", "90", "-90", "180"])
        self.angle_cb.setToolTip("Pivot the new part around the connection point")
        if self.selected_sketch: self.angle_cb.setEnabled(False)

        self.length_cb = QtWidgets.QComboBox()
        self.length_cb.addItems([f"{l} MM" for l in self.lengths] + ["Custom"])
        if self.selected_sketch: self.length_cb.setEnabled(False)

        self.custom_length = QtWidgets.QDoubleSpinBox()
        self.custom_length.setRange(1.0, 2400.0) 
        self.custom_length.setValue(2400.0)
        self.custom_length.setSuffix(" mm")
        if self.selected_sketch: self.custom_length.setEnabled(False)

        self.width_cb = QtWidgets.QComboBox()
        self.width_cb.addItems([f"{w} MM" for w in self.widths])

        self.depth_cb = QtWidgets.QComboBox()
        self.depth_cb.addItems([f"{d} MM" for d in self.depths])

        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(1.0, 10.0)
        self.thick_input.setValue(2.0)
        self.thick_input.setSuffix(" mm")

        self.spacing_cb = QtWidgets.QComboBox()
        self.spacing_cb.addItems([f"{rs} MM" for rs in self.rung_spacings])
        self.spacing_cb.setCurrentIndex(1) # Default to 300

        self.layout.addRow("Fitting Type:", self.type_cb)
        self.layout.addRow("Attach Angle (°):", self.angle_cb) 
        self.layout.addRow("Standard Length:", self.length_cb)
        self.layout.addRow("Custom Length:", self.custom_length)
        self.layout.addRow("Ladder Width:", self.width_cb)
        self.layout.addRow("Ladder Depth:", self.depth_cb)
        self.layout.addRow("Rail Thickness:", self.thick_input)
        self.layout.addRow("Rung Spacing:", self.spacing_cb)

        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.angle_cb.currentIndexChanged.connect(self.trigger_preview)
        self.length_cb.currentIndexChanged.connect(self.update_ui)
        self.custom_length.valueChanged.connect(self.trigger_preview)
        self.width_cb.currentIndexChanged.connect(self.trigger_preview)
        self.depth_cb.currentIndexChanged.connect(self.trigger_preview)
        self.thick_input.valueChanged.connect(self.trigger_preview)
        self.spacing_cb.currentIndexChanged.connect(self.trigger_preview)
        
        self.update_ui()
        self.trigger_preview()

    def update_ui(self):
        val_len = self.length_cb.currentText()
        if val_len == "Custom":
            self.custom_length.setEnabled(True)
        else:
            self.custom_length.setValue(float(val_len.replace(" MM", "")))
            self.custom_length.setEnabled(False)
            
        if self.selected_sketch:
            self.custom_length.setEnabled(False)
            
        self.trigger_preview()

    def calculate_manual_shape(self, f_type, l, w, d, t, attach_angle, rs=300.0):
        shape = None
        if f_type == "CABLE LADDER STRAIGHT": shape = self.engine.make_straight_ladder(l, w, d, t, rs)
        elif f_type == "CABLE LADDER 90 HORIZONTAL ELBOW": shape = self.engine.make_90_elbow(l, w, d, t)
        elif f_type == "CABLE LADDER HORIZONTAL TEE CONNECTOR": shape = self.engine.make_tee(l, w, d, t)
        elif f_type == "CABLE LADDER HORIZONTAL CROSS CONNECTOR": shape = self.engine.make_cross(l, w, d, t)
        elif f_type == "CABLE LADDER VERTICAL DOWN ELBOW": shape = self.engine.make_vertical_elbow(l, w, d, t, "DOWN")
        elif f_type == "CABLE LADDER VERTICAL UP ELBOW": shape = self.engine.make_vertical_elbow(l, w, d, t, "UP")

        if shape and self.base_placement:
            final_placement = self.base_placement.copy()
            final_placement.Base = final_placement.Base + final_placement.Rotation.multVec(self.snap_offset)
            final_placement.Rotation = final_placement.Rotation.multiply(self.snap_rotation)
            
            if attach_angle != 0.0:
                extra_rot = App.Rotation(App.Vector(0,0,1), attach_angle)
                final_placement.Rotation = final_placement.Rotation.multiply(extra_rot)
            
            fine_tune_offset = App.Vector(0, 0, 0)
            if "TEE" in f_type or "CROSS" in f_type:
                fine_tune_offset = App.Vector(l/2.0, 0, 0)
            elif "HORIZONTAL ELBOW" in f_type:
                R = 300.0
                Ro = R + w/2.0
                E = max(l/2.0 - Ro, 100.0)
                fine_tune_offset = App.Vector(E, -R, 0) 
            elif "VERTICAL" in f_type:
                R = 300.0
                E = max(l/2.0 - R, 100.0)
                fine_tune_offset = App.Vector(E, -w/2.0, 0)
                
            final_placement.Base = final_placement.Base + final_placement.Rotation.multVec(fine_tune_offset)
            shape.Placement = final_placement
            
        return [shape] if shape else []

    def trigger_preview(self, *args):
        if not self.preview_manager: return
        
        try:
            f_type = self.type_cb.currentText()
            l = self.custom_length.value()
            w = float(self.width_cb.currentText().replace(" MM", ""))
            d = float(self.depth_cb.currentText().replace(" MM", ""))
            t = self.thick_input.value()
            attach_angle = float(self.angle_cb.currentText())
            rs = float(self.spacing_cb.currentText().replace(" MM", ""))
            
            if self.selected_sketch:
                # Need to grab only the raw shapes for the preview
                ladders, fittings = self.engine.calculate_sketch_shapes(self.selected_sketch, w, d, t, rs)
                all_shapes = ladders + [s for f_name, s in fittings]
            else:
                all_shapes = self.calculate_manual_shape(f_type, l, w, d, t, attach_angle, rs)
            
            self.last_error = "" # Reset on success
            
            if all_shapes:
                preview_compound = Part.makeCompound(all_shapes)
                self.preview_manager.update(preview_compound, color=(0.85, 0.85, 0.86))
                
        except ValueError as e:
            error_msg = str(e)
            if self.preview_manager:
                if hasattr(self.preview_manager, 'clear'): self.preview_manager.clear()
            if getattr(self, 'last_error', None) != error_msg:
                self.last_error = error_msg
                QtWidgets.QMessageBox.warning(self.form, "Preview Error", error_msg)
        except Exception:
            pass

    def setup_smart_folder(self, w, d, t, rs):
        doc = App.ActiveDocument
        if not doc:
            doc = App.newDocument()
            
        folder_name = f"{self.selected_sketch.Name}_LadderSystem"
        group = doc.getObject(folder_name)
        
        if not group:
            group = doc.addObject("App::DocumentObjectGroup", folder_name)
            
        if not hasattr(group, "IsCableLadderSystem"):
            group.addProperty("App::PropertyBool", "IsCableLadderSystem", "System Core", "Identifies group as Cable Ladder")
        if not hasattr(group, "LadderWidth"):
            group.addProperty("App::PropertyLength", "LadderWidth", "Live Parameters", "Ladder Width")
        if not hasattr(group, "LadderDepth"):
            group.addProperty("App::PropertyLength", "LadderDepth", "Live Parameters", "Ladder Depth")
        if not hasattr(group, "RailThickness"):
            group.addProperty("App::PropertyLength", "RailThickness", "Live Parameters", "Rail Thickness")
        if not hasattr(group, "RungSpacing"):
            group.addProperty("App::PropertyLength", "RungSpacing", "Live Parameters", "Spacing between rungs")
        if not hasattr(group, "LinkedSketch"):
            group.addProperty("App::PropertyLink", "LinkedSketch", "System Core", "Linked Sketch")
            
        group.IsCableLadderSystem = True
        group.LadderWidth = w
        group.LadderDepth = d
        group.RailThickness = t
        group.RungSpacing = rs
        group.LinkedSketch = self.selected_sketch
            
        App.GlobalCableLadderObserver.trigger_rebuild_manually(group, force_now=True)

    def generate_fitting(self, f_type, l, w, d, t, attach_angle, rs):
        doc = App.ActiveDocument
        if doc is None:
            doc = App.newDocument()
            
        doc.openTransaction(f"Create {f_type}")
        
        if "STRAIGHT" in f_type: folder_name = "Straight_Ladders"
        elif "ELBOW" in f_type: folder_name = "Elbows"
        elif "TEE" in f_type: folder_name = "Tees"
        elif "CROSS" in f_type: folder_name = "Crosses"
        else: folder_name = "Other_Fittings"
        
        progress = QtWidgets.QProgressDialog(f"Generating {f_type}...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Generating 3D Models")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            shapes = self.calculate_manual_shape(f_type, l, w, d, t, attach_angle, rs)
            if shapes:
                # Group Manual objects neatly
                parent_group = doc.getObject("Manual_Cable_Ladder_System")
                if not parent_group:
                    parent_group = doc.addObject("App::DocumentObjectGroup", "Manual_Cable_Ladder_System")
                    
                sub_group = None
                for child in parent_group.Group:
                    if child.Name == folder_name or child.Label == folder_name:
                        sub_group = child
                        break
                if not sub_group:
                    sub_group = doc.addObject("App::DocumentObjectGroup", folder_name)
                    parent_group.addObject(sub_group)

                obj = doc.addObject("Part::Feature", f_type.replace(" ", "_"))
                obj.Shape = shapes[0].removeSplitter()
                if hasattr(obj, "ViewObject"):
                    obj.ViewObject.ShapeColor = (0.85, 0.85, 0.86) 
                    obj.ViewObject.LineColor = (0.2, 0.2, 0.2)
                
                sub_group.addObject(obj)
            
            doc.recompute()
            FreeCADGui.SendMsgToActiveView("ViewFit")
        finally:
            progress.close()
            doc.commitTransaction()

    def accept(self):
        w = float(self.width_cb.currentText().replace(" MM", ""))
        d = float(self.depth_cb.currentText().replace(" MM", ""))
        t = self.thick_input.value()
        rs = float(self.spacing_cb.currentText().replace(" MM", ""))
        
        if self.preview_manager:
            if hasattr(self.preview_manager, 'clear'): self.preview_manager.clear()
            
        FreeCADGui.Control.closeDialog()
        
        if self.selected_sketch:
            self.setup_smart_folder(w, d, t, rs)
        else:
            f_type = self.type_cb.currentText()
            l = self.custom_length.value()
            attach_angle = float(self.angle_cb.currentText())
            self.generate_fitting(f_type, l, w, d, t, attach_angle, rs)

    def reject(self):
        if self.preview_manager:
            if hasattr(self.preview_manager, 'clear'): self.preview_manager.clear()
        FreeCADGui.Control.closeDialog()


# Command Registration
class CreateCableLadderFittings:
    def GetResources(self):
        icon_path = ComfacUtils.get_icon_path('CableLadder.svg') if ComfacUtils else ""
        return {
            'Pixmap': icon_path, 
            'MenuText': "Generate Cable Ladder System", 
            'ToolTip': "Auto-route Cable Ladders from a Sketch, or Auto-Snap manually"
        }
        
    def Activated(self):
        sel_ex = FreeCADGui.Selection.getSelectionEx()
        base_placement = None
        snap_offset = App.Vector(0, 0, 0)
        snap_rotation = App.Rotation()
        selected_sketch = None

        if sel_ex:
            obj_ex = sel_ex[0]
            obj = obj_ex.Object
            
            if hasattr(obj, "Geometry") and "Sketch" in type(obj).__name__:
                selected_sketch = obj
            else:
                if hasattr(obj, "Placement"):
                    base_placement = obj.Placement.copy()
                
                lbl = obj.Label.upper()
                
                if hasattr(obj, "Shape") and obj_ex.HasSubObjects:
                    picked_points = obj_ex.PickedPoints
                    if picked_points:
                        local_pt = obj.Placement.inverse().multVec(picked_points[0])
                        bbox = obj.Shape.BoundBox
                        
                        if "HORIZONTAL ELBOW" in lbl:
                            E = -bbox.XMin
                            d1 = (local_pt - App.Vector(-E, 300, 0)).Length
                            d2 = (local_pt - App.Vector(300, -E, 0)).Length
                            if d1 < d2:
                                snap_offset = App.Vector(-E, 300, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 180)
                            else:
                                snap_offset = App.Vector(300, -E, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), -90)
                                
                        elif "TEE" in lbl:
                            dist_x = bbox.XMax 
                            dist_y = bbox.YMin 
                            d1 = (local_pt - App.Vector(dist_x, 0, 0)).Length
                            d2 = (local_pt - App.Vector(-dist_x, 0, 0)).Length
                            d3 = (local_pt - App.Vector(0, dist_y, 0)).Length
                            
                            m = min(d1, d2, d3)
                            if m == d1:
                                snap_offset = App.Vector(dist_x, 0, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 0)
                            elif m == d2:
                                snap_offset = App.Vector(-dist_x, 0, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 180)
                            else:
                                snap_offset = App.Vector(0, dist_y, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), -90)
                                
                        elif "CROSS" in lbl:
                            dist_x = bbox.XMax
                            dist_y = bbox.YMax
                            d1 = (local_pt - App.Vector(dist_x, 0, 0)).Length
                            d2 = (local_pt - App.Vector(-dist_x, 0, 0)).Length
                            d3 = (local_pt - App.Vector(0, dist_y, 0)).Length
                            d4 = (local_pt - App.Vector(0, -dist_y, 0)).Length
                            
                            m = min(d1, d2, d3, d4)
                            if m == d1:
                                snap_offset = App.Vector(dist_x, 0, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 0)
                            elif m == d2:
                                snap_offset = App.Vector(-dist_x, 0, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 180)
                            elif m == d3:
                                snap_offset = App.Vector(0, dist_y, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 90)
                            else:
                                snap_offset = App.Vector(0, -dist_y, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), -90)
                                
                        elif "VERTICAL" in lbl:
                            E = -bbox.XMin
                            w_val = bbox.YMax 
                            d1 = (local_pt - App.Vector(-E, w_val/2, 0)).Length
                            d2 = (local_pt - App.Vector(300, w_val/2, bbox.ZMin)).Length
                            
                            if d1 < d2:
                                snap_offset = App.Vector(-E, w_val/2, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 180) 
                            else:
                                snap_offset = App.Vector(300, w_val/2, bbox.ZMin)
                                snap_rotation = App.Rotation(App.Vector(0,1,0), -90)

                        elif "STRAIGHT" in lbl:
                            l_val = bbox.XMax
                            if local_pt.x > l_val / 2.0:
                                snap_offset = App.Vector(l_val, 0, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 0)
                            else:
                                snap_offset = App.Vector(0, 0, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 180)
                                
                        else:
                            if local_pt.x > 0:
                                snap_offset = App.Vector(bbox.XMax, 0, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 0)
                            else:
                                snap_offset = App.Vector(bbox.XMin, 0, 0)
                                snap_rotation = App.Rotation(App.Vector(0,0,1), 180)

        progress = None
        if selected_sketch:
            progress = QtWidgets.QProgressDialog("Launching Cable Ladder Tool...\nPlease wait while geometry is calculated.", None, 0, 0)
            progress.setWindowTitle("Loading")
            progress.setWindowModality(QtCore.Qt.ApplicationModal)
            progress.setMinimumDuration(0)
            progress.show()
            QtWidgets.QApplication.processEvents()

        try:
            panel = CableLadderFittingsTaskPanel(selected_sketch, base_placement, snap_offset, snap_rotation)
            FreeCADGui.Control.showDialog(panel)
        finally:
            if progress:
                progress.close()

try:
    FreeCADGui.addCommand('CreateCableLadderFittings', CreateCableLadderFittings())
except Exception as e:
    App.Console.PrintError(f"Failed to load command: {str(e)}\n")