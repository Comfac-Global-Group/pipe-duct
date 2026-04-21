import FreeCAD as App
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui
import os
import json

try:
    import ComfacUtils
except ImportError:
    ComfacUtils = None

# ==========================================
# GLOBAL PIPE DATA (Accessible by Observers)
# ==========================================
PIPE_DATA = {}
try:
    with open(os.path.join(os.path.dirname(__file__), "..", "data", "PipeData.json"), 'r') as f:
        PIPE_DATA = json.load(f)
    rename_mapping = {"Electrical Conduit - EMT": "EMT Pipes", "Electrical Conduit - IMC": "RSC Pipes & IMC Pipes", "Electrical Conduit -RIGID": "EMT Pipes - Compression"}
    for old_name in list(PIPE_DATA.keys()):
        if old_name in rename_mapping: PIPE_DATA[rename_mapping[old_name]] = PIPE_DATA.pop(old_name)
        elif old_name == "Electrical Conduit - RIGID": PIPE_DATA["EMT Pipes - Compression"] = PIPE_DATA.pop(old_name)
except Exception as e:
    FreeCAD.Console.PrintError(f"Failed to load pipe data: {e}\n")

PVC_ADAPTER_SIZES = {"4 inch": 114.3, "3 1/2 inch": 101.6, "3 inch": 88.9, "2 1/2 inch": 73.0, "2 inch": 60.3, "1 1/2 inch": 48.3, "1 1/4 inch": 42.2, "1 inch": 33.4, "3/4 inch": 26.7, "1/2 inch": 21.3}
LOCKNUT_SIZES = {
    "PVC": {"1/2 inch": 21.3, "3/4 inch": 26.7, "1 inch": 33.4, "1 1/4 inch": 42.2, "1 1/2 inch": 48.3, "2 inch": 60.3, "2 1/2 inch": 73.0, "3 inch": 88.9, "3 1/2 inch": 101.6, "4 inch": 114.3},
    "RSC Pipes & IMC Pipes": {"1/2 inch": 21.3, "3/4 inch": 26.7, "1 inch": 33.4, "1 1/4 inch": 42.2, "1 1/2 inch": 48.3, "2 inch": 60.3, "2 1/2 inch": 73.0, "3 inch": 88.9, "3 1/2 inch": 101.6, "4 inch": 114.3},
    "EMT Pipes": {"1/2 inch": 17.9, "3/4 inch": 23.4, "1 inch": 29.5, "1 1/4 inch": 38.4, "1 1/2 inch": 44.2, "2 inch": 55.8},
    "EMT Pipes - Compression": {"1/2 inch": 17.9, "3/4 inch": 23.4, "1 inch": 29.5, "1 1/4 inch": 38.4, "1 1/2 inch": 44.2, "2 inch": 55.8}
}
LONG_BEND_SIZES = {
    "Polyvinyl Chloride (PVC) Pipe Sizes - Schedule 40": {"1/2 inch": 21.3, "3/4 inch": 26.7, "1 inch": 33.4, "1 1/4 inch": 42.2, "1 1/2 inch": 48.3, "2 inch": 60.3, "2 1/2 inch": 73.0, "3 inch": 88.9, "3 1/2 inch": 101.6, "4 inch": 114.3},
    "Polyvinyl Chloride (PVC) Pipe Sizes - Schedule 80": {"1/2 inch": 21.3, "3/4 inch": 26.7, "1 inch": 33.4, "1 1/4 inch": 42.2, "1 1/2 inch": 48.3, "2 inch": 60.3, "2 1/2 inch": 73.0, "3 inch": 88.9, "3 1/2 inch": 101.6, "4 inch": 114.3},
    "RSC Pipes & IMC Pipes": {"1/2 inch": 21.3, "3/4 inch": 26.7, "1 inch": 33.4, "1 1/4 inch": 42.2, "1 1/2 inch": 48.3, "2 inch": 60.3, "2 1/2 inch": 73.0, "3 inch": 88.9, "3 1/2 inch": 101.6, "4 inch": 114.3}
}

def get_dimensions_from_catalog(f_type, mat, sz):
    if f_type == "PVC ADAPTER":
        D = PVC_ADAPTER_SIZES.get(sz, 60.3); t = max(2.0, D * 0.05)
        if mat in PIPE_DATA and sz in PIPE_DATA[mat]: t = PIPE_DATA[mat][sz][1]
        else:
            for m in PIPE_DATA:
                if "PVC" in m and sz in PIPE_DATA[m]: t = PIPE_DATA[m][sz][1]; break
        return [D, t]
    if f_type == "LOCKNUT":
        D = LOCKNUT_SIZES.get(mat, {}).get(sz, 60.3)
        return [D, 3.0]
    if f_type == "LONG BEND ELBOW":
        D = LONG_BEND_SIZES.get(mat, {}).get(sz, 60.3)
        t = max(2.0, D * 0.05)
        if mat in PIPE_DATA and sz in PIPE_DATA[mat]: t = PIPE_DATA[mat][sz][1]
        return [D, t]
    if mat in PIPE_DATA and sz in PIPE_DATA[mat]: return PIPE_DATA[mat][sz]
    return [50.0, 3.0]

# ==========================================
# GEOMETRY ENGINE (Headless Math & Shapes)
# ==========================================
class PipeGeometryEngine:
    
    """CSG Engine to build authentic pipes and socketed fittings."""
    
    def get_socket_depth(self, D): return max(10.0, D * 0.4)

    def make_straight_pipe(self, L, D, t):
        outer = Part.makeCylinder(D/2, L, App.Vector(0,0,0), App.Vector(0,0,1))
        inner = Part.makeCylinder(D/2 - t, L, App.Vector(0,0,0), App.Vector(0,0,1))
        return outer.cut(inner).removeSplitter()

    def make_socket_collar(self, D, t_f, SD, dir_vec=App.Vector(0,0,1)):
        outer = Part.makeCylinder(D/2 + t_f, SD, App.Vector(0,0,0), dir_vec)
        inner = Part.makeCylinder(D/2, SD, App.Vector(0,0,0), dir_vec)
        return outer.cut(inner)

    def make_hex_prism(self, R, L, pos):
        pts = []
        for i in range(6):
            angle = math.radians(i * 60)
            pts.append(App.Vector(R * math.cos(angle), R * math.sin(angle), 0))
        pts.append(pts[0])
        wire = Part.Wire([Part.makeLine(pts[i], pts[i+1]) for i in range(6)])
        face = Part.Face(wire)
        shape = face.extrude(App.Vector(0, 0, L))
        shape.Placement.Base = pos
        return shape

    def make_set_screw_coupler(self, D, t):
        SD = self.get_socket_depth(D)
        L_al = 2.0 
        total_L = L_al*2 + SD*2
        t_f = max(2.0, D * 0.08)
        R_out = D/2 + t_f
        
        body = Part.makeCylinder(R_out, total_L, App.Vector(0,0,-total_L/2), App.Vector(0,0,1))
        c_ring = Part.makeCylinder(R_out + 0.3, 0.5, App.Vector(0,0,-0.25), App.Vector(0,0,1))
        body = body.fuse(c_ring)
        
        rim_w = 1.5
        rim1 = Part.makeCylinder(R_out + 1.0, rim_w, App.Vector(0,0, total_L/2 - rim_w), App.Vector(0,0,1))
        rim2 = Part.makeCylinder(R_out + 1.0, rim_w, App.Vector(0,0, -total_L/2), App.Vector(0,0,1))
        
        ribs = []
        for i in range(4):
            angle = math.radians(i * 90)
            x = R_out * math.cos(angle)
            y = R_out * math.sin(angle)
            rib = Part.makeCylinder(0.6, total_L - 2*rim_w, App.Vector(x, y, -total_L/2 + rim_w), App.Vector(0,0,1))
            ribs.append(rib)
            
        boss_R = max(3.5, D * 0.12)
        boss_H = max(2.0, D * 0.06)
        screw_R = boss_R * 0.6
        exp_thread_H = 1.8
        head_R = boss_R * 0.95
        head_H = 1.5
        base_Y = R_out - 0.2
        
        def make_screw(z_pos):
            b = Part.makeCylinder(boss_R, boss_H, App.Vector(0, base_Y, z_pos), App.Vector(0,1,0))
            th = Part.makeCylinder(screw_R, exp_thread_H, App.Vector(0, base_Y + boss_H, z_pos), App.Vector(0,1,0))
            h_y = base_Y + boss_H + exp_thread_H
            h = Part.makeCylinder(head_R, head_H, App.Vector(0, h_y, z_pos), App.Vector(0,1,0))
            dome = Part.makeSphere(head_R, App.Vector(0, h_y + head_H - head_R*0.6, z_pos))
            h = h.fuse(dome)
            
            slot_w = max(1.0, head_R * 0.3)
            slot_d = head_H * 2.0
            slot_l = head_R * 2.2
            cut_y = h_y + head_H - slot_d * 0.4
            
            slot1 = Part.makeBox(slot_l, slot_d, slot_w)
            slot1.Placement.Base = App.Vector(-slot_l/2, cut_y, z_pos - slot_w/2)
            slot2 = Part.makeBox(slot_w, slot_d, slot_l)
            slot2.Placement.Base = App.Vector(-slot_w/2, cut_y, z_pos - slot_l/2)
            
            cross = slot1.fuse(slot2)
            return b.fuse([th, h]).cut(cross)
            
        screw1 = make_screw(SD/2)
        screw2 = make_screw(-SD/2)
        body = body.fuse([rim1, rim2] + ribs + [screw1, screw2])
        
        body_in = Part.makeCylinder(D/2 - t, total_L + 2, App.Vector(0,0,-total_L/2 - 1), App.Vector(0,0,1))
        s1 = Part.makeCylinder(D/2, SD, App.Vector(0,0,L_al), App.Vector(0,0,1))
        s2 = Part.makeCylinder(D/2, SD, App.Vector(0,0,-total_L/2), App.Vector(0,0,1))
        
        return body.cut(body_in).cut(s1).cut(s2).removeSplitter(), L_al + SD

    def make_compression_coupler(self, D, t):
        R_base = D/2 + max(2.5, D * 0.08)
        R_hex_center = R_base + max(3.5, D * 0.12)
        R_hex_end = R_hex_center + max(1.5, D * 0.05)
        
        center_hex_L = max(8.0, D*0.15)
        gap_L = max(5.0, D*0.12)
        end_hex_L = max(10.0, D*0.25)
        col_L = max(3.0, D*0.08)
        lip_L = 2.0
        
        total_L = center_hex_L + 2*gap_L + 2*end_hex_L + 2*col_L + 2*lip_L
        L_al = 2.0
        actual_SD = total_L/2 - L_al
        
        body = Part.makeCylinder(R_base, center_hex_L + 2*gap_L, App.Vector(0,0,-(center_hex_L/2 + gap_L)), App.Vector(0,0,1))
        center_hex = self.make_hex_prism(R_hex_center, center_hex_L, App.Vector(0,0,-center_hex_L/2))
        hex1 = self.make_hex_prism(R_hex_end, end_hex_L, App.Vector(0,0, center_hex_L/2 + gap_L))
        hex2 = self.make_hex_prism(R_hex_end, end_hex_L, App.Vector(0,0, -(center_hex_L/2 + gap_L + end_hex_L)))
        col1 = Part.makeCone(R_hex_end*0.88, R_base, col_L, App.Vector(0,0, center_hex_L/2 + gap_L + end_hex_L), App.Vector(0,0,1))
        col2 = Part.makeCone(R_base, R_hex_end*0.88, col_L, App.Vector(0,0, -(center_hex_L/2 + gap_L + end_hex_L + col_L)), App.Vector(0,0,1))
        lip1 = Part.makeCylinder(R_base, lip_L, App.Vector(0,0, center_hex_L/2 + gap_L + end_hex_L + col_L), App.Vector(0,0,1))
        lip2 = Part.makeCylinder(R_base, lip_L, App.Vector(0,0, -(center_hex_L/2 + gap_L + end_hex_L + col_L + lip_L)), App.Vector(0,0,1))
        
        body = body.fuse([center_hex, hex1, hex2, col1, col2, lip1, lip2])
        
        threads = []
        num_threads = int(gap_L / 1.5)
        for i in range(num_threads):
            z_pos = center_hex_L/2 + (i+1)*1.5 - 0.5
            threads.append(Part.makeTorus(R_base, 0.5, App.Vector(0,0,z_pos), App.Vector(0,0,1)))
            threads.append(Part.makeTorus(R_base, 0.5, App.Vector(0,0,-z_pos), App.Vector(0,0,1)))
            
        if threads: body = body.fuse(threads)
            
        body_in = Part.makeCylinder(D/2 - t, total_L + 2, App.Vector(0,0,-total_L/2 - 1), App.Vector(0,0,1))
        s1 = Part.makeCylinder(D/2, actual_SD, App.Vector(0,0,L_al), App.Vector(0,0,1))
        s2 = Part.makeCylinder(D/2, actual_SD, App.Vector(0,0,-total_L/2), App.Vector(0,0,1))
        
        return body.cut(body_in).cut(s1).cut(s2).removeSplitter(), L_al + actual_SD

    def make_rsc_coupler(self, D, t):
        SD = self.get_socket_depth(D)
        L_al = 2.0 
        total_L = L_al*2 + SD*2
        t_f = max(3.5, D * 0.15) 
        R_out = D/2 + t_f
        
        body = Part.makeCylinder(R_out, total_L, App.Vector(0,0,-total_L/2), App.Vector(0,0,1))
        body_in = Part.makeCylinder(D/2 - t, total_L + 2, App.Vector(0,0,-total_L/2 - 1), App.Vector(0,0,1))
        s1 = Part.makeCylinder(D/2, SD, App.Vector(0,0,L_al), App.Vector(0,0,1))
        s2 = Part.makeCylinder(D/2, SD, App.Vector(0,0,-total_L/2), App.Vector(0,0,1))
        body = body.cut(body_in).cut(s1).cut(s2)
        
        threads = []
        num_threads = int(SD / 2.0)
        for i in range(num_threads):
            z1 = L_al + i*2.0 + 1.0
            z2 = -total_L/2 + i*2.0 + 1.0
            threads.append(Part.makeTorus(D/2 + 0.3, 0.5, App.Vector(0,0,z1), App.Vector(0,0,1)))
            threads.append(Part.makeTorus(D/2 + 0.3, 0.5, App.Vector(0,0,z2), App.Vector(0,0,1)))
            
        if threads: body = body.cut(Part.makeCompound(threads))
            
        return body.removeSplitter(), L_al + SD

    def make_coupler(self, D, t, mat_type=None):
        if mat_type == "EMT Pipes": return self.make_set_screw_coupler(D, t)
        elif mat_type == "EMT Pipes - Compression": return self.make_compression_coupler(D, t)
        elif mat_type == "RSC Pipes & IMC Pipes": return self.make_rsc_coupler(D, t)
            
        SD = self.get_socket_depth(D)
        t_f = t + 1.0 
        L_al = 2.0 
        
        body_out = Part.makeCylinder(D/2 + t_f, L_al*2 + SD*2, App.Vector(0,0,-L_al-SD), App.Vector(0,0,1))
        body_in = Part.makeCylinder(D/2 - t, L_al*2 + SD*2 + 2, App.Vector(0,0,-L_al-SD-1), App.Vector(0,0,1))
        shell = body_out.cut(body_in)
        s1 = Part.makeCylinder(D/2, SD, App.Vector(0,0,L_al), App.Vector(0,0,1))
        s2 = Part.makeCylinder(D/2, SD, App.Vector(0,0,-L_al-SD), App.Vector(0,0,1))
        
        return shell.cut(s1).cut(s2).removeSplitter(), L_al + SD

    def make_end_cap(self, D, t):
        SD = self.get_socket_depth(D)
        t_f = t + 1.5
        L_al = 2.0
        
        cap = Part.makeCylinder(D/2 + t_f, L_al, App.Vector(0,0,0), App.Vector(0,0,1))
        collar = self.make_socket_collar(D, t_f, SD, App.Vector(0,0,1))
        collar.translate(App.Vector(0,0,L_al))
        
        return cap.fuse(collar).removeSplitter(), L_al + SD

    def make_pvc_adapter(self, D, t):
        SD = self.get_socket_depth(D)
        t_f = t + max(3.0, D * 0.08) 
        hex_t = max(5.0, D * 0.12)
        male_L = max(15.0, D * 0.3)
        
        socket = Part.makeCylinder(D/2 + t_f, SD, App.Vector(0,0,-SD), App.Vector(0,0,1))
        R_hex = D/2 + t_f + max(4.0, D*0.1)
        hex_nut = self.make_hex_prism(R_hex, hex_t, App.Vector(0,0,0))
        
        male_R = D/2
        male = Part.makeCylinder(male_R, male_L, App.Vector(0,0,hex_t), App.Vector(0,0,1))
        
        num_threads = max(4, int(male_L / 2.5))
        pitch = male_L / (num_threads + 1)
        threads = []
        dir_v = App.Vector(0,0,1)
        for j in range(num_threads):
            z_offset = hex_t + (j + 1) * pitch
            threads.append(Part.makeTorus(male_R, 0.6, App.Vector(0,0,z_offset), dir_v))
            
        body = socket.fuse([hex_nut, male] + threads)
        through_bore = Part.makeCylinder(D/2 - t, SD + hex_t + male_L + 2, App.Vector(0,0,-SD - 1), App.Vector(0,0,1))
        socket_bore = Part.makeCylinder(D/2, SD, App.Vector(0,0,-SD), App.Vector(0,0,1))
        
        return body.cut(through_bore).cut(socket_bore).removeSplitter(), SD + hex_t + male_L

    def make_trapezoid_tab(self, R_inner, R_outer, W_base, W_tip, thickness):
        p1 = App.Vector(R_inner, -W_base/2.0, 0); p2 = App.Vector(R_outer, -W_tip/2.0, 0)
        p3 = App.Vector(R_outer, W_tip/2.0, 0); p4 = App.Vector(R_inner, W_base/2.0, 0)
        return Part.Face(Part.makePolygon([p1, p2, p3, p4, p1])).extrude(App.Vector(0, 0, thickness))

    def add_threads(self, body, R_in, thickness, pos, dir_v):
        threads = []
        num_threads = max(3, int(thickness / 1.5))
        pitch = thickness / (num_threads + 1)
        for j in range(num_threads):
            threads.append(Part.makeTorus(R_in, 0.4, pos + dir_v * ((j + 1) * pitch), dir_v))
        if threads:
            t_comp = threads[0]
            for i in range(1, len(threads)): t_comp = t_comp.fuse(threads[i])
            body = body.fuse(t_comp)
        return body

    def make_pipe_locknut(self, mat_type, D):
        pos = App.Vector(0,0,0); dir_v = App.Vector(0,0,1)
        if mat_type == "PVC":
            thickness = 8.0
            R_in = D / 2.0; R_hex = R_in + max(6.0, D * 0.2)
            R_flange = R_hex * 1.25; flange_t = max(2.0, thickness * 0.35)
            
            body = Part.makeCylinder(R_flange, flange_t, pos, dir_v).fuse(self.make_hex_prism(R_hex, thickness - flange_t, pos + dir_v * flange_t))
            body = body.cut(Part.makeCylinder(R_in, thickness + 2.0, pos - dir_v, dir_v))
            return self.add_threads(body, R_in, thickness, pos, dir_v).removeSplitter()

        elif mat_type in ["RSC Pipes & IMC Pipes", "EMT Pipes"]:
            thickness = 3.0
            R_in = D / 2.0; R_valley = R_in + max(3.0, D * 0.08); R_out = R_in + max(6.0, D * 0.22)
            num_tabs = 8; W_base = max(4.0, D * 0.15); W_tip = max(3.0, D * 0.10)
            
            body = Part.makeCylinder(R_valley, thickness, pos, dir_v)
            for i in range(num_tabs):
                tab = self.make_trapezoid_tab(R_valley - 0.5, R_out, W_base, W_tip, thickness)
                tab.Placement = App.Placement(pos, App.Rotation(App.Vector(0,0,1), dir_v)).multiply(App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1), i * (360.0/num_tabs))))
                body = body.fuse(tab)
                
            body = body.cut(Part.makeCylinder(R_in, thickness + 2.0, pos - dir_v, dir_v))
            return self.add_threads(body, R_in, thickness, pos, dir_v).removeSplitter()
            
        elif mat_type in ["EMT COMPRESSION", "EMT Pipes - Compression"]:
            thickness = 5.0
            R_in = D / 2.0; R_valley = R_in + max(4.0, D * 0.12); R_out = R_in + max(8.0, D * 0.28)
            num_tabs = 6; W_base = max(6.0, D * 0.25); W_tip = max(4.0, D * 0.15)
            
            body = Part.makeCylinder(R_valley, thickness, pos, dir_v)
            for i in range(num_tabs):
                tab = self.make_trapezoid_tab(R_valley - 0.5, R_out, W_base, W_tip, thickness)
                tab.Placement = App.Placement(pos, App.Rotation(App.Vector(0,0,1), dir_v)).multiply(App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1), i * (360.0/num_tabs))))
                body = body.fuse(tab)
                
            body = body.cut(Part.makeCylinder(R_in, thickness + 2.0, pos - dir_v, dir_v))
            return self.add_threads(body, R_in, thickness, pos, dir_v).removeSplitter()
            
        return None

    def make_90_elbow(self, D, t):
        SD = self.get_socket_depth(D)
        t_f = t + 1.0; R = D/2 + 5.0; L_al = R 

        p1 = App.Vector(0,0,L_al); C = App.Vector(R, 0, L_al)
        face_out = Part.Face(Part.Wire(Part.makeCircle(D/2 + t_f, p1, App.Vector(0,0,1))))
        face_in = Part.Face(Part.Wire(Part.makeCircle(D/2 - t, p1, App.Vector(0,0,1))))
        body = face_out.revolve(C, App.Vector(0,-1,0), 90).cut(face_in.revolve(C, App.Vector(0,-1,0), 90))
        
        s1 = self.make_socket_collar(D, t_f, SD, App.Vector(0,0,1)); s1.translate(p1)
        ang_end = math.radians(90)
        s2 = self.make_socket_collar(D, t_f, SD, App.Vector(math.sin(ang_end), 0, -math.cos(ang_end)))
        s2.translate(C + App.Vector(0, 0, -R))
        
        return body.fuse([s1, s2]).removeSplitter(), L_al + SD

    def make_long_bend_elbow(self, D, t):
        SD = self.get_socket_depth(D)
        t_f = t + 1.0; R = D * 4.0; L_al = R 

        p1 = App.Vector(0,0,L_al); C = App.Vector(R, 0, L_al)
        face_out = Part.Face(Part.Wire(Part.makeCircle(D/2 + t_f, p1, App.Vector(0,0,1))))
        face_in = Part.Face(Part.Wire(Part.makeCircle(D/2 - t, p1, App.Vector(0,0,1))))
        body = face_out.revolve(C, App.Vector(0,-1,0), 90).cut(face_in.revolve(C, App.Vector(0,-1,0), 90))
        
        s1 = self.make_socket_collar(D, t_f, SD, App.Vector(0,0,1)); s1.translate(p1)
        ang_end = math.radians(90)
        s2 = self.make_socket_collar(D, t_f, SD, App.Vector(math.sin(ang_end), 0, -math.cos(ang_end)))
        s2.translate(C + App.Vector(0, 0, -R))
        
        return body.fuse([s1, s2]).removeSplitter(), L_al + SD

    def make_45_elbow(self, D, t):
        SD = self.get_socket_depth(D)
        t_f = t + 1.0; R = D/2 + 5.0; L_al = R * math.tan(math.radians(22.5))

        p1 = App.Vector(0,0,L_al); C = App.Vector(R, 0, L_al)
        face_out = Part.Face(Part.Wire(Part.makeCircle(D/2 + t_f, p1, App.Vector(0,0,1))))
        face_in = Part.Face(Part.Wire(Part.makeCircle(D/2 - t, p1, App.Vector(0,0,1))))
        body = face_out.revolve(C, App.Vector(0,-1,0), 45).cut(face_in.revolve(C, App.Vector(0,-1,0), 45))
        
        s1 = self.make_socket_collar(D, t_f, SD, App.Vector(0,0,1)); s1.translate(p1)
        ang_end = math.radians(45)
        s2 = self.make_socket_collar(D, t_f, SD, App.Vector(math.sin(ang_end), 0, -math.cos(ang_end)))
        s2.translate(C + App.Vector(-R * math.cos(ang_end), 0, -R * math.sin(ang_end)))
        
        return body.fuse([s1, s2]).removeSplitter(), L_al + SD

    def make_tee(self, D, t):
        SD = self.get_socket_depth(D)
        t_f = t + 1.0; L_al = D/2 + 4.0
        
        body = Part.makeCylinder(D/2 + t_f, L_al*2, App.Vector(0,0,-L_al), App.Vector(0,0,1)).fuse(Part.makeCylinder(D/2 + t_f, L_al, App.Vector(0,0,0), App.Vector(1,0,0)))
        shell = body.cut(Part.makeCylinder(D/2 - t, L_al*2 + 2, App.Vector(0,0,-L_al - 1), App.Vector(0,0,1)).fuse(Part.makeCylinder(D/2 - t, L_al + 1, App.Vector(0,0,0), App.Vector(1,0,0))))
        
        s1 = self.make_socket_collar(D, t_f, SD, App.Vector(0,0,1)); s1.translate(App.Vector(0,0,L_al))
        s2 = self.make_socket_collar(D, t_f, SD, App.Vector(0,0,-1)); s2.translate(App.Vector(0,0,-L_al))
        s3 = self.make_socket_collar(D, t_f, SD, App.Vector(1,0,0)); s3.translate(App.Vector(L_al,0,0))
        return shell.fuse([s1, s2]).removeSplitter(), L_al + SD

    def make_cross(self, D, t):
        SD = self.get_socket_depth(D)
        t_f = t + 1.0; L_al = D/2 + 4.0
        
        body = Part.makeCylinder(D/2 + t_f, L_al*2, App.Vector(0,0,-L_al), App.Vector(0,0,1)).fuse(Part.makeCylinder(D/2 + t_f, L_al*2, App.Vector(-L_al,0,0), App.Vector(1,0,0)))
        shell = body.cut(Part.makeCylinder(D/2 - t, L_al*2 + 2, App.Vector(0,0,-L_al - 1), App.Vector(0,0,1)).fuse(Part.makeCylinder(D/2 - t, L_al*2 + 2, App.Vector(-L_al - 1,0,0), App.Vector(1,0,0))))
        
        s1 = self.make_socket_collar(D, t_f, SD, App.Vector(0,0,1)); s1.translate(App.Vector(0,0,L_al))
        s2 = self.make_socket_collar(D, t_f, SD, App.Vector(0,0,-1)); s2.translate(App.Vector(0,0,-L_al))
        s3 = self.make_socket_collar(D, t_f, SD, App.Vector(1,0,0)); s3.translate(App.Vector(L_al,0,0))
        s4 = self.make_socket_collar(D, t_f, SD, App.Vector(-1,0,0)); s4.translate(App.Vector(-L_al,0,0))
        return shell.fuse([s1, s2, s3, s4]).removeSplitter(), L_al + SD

    def find_tee_vectors(self, vectors):
        for i, v1 in enumerate(vectors):
            for j, v2 in enumerate(vectors):
                if i != j and abs(v1.getAngle(v2) - math.pi) < 0.1: 
                    branch = [v for k, v in enumerate(vectors) if k not in (i, j)][0]
                    if abs(v1.getAngle(branch) - math.pi/2) < 0.1: return v1, v2, branch
        return None, None, None

    def find_cross_vectors(self, vectors):
        pairs = []; used = []
        for i in range(4):
            if i in used: continue
            for j in range(i+1, 4):
                if j in used: continue
                if abs(vectors[i].getAngle(vectors[j]) - math.pi) < 0.1:
                    pairs.append((vectors[i], vectors[j])); used.extend([i, j]); break
        if len(pairs) == 2 and abs(pairs[0][0].getAngle(pairs[1][0]) - math.pi/2) < 0.1:
            return pairs
        return None

    def get_placement(self, center, v_z, v_y):
        Z = v_z.normalize(); Y = v_y.normalize(); X = Y.cross(Z).normalize()
        if X.Length < 0.01:
            Y = App.Vector(0,1,0) if abs(Z.y) < 0.9 else App.Vector(1,0,0)
            X = Y.cross(Z).normalize()
        Y = Z.cross(X).normalize()
        
        m = App.Matrix()
        m.A11 = X.x; m.A12 = Y.x; m.A13 = Z.x; m.A14 = center.x
        m.A21 = X.y; m.A22 = Y.y; m.A23 = Z.y; m.A24 = center.y
        m.A31 = X.z; m.A32 = Y.z; m.A33 = Z.z; m.A34 = center.z
        return App.Placement(m)

    def calculate_system(self, sketches, D, t, mat_type=None):
        all_edges = []
        for sk in sketches: all_edges.extend([e for e in sk.Shape.Edges if e.Length > 0.001])
        if not all_edges: return None

        raw_lines = []
        for edge in all_edges:
            if hasattr(edge, "Curve") and 'Line' in str(type(edge.Curve).__name__):
                raw_lines.append((edge.Vertexes[0].Point, edge.Vertexes[-1].Point))

        vertices = {}
        for p1, p2 in raw_lines:
            k1 = (round(p1.x, 2), round(p1.y, 2), round(p1.z, 2))
            k2 = (round(p2.x, 2), round(p2.y, 2), round(p2.z, 2))
            if k1 not in vertices: vertices[k1] = []
            if k2 not in vertices: vertices[k2] = []
            vertices[k1].append(App.Vector(p2.x - p1.x, p2.y - p1.y, p2.z - p1.z).normalize())
            vertices[k2].append(App.Vector(p1.x - p2.x, p1.y - p2.y, p1.z - p2.z).normalize())

        comps = {"Pipes": [], "Elbows": [], "Tees": [], "Crosses": [], "Couplers": [], "Caps": []}
        vertex_allowances = {}; SD = self.get_socket_depth(D)
        
        for pt_key, vectors in vertices.items():
            pt = App.Vector(pt_key[0], pt_key[1], pt_key[2])
            degree = len(vectors)
            
            if degree > 4: raise ValueError(f"Too many pipes at one point. Found {degree}.")
            elif degree == 1:
                shape, L_al = self.make_end_cap(D, t)
                v_y = App.Vector(0,1,0) if abs(vectors[0].dot(App.Vector(0,1,0))) < 0.9 else App.Vector(1,0,0)
                shape.Placement = self.get_placement(pt, vectors[0], v_y)
                comps["Caps"].append(shape); vertex_allowances[pt_key] = L_al
            elif degree == 2:
                v1, v2 = vectors[0], vectors[1]
                angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, v1.dot(v2)))))
                
                if abs(angle_deg - 180.0) < 5.0: 
                    shape, L_al = self.make_coupler(D, t, mat_type)
                    v_y = App.Vector(0,1,0) if abs(v1.dot(App.Vector(0,1,0))) < 0.9 else App.Vector(1,0,0)
                    shape.Placement = self.get_placement(pt, v1, v_y)
                    comps["Couplers"].append(shape); vertex_allowances[pt_key] = L_al
                elif abs(angle_deg - 90.0) < 5.0: 
                    shape, L_al = self.make_90_elbow(D, t)
                    shape.Placement = self.get_placement(pt, v1, v1.cross(v2))
                    comps["Elbows"].append(shape); vertex_allowances[pt_key] = L_al
                elif abs(angle_deg - 45.0) < 5.0 or abs(angle_deg - 135.0) < 5.0: 
                    shape, L_al = self.make_45_elbow(D, t)
                    shape.Placement = self.get_placement(pt, v1, v1.cross(v2))
                    comps["Elbows"].append(shape); vertex_allowances[pt_key] = L_al
                else: 
                    # STRICT ENFORCEMENT: Only 90 and 45 degree bends allowed
                    raise ValueError(f"Invalid Elbow Angle ({angle_deg:.1f}°). The system strictly supports 90° and 45° elbows. Please adjust your sketch to match standard fittings.")

            elif degree == 3:
                v_m1, v_m2, v_b = self.find_tee_vectors(vectors)
                if not v_m1: raise ValueError("Invalid Tee Intersection!")
                shape, L_al = self.make_tee(D, t)
                shape.Placement = self.get_placement(pt, v_m1, v_m1.cross(v_b))
                comps["Tees"].append(shape); vertex_allowances[pt_key] = L_al
            elif degree == 4:
                pairs = self.find_cross_vectors(vectors)
                if not pairs: raise ValueError("Invalid Cross Intersection!")
                shape, L_al = self.make_cross(D, t)
                shape.Placement = self.get_placement(pt, pairs[0][0], pairs[0][0].cross(pairs[1][0]))
                comps["Crosses"].append(shape); vertex_allowances[pt_key] = L_al

        for p1, p2 in raw_lines:
            v_dir = (p2 - p1); total_len = v_dir.Length; v_dir.normalize()
            k1 = (round(p1.x, 2), round(p1.y, 2), round(p1.z, 2))
            k2 = (round(p2.x, 2), round(p2.y, 2), round(p2.z, 2))
            a1 = vertex_allowances.get(k1, 0); a2 = vertex_allowances.get(k2, 0)
            
            if total_len < (a1 + a2): raise ValueError(f"Sketch segment too short! Min required: {a1+a2:.1f} mm.")
            
            pipe_start = p1 + v_dir * (a1 - SD); pipe_end = p2 - v_dir * (a2 - SD)
            actual_L = (pipe_end - pipe_start).Length
            
            if actual_L > 0.1:
                shape = self.make_straight_pipe(actual_L, D, t)
                v_y = App.Vector(0,1,0) if abs(v_dir.dot(App.Vector(0,1,0))) < 0.9 else App.Vector(1,0,0)
                shape.Placement = self.get_placement(pipe_start, v_dir, v_y)
                comps["Pipes"].append(shape)

        return comps


# ==========================================
# LIVE BACKGROUND OBSERVER (PIPES)
# ==========================================
class PipeLiveObserver:
    def __init__(self):
        self.pending_rebuilds = set(); self.pending_deferred = set() 
        self.timer = QtCore.QTimer(); self.timer.setSingleShot(True); self.timer.timeout.connect(self.process_rebuilds)
        self.edit_check_timer = QtCore.QTimer(); self.edit_check_timer.setInterval(1000); self.edit_check_timer.timeout.connect(self.check_deferred_rebuilds)
        self.is_generating = False; self.last_error = ""

    def trigger_rebuild_manually(self, group):
        self.pending_rebuilds.add(group); self.process_rebuilds()

    def slotChangedObject(self, obj, prop):
        if self.is_generating: return

        needs_rebuild = False; is_editing = False
        
        if obj.isDerivedFrom("Sketcher::SketchObject") and prop in ["Shape", "Placement"]:
            try:
                if FreeCADGui.ActiveDocument:
                    in_edit = FreeCADGui.ActiveDocument.getInEdit()
                    if in_edit and in_edit.Object == obj: is_editing = True
            except Exception: pass

            if obj.Document:
                for doc_obj in obj.Document.Objects:
                    if doc_obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(doc_obj, "LinkedSketches"):
                        if obj in doc_obj.LinkedSketches:
                            if is_editing:
                                self.pending_deferred.add(doc_obj)
                                if not self.edit_check_timer.isActive(): self.edit_check_timer.start()
                            else:
                                self.pending_rebuilds.add(doc_obj); needs_rebuild = True

        if obj.isDerivedFrom("App::DocumentObjectGroup") and hasattr(obj, "LinkedSketches"):
            if prop in ["PipeOuterDiameter", "PipeThickness", "PipeMaterial", "NominalSize"]:
                
                mat = getattr(obj, "PipeMaterial", "")
                sz = getattr(obj, "NominalSize", "")
                
                # Handle auto dropdown cascade for the observer
                if prop == "PipeMaterial" and mat in PIPE_DATA:
                    new_sizes = list(PIPE_DATA[mat].keys())
                    if new_sizes:
                        obj.NominalSize = new_sizes
                        if sz not in new_sizes: sz = new_sizes[0]
                        obj.NominalSize = sz
                
                if prop in ["PipeMaterial", "NominalSize"]:
                    dims = get_dimensions_from_catalog("STRAIGHT PIPE", mat, sz)
                    obj.PipeOuterDiameter = dims[0]
                    obj.PipeThickness = dims[1]

                self.pending_rebuilds.add(obj); needs_rebuild = True
                
        if needs_rebuild: self.timer.start(500)

    def check_deferred_rebuilds(self):
        to_process = set(); active_edit_obj = None
        try:
            if FreeCADGui.ActiveDocument:
                in_edit = FreeCADGui.ActiveDocument.getInEdit()
                if in_edit: active_edit_obj = in_edit.Object
        except Exception: pass

        for group in list(self.pending_deferred):
            is_group_editing = False
            sketches = getattr(group, "LinkedSketches", [])
            if active_edit_obj and active_edit_obj in sketches: is_group_editing = True
            if not is_group_editing: to_process.add(group)

        for group in to_process:
            self.pending_deferred.remove(group); self.pending_rebuilds.add(group)

        if self.pending_rebuilds: self.timer.start(200)
        if not self.pending_deferred: self.edit_check_timer.stop()

    def process_rebuilds(self):
        if not self.pending_rebuilds: return
        self.is_generating = True
        
        progress = QtWidgets.QProgressDialog("Generating Pipe Geometry...", None, 0, 0, None)
        progress.setWindowTitle("Please Wait"); progress.setWindowModality(QtCore.Qt.WindowModal); progress.show()
        QtCore.QCoreApplication.processEvents() 
        
        try:
            for group in list(self.pending_rebuilds):
                if group.Document: 
                    self.rebuild_folder(group)
                    QtCore.QCoreApplication.processEvents()
        finally:
            self.pending_rebuilds.clear(); self.is_generating = False; progress.close() 

    def rebuild_folder(self, group):
        doc = group.Document
        sketches = getattr(group, "LinkedSketches", [])
        if not sketches: return
        
        D_prop = getattr(group, "PipeOuterDiameter", 50.0); t_prop = getattr(group, "PipeThickness", 3.0)
        mat_prop = getattr(group, "PipeMaterial", "")
        
        D = D_prop.Value if hasattr(D_prop, 'Value') else float(D_prop)
        t = t_prop.Value if hasattr(t_prop, 'Value') else float(t_prop)
        mat_type = mat_prop.Value if hasattr(mat_prop, 'Value') else str(mat_prop)
        
        if "PVC" in mat_type: color = (0.12, 0.56, 1.0) 
        elif "Copper" in mat_type: color = (0.72, 0.45, 0.20)  
        elif "Stainless" in mat_type: color = (0.75, 0.75, 0.8)
        elif "Conduit" in mat_type or "EMT" in mat_type or "RSC" in mat_type: color = (0.88, 0.90, 0.92)    
        else: color = (0.25, 0.25, 0.25)
            
        engine = PipeGeometryEngine()
        
        def gather_items(grp):
            items = []
            for child in grp.Group:
                if child not in sketches:
                    items.append(child)
                    if child.isDerivedFrom("App::DocumentObjectGroup"): items.extend(gather_items(child))
            return items

        try:
            components = engine.calculate_system(sketches, D, t, mat_type)
            self.last_error = "" 
        except ValueError as ve:
            error_msg = str(ve)
            for item in reversed(gather_items(group)): doc.removeObject(item.Name)
            doc.recompute()
            if self.last_error != error_msg:
                self.last_error = error_msg
                App.Console.PrintError(f"\n[PIPE ROUTING ERROR] {error_msg}\n")
                QtWidgets.QMessageBox.critical(None, "Routing Error", error_msg)
            return

        for item in reversed(gather_items(group)): doc.removeObject(item.Name)

        def get_or_create_subgroup(parent_group, name):
            for obj in parent_group.Group:
                if obj.Name == name or obj.Label == name: return obj
            sub = doc.addObject("App::DocumentObjectGroup", name); parent_group.addObject(sub)
            return sub

        if components:
            for folder_name, items in components.items():
                if not items: continue 
                target_folder = get_or_create_subgroup(group, folder_name)
                base_name = folder_name[:-1] if folder_name.endswith('s') else folder_name
                for i, s in enumerate(items):
                    obj = doc.addObject("Part::Feature", f"{base_name}_{i+1}")
                    obj.Shape = s
                    if hasattr(obj, "ViewObject") and obj.ViewObject: obj.ViewObject.ShapeColor = color
                    target_folder.addObject(obj)
        doc.recompute()

if not hasattr(App, "GlobalPipeObserver"):
    App.GlobalPipeObserver = PipeLiveObserver()
    App.addDocumentObserver(App.GlobalPipeObserver)


# ==========================================
# UI TASK PANEL
# ==========================================
class PipeTaskPanel:
    def __init__(self, sketches, target_placement=None, detected_D=None, detected_t=None, detected_color=None):
        self.sketches = sketches 
        self.target_placement = target_placement
        self.detected_D = detected_D
        self.detected_t = detected_t
        self.detected_color = detected_color
        self.form = QtWidgets.QWidget(); self.layout = QtWidgets.QFormLayout(self.form)
        self.doc = App.ActiveDocument; self.last_error = ""
        
        self.preview = None
        if ComfacUtils and hasattr(ComfacUtils, 'PreviewManager'): self.preview = ComfacUtils.PreviewManager(self.doc, "Pipe_Preview")
        self.fittings = ["STRAIGHT PIPE", "90 DEG ELBOW", "45 DEG ELBOW", "LONG BEND ELBOW", "TEE", "CROSS", "COUPLER", "END CAP", "PVC ADAPTER", "LOCKNUT"]

        self.is_auto_mode = (self.detected_D is not None and not self.sketches)
        self.auto_material = "Unknown Material"

        if self.is_auto_mode:
            best_match = None; min_diff = 999
            for mat, sizes in PIPE_DATA.items():
                for sz, dims in sizes.items():
                    diff = abs(dims[0] - self.detected_D) + abs(dims[1] - self.detected_t)
                    if diff < 1.5 and diff < min_diff: min_diff = diff; best_match = mat
            if best_match: self.auto_material = best_match

        if self.sketches:
            if len(self.sketches) > 1: self.mode_label = QtWidgets.QLabel("<b>Multi-Sketch Live Mode Active</b><br>Will merge lines and generate fittings globally.")
            else: self.mode_label = QtWidgets.QLabel("<b>Live Folder Mode Active</b><br>Will generate dynamic pipes based on sketch.")
            self.layout.addRow(self.mode_label)
        elif self.is_auto_mode:
            self.mode_label = QtWidgets.QLabel(f"<b>Auto adoption of Pipe size</b><br>Detected OD: {self.detected_D:.1f} mm | Thickness: {self.detected_t:.1f} mm<br>Detected Material: <b>{self.auto_material}</b>")
            self.layout.addRow(self.mode_label)
        else:
            self.mode_label = QtWidgets.QLabel("<b>Manual Mode</b><br>Generate discrete pipe parts.")
            self.layout.addRow(self.mode_label)

        self.type_cb = QtWidgets.QComboBox(); self.type_cb.addItems(self.fittings)
        if self.sketches: self.type_cb.setEnabled(False)

        self.material_cb = QtWidgets.QComboBox(); self.material_cb.addItems(list(PIPE_DATA.keys()))
        self.size_cb = QtWidgets.QComboBox()

        self.len_input = QtWidgets.QDoubleSpinBox(); self.len_input.setRange(10.0, 10000.0)
        self.len_input.setValue(1000.0); self.len_input.setSuffix(" mm")
        if self.sketches: self.len_input.setEnabled(False)
        
        self.rot_input = QtWidgets.QDoubleSpinBox()
        self.rot_input.setRange(0.0, 360.0)
        self.rot_input.setSingleStep(90.0)
        self.rot_input.setValue(0.0)
        self.rot_input.setSuffix(" °")
        if self.sketches: self.rot_input.setEnabled(False)

        part_label = "Fittings to Attach:" if self.is_auto_mode else "Manual Part:"
        self.layout.addRow(part_label, self.type_cb)
        self.layout.addRow("Straight Length:", self.len_input)
        self.layout.addRow("Rotation Angle:", self.rot_input)
        self.layout.addRow("Materials:", self.material_cb)
        self.layout.addRow("Nominal Size:", self.size_cb)

        if self.is_auto_mode:
            if self.auto_material != "Unknown Material":
                idx = self.material_cb.findText(self.auto_material)
                if idx >= 0: self.material_cb.setCurrentIndex(idx)

            for cb in [self.size_cb, self.material_cb]:
                lbl = self.layout.labelForField(cb)
                if lbl: lbl.setVisible(False)
                cb.setVisible(False)

        self.update_ui(); self.trigger_preview()

        self.type_cb.currentIndexChanged.connect(self.update_ui)
        self.type_cb.currentIndexChanged.connect(self.trigger_preview)
        self.len_input.valueChanged.connect(self.trigger_preview)
        self.rot_input.valueChanged.connect(self.trigger_preview)
        self.material_cb.currentTextChanged.connect(self.update_ui) 
        self.material_cb.currentTextChanged.connect(self.update_size_dropdown)
        self.size_cb.currentTextChanged.connect(self.trigger_preview)

    def update_size_dropdown(self, trigger_preview=True):
        f_type = self.type_cb.currentText()
        if f_type == "PVC ADAPTER": return 

        self.size_cb.blockSignals(True); self.size_cb.clear()
        mat = self.material_cb.currentText()

        if f_type == "LOCKNUT":
            if mat in LOCKNUT_SIZES: self.size_cb.addItems(list(LOCKNUT_SIZES[mat].keys()))
        elif f_type == "LONG BEND ELBOW":
            if mat in LONG_BEND_SIZES: self.size_cb.addItems(list(LONG_BEND_SIZES[mat].keys()))
        else:
            if mat in PIPE_DATA: self.size_cb.addItems(list(PIPE_DATA[mat].keys()))

        self.size_cb.blockSignals(False)
        if trigger_preview and hasattr(self, 'len_input'): self.trigger_preview()

    def update_ui(self):
        f_type = self.type_cb.currentText(); mat = self.material_cb.currentText()
        is_straight = (f_type == "STRAIGHT PIPE"); is_pvc_adapter = (f_type == "PVC ADAPTER")
        is_locknut = (f_type == "LOCKNUT"); is_long_bend = (f_type == "LONG BEND ELBOW")
        
        prev_mat = self.material_cb.currentText()
        self.material_cb.blockSignals(True); self.material_cb.clear()
        if is_locknut: self.material_cb.addItems(list(LOCKNUT_SIZES.keys()))
        elif is_long_bend: self.material_cb.addItems(list(LONG_BEND_SIZES.keys()))
        else: self.material_cb.addItems(list(PIPE_DATA.keys()))
            
        idx = self.material_cb.findText(prev_mat)
        if idx >= 0: self.material_cb.setCurrentIndex(idx)
        self.material_cb.blockSignals(False)

        if not self.sketches:
            self.layout.labelForField(self.len_input).setVisible(is_straight)
            self.len_input.setVisible(is_straight); self.len_input.setEnabled(is_straight)

            lbl_r = self.layout.labelForField(self.rot_input)
            if lbl_r: lbl_r.setVisible(not is_straight)
            self.rot_input.setVisible(not is_straight)

            if hasattr(self, 'is_auto_mode') and self.is_auto_mode:
                lbl_m = self.layout.labelForField(self.material_cb)
                if lbl_m: lbl_m.setVisible(False)
                self.material_cb.setVisible(False)
                
                lbl_s = self.layout.labelForField(self.size_cb)
                if lbl_s: lbl_s.setVisible(False)
                self.size_cb.setVisible(False)
            else:
                lbl_m = self.layout.labelForField(self.material_cb)
                if lbl_m: lbl_m.setVisible(not is_pvc_adapter)
                self.material_cb.setVisible(not is_pvc_adapter)
                
                lbl_s = self.layout.labelForField(self.size_cb)
                if lbl_s: lbl_s.setVisible(True)
                self.size_cb.setVisible(True)

        self.size_cb.blockSignals(True); current_sz = self.size_cb.currentText(); self.size_cb.clear()
        if is_pvc_adapter: self.size_cb.addItems(list(PVC_ADAPTER_SIZES.keys()))
        elif is_locknut and mat in LOCKNUT_SIZES: self.size_cb.addItems(list(LOCKNUT_SIZES[mat].keys()))
        elif is_long_bend and mat in LONG_BEND_SIZES: self.size_cb.addItems(list(LONG_BEND_SIZES[mat].keys()))
        elif mat in PIPE_DATA: self.size_cb.addItems(list(PIPE_DATA[mat].keys()))
                
        idx = self.size_cb.findText(current_sz)
        if idx >= 0: self.size_cb.setCurrentIndex(idx)
        self.size_cb.blockSignals(False)

    def get_pipe_dimensions(self):
        f_type = self.type_cb.currentText(); sz = self.size_cb.currentText(); mat = self.material_cb.currentText()
        
        if self.detected_D and not self.sketches: return [self.detected_D, self.detected_t if f_type != "LOCKNUT" else 3.0]
            
        return get_dimensions_from_catalog(f_type, mat, sz) 

    def get_material_color(self):
        if self.is_auto_mode and getattr(self, 'detected_color', None) is not None: return self.detected_color
        
        f_type = self.type_cb.currentText(); mat = self.material_cb.currentText()
        if f_type == "PVC ADAPTER" or "PVC" in mat: return (0.12, 0.56, 1.0) 
        if f_type == "LOCKNUT":
            if mat == "PVC": return (1.0, 0.4, 0.0) 
            elif mat in ["RSC Pipes & IMC Pipes", "EMT Pipes"]: return (0.88, 0.90, 0.92) 
            elif mat == "EMT Pipes - Compression": return (0.65, 0.67, 0.70) 
        if "Copper" in mat: return (0.72, 0.45, 0.20)  
        elif "Stainless" in mat: return (0.75, 0.75, 0.8)
        elif "Conduit" in mat or "EMT" in mat or "RSC" in mat: return (0.88, 0.90, 0.92)    
        else: return (0.25, 0.25, 0.25)                  

    def get_manual_shape(self, D, t):
        f_type = self.type_cb.currentText(); mat = self.material_cb.currentText(); engine = PipeGeometryEngine()
        s = None; needs_alignment = False; L_al = 0.0

        if f_type == "STRAIGHT PIPE": s = engine.make_straight_pipe(self.len_input.value(), D, t)
        elif f_type == "90 DEG ELBOW": s, _ = engine.make_90_elbow(D, t); L_al = D/2 + 5.0; needs_alignment = True
        elif f_type == "45 DEG ELBOW": s, _ = engine.make_45_elbow(D, t); L_al = (D/2 + 5.0) * math.tan(math.radians(22.5)); needs_alignment = True
        elif f_type == "LONG BEND ELBOW": s, _ = engine.make_long_bend_elbow(D, t); L_al = D * 4.0; needs_alignment = True
        elif f_type == "TEE": s, _ = engine.make_tee(D, t); L_al = D/2 + 4.0; needs_alignment = True
        elif f_type == "CROSS": s, _ = engine.make_cross(D, t); L_al = D/2 + 4.0; needs_alignment = True
        elif f_type == "COUPLER": s, _ = engine.make_coupler(D, t, mat); L_al = 2.0; needs_alignment = True
        elif f_type == "END CAP": s, _ = engine.make_end_cap(D, t); L_al = 2.0; needs_alignment = True
        elif f_type == "PVC ADAPTER": s, _ = engine.make_pvc_adapter(D, t)
        elif f_type == "LOCKNUT": s = engine.make_pipe_locknut(mat, D)

        if s and needs_alignment and not self.sketches:
            mat_rot = App.Rotation(App.Vector(1,0,0), 180).Matrix
            mat_trans = App.Matrix(); mat_trans.move(App.Vector(0,0,L_al))
            s = s.transformShape(mat_trans.multiply(mat_rot))

        return s

    def trigger_preview(self):
        if not self.preview: return
        D, t = self.get_pipe_dimensions(); color = self.get_material_color(); mat = self.material_cb.currentText()
        if t >= D/2.0: self.preview.clear(); return

        all_shapes = []
        try:
            if self.sketches:
                components = PipeGeometryEngine().calculate_system(self.sketches, D, t, mat)
                if components:
                    for k, items in components.items(): all_shapes.extend(items)
                self.last_error = ""
            else:
                s = self.get_manual_shape(D, t)
                if s:
                    if self.target_placement: 
                        base_place = self.target_placement
                        rot_angle = self.rot_input.value()
                        local_rot = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1), rot_angle))
                        final_plac = base_place.multiply(local_rot)
                        s = s.transformShape(final_plac.Matrix)
                    all_shapes.append(s)

            if all_shapes: self.preview.update(Part.makeCompound(all_shapes), color=color)
            else: self.preview.clear()
        except ValueError as e:
            if self.preview: self.preview.clear()
            if getattr(self, 'last_error', None) != str(e):
                self.last_error = str(e); QtWidgets.QMessageBox.warning(self.form, "Preview Error", str(e))
        except Exception: pass

    def setup_smart_folder(self, D, t, color, mat_name, all_mats, all_sizes):
        doc = App.ActiveDocument
        folder_name = f"{mat_name}_System"
        group = doc.getObject(folder_name)
        if not group: group = doc.addObject("App::DocumentObjectGroup", folder_name)
            
        if not hasattr(group, "PipeMaterial"): group.addProperty("App::PropertyEnumeration", "PipeMaterial", "Live Parameters", "Pipe Material")
        group.PipeMaterial = all_mats
        group.PipeMaterial = self.material_cb.currentText()

        if not hasattr(group, "NominalSize"): group.addProperty("App::PropertyEnumeration", "NominalSize", "Live Parameters", "Nominal Pipe Size")
        group.NominalSize = all_sizes
        group.NominalSize = self.size_cb.currentText()

        if not hasattr(group, "PipeOuterDiameter"): group.addProperty("App::PropertyLength", "PipeOuterDiameter", "Live Parameters", "Pipe OD")
        if not hasattr(group, "PipeThickness"): group.addProperty("App::PropertyLength", "PipeThickness", "Live Parameters", "Wall Thickness")
        
        group.setEditorMode("PipeOuterDiameter", 1)
        group.setEditorMode("PipeThickness", 1)

        if not hasattr(group, "LinkedSketches"): group.addProperty("App::PropertyLinkListGlobal", "LinkedSketches", "System Core", "Linked Sketches")
            
        group.PipeOuterDiameter = D; group.PipeThickness = t
        group.LinkedSketches = self.sketches
        App.GlobalPipeObserver.trigger_rebuild_manually(group)

    def accept(self):
        D, t = self.get_pipe_dimensions(); color = self.get_material_color()
        if self.type_cb.currentText() == "PVC ADAPTER": mat_name = "PVC"
        elif self.type_cb.currentText() == "LOCKNUT": mat_name = self.material_cb.currentText().replace(" ", "_").replace("&", "and")
        else: mat_name = self.material_cb.currentText().replace(" ", "_").replace("-", "_")

        if t >= D/2.0: QtWidgets.QMessageBox.critical(None, "Error", "Wall thickness is mathematically impossible."); return

        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()
        
        all_mats = [self.material_cb.itemText(i) for i in range(self.material_cb.count())]
        all_sizes = [self.size_cb.itemText(i) for i in range(self.size_cb.count())]
        
        if self.sketches:
            progress = QtWidgets.QProgressDialog("Initializing Pipe System...", None, 0, 0, None)
            progress.setWindowTitle("Please Wait"); progress.setWindowModality(QtCore.Qt.WindowModal); progress.show()
            QtCore.QCoreApplication.processEvents()
            self.setup_smart_folder(D, t, color, mat_name, all_mats, all_sizes)
            progress.close() 
        else:
            doc = App.ActiveDocument
            doc.openTransaction("Generate Manual Pipe")
            try:
                main_group = doc.getObject(f"{mat_name}_System")
                if not main_group: main_group = doc.addObject("App::DocumentObjectGroup", f"{mat_name}_System")
                    
                shape = self.get_manual_shape(D, t)
                if shape:
                    f_type = self.type_cb.currentText()
                    
                    folder_map = {
                        "STRAIGHT PIPE": "Pipes", "90 DEG ELBOW": "Elbows", "45 DEG ELBOW": "Elbows", 
                        "LONG BEND ELBOW": "Elbows", "TEE": "Tees", "CROSS": "Crosses", 
                        "COUPLER": "Couplers", "END CAP": "Caps", "PVC ADAPTER": "Adapters", "LOCKNUT": "Locknuts"
                    }
                    folder_target = folder_map.get(f_type, "Fittings")
                    
                    grp = None
                    for obj_grp in main_group.Group:
                        if obj_grp.Label == folder_target or obj_grp.Name == folder_target:
                            grp = obj_grp
                            break
                    if not grp:
                        for obj_grp in main_group.Group:
                            if obj_grp.Label.lower() == folder_target.lower():
                                grp = obj_grp
                                grp.Label = folder_target 
                                break
                    if not grp:
                        grp = doc.addObject("App::DocumentObjectGroup", folder_target)
                        grp.Label = folder_target
                        main_group.addObject(grp)
                    
                    safe_name = f_type.title().replace(" ", "_")
                    if safe_name[0].isdigit():
                        safe_name = "Fitting_" + safe_name
                    obj = doc.addObject("Part::Feature", safe_name)
                    obj.Label = f_type.title()
                    
                    # Exact manual placement math you requested:
                    if self.target_placement: 
                        base_place = self.target_placement
                        rot_angle = self.rot_input.value()
                        local_rot = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1), rot_angle))
                        final_plac = base_place.multiply(local_rot)
                        
                        obj.Shape = shape.transformShape(final_plac.Matrix)
                    else:
                        obj.Shape = shape

                    if hasattr(obj, "ViewObject") and obj.ViewObject: 
                        obj.ViewObject.ShapeColor = color
                        obj.ViewObject.Visibility = True
                    grp.addObject(obj)

                doc.recompute(); FreeCADGui.SendMsgToActiveView("ViewFit")
            except Exception as e:
                doc.abortTransaction(); App.Console.PrintError(f"Pipe System Error: {e}\n")
            finally: doc.commitTransaction()

    def reject(self):
        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()


class CreatePipeLibraries:
    def GetResources(self):
        icon = ComfacUtils.get_icon_path('Pipe_Fittings.svg') if ComfacUtils else ""
        return {'Pixmap': icon, 'MenuText': "Pipe Libraries", 'ToolTip': "Generates pipes and socketed fittings based on standard sizes"}

    def Activated(self):
        doc = App.ActiveDocument
        if not doc: App.newDocument("Piping_Workspace")
            
        target_place = None; detected_D = None; detected_t = None; detected_color = None
        sel = FreeCADGui.Selection.getSelectionEx()
        
        if sel and sel[0].HasSubObjects:
            try:
                obj = sel[0].Object; sub = sel[0].SubObjects[0]
                
                if hasattr(obj, "ViewObject") and obj.ViewObject and hasattr(obj.ViewObject, "ShapeColor"):
                    sc = obj.ViewObject.ShapeColor
                    if hasattr(sc, 'r'): detected_color = (sc.r, sc.g, sc.b)
                    elif isinstance(sc, (tuple, list)) and len(sc) >= 3: detected_color = (sc[0], sc[1], sc[2])

                obj_shape = sel[0].Object.Shape
                obj_center_local = obj_shape.BoundBox.Center if hasattr(obj_shape, "BoundBox") else App.Vector(0,0,0)
                
                center_local = None; normal_local = None; radii = []

                if isinstance(sub, Part.Edge) and hasattr(sub.Curve, "Center"):
                    center_local = sub.Curve.Center; normal_local = sub.Curve.Axis.normalize()
                    for e in sel[0].SubObjects:
                        if hasattr(e.Curve, "Radius"): radii.append(e.Curve.Radius)
                        
                    if (center_local - obj_center_local).dot(normal_local) < 0: normal_local = normal_local.multiply(-1)

                elif isinstance(sub, Part.Face):
                    for e in sub.Edges:
                        if hasattr(e.Curve, "Radius"): radii.append(e.Curve.Radius)
                        
                    if hasattr(sub.Surface, "Axis"): 
                        axis = sub.Surface.Axis.normalize()
                        circular_edges = [e for e in sub.Edges if hasattr(e.Curve, "Center")]
                        if circular_edges:
                            picked_pt = sel[0].PickedPoints[0] if hasattr(sel[0], "PickedPoints") and len(sel[0].PickedPoints) > 0 else None
                            if picked_pt:
                                closest_edge = min(circular_edges, key=lambda e: (e.Curve.Center - picked_pt).Length)
                                center_local = closest_edge.Curve.Center
                            else: center_local = circular_edges[0].Curve.Center
                                
                            if (center_local - obj_center_local).dot(axis) > 0: normal_local = axis
                            else: normal_local = axis.multiply(-1)
                    else: 
                        center_local = sub.CenterOfMass
                        uv = sub.Surface.parameter(center_local)
                        normal_local = sub.normalAt(uv[0], uv[1]).normalize()
                        if (center_local - obj_center_local).dot(normal_local) < 0: normal_local = normal_local.multiply(-1)

                if center_local is not None and normal_local is not None:
                    Z = normal_local
                    if abs(Z.z) < 0.99: v_y = App.Vector(0, 0, 1) 
                    else: v_y = App.Vector(1, 0, 0) 
                        
                    X = v_y.cross(Z).normalize(); Y = Z.cross(X).normalize()
                    m = App.Matrix()
                    m.A11 = X.x; m.A12 = Y.x; m.A13 = Z.x; m.A14 = center_local.x
                    m.A21 = X.y; m.A22 = Y.y; m.A23 = Z.y; m.A24 = center_local.y
                    m.A31 = X.z; m.A32 = Y.z; m.A33 = Z.z; m.A34 = center_local.z
                    target_place = App.Placement(m)
                    
                if len(radii) >= 2:
                    radii.sort()
                    detected_D = radii[-1] * 2.0; detected_t = radii[-1] - radii[0]
                elif len(radii) == 1:
                    detected_D = radii[0] * 2.0; detected_t = max(2.0, detected_D * 0.05)
                    
            except Exception as e:
                App.Console.PrintError(f"Auto-detect error: {e}\n")

        sketches = [obj.Object for obj in sel if hasattr(obj, "Object") and obj.Object.isDerivedFrom("Sketcher::SketchObject")]
        FreeCADGui.Control.showDialog(PipeTaskPanel(sketches, target_place, detected_D, detected_t, detected_color))

try: FreeCADGui.addCommand('CreatePipeLibraries', CreatePipeLibraries())
except: pass