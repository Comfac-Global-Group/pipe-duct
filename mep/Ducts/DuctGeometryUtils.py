import FreeCAD
import Part
import math
from collections import deque

# ---------------------------------------------------------------------------
# Module-level angle constants (avoids repeated math.radians() calls)
# ---------------------------------------------------------------------------
_PI_4  = math.pi / 4.0       # 45°
_PI_2  = math.pi / 2.0       # 90°
_3PI_4 = 3.0 * math.pi / 4.0 # 135°
_PI    = math.pi              # 180°
_5PI_4 = 5.0 * math.pi / 4.0 # 225°
_3PI_2 = 3.0 * math.pi / 2.0 # 270°
_7PI_4 = 7.0 * math.pi / 4.0 # 315°
_2PI   = 2.0 * math.pi       # 360°

# ---------------------------------------------------------------------------
# Shared utility: strip FreeCAD Quantity objects to plain float
# ---------------------------------------------------------------------------
def _to_float(val):
    """Strip FreeCAD Quantity objects to raw float."""
    return float(val.Value if hasattr(val, 'Value') else val)

from compat import QtWidgets, QtCore, QtGui

TOLERANCE = 0.001

CATEGORIES = ["Straight", "Transitions", "Elbow", "Tee", "Offset"]
PROFILES = ["Rectangular", "Rounded Rectangular", "Circular"]
CONSTRUCTIONS = ["Smooth", "Segmented", "Mitered"]
TEE_TYPES = ["Y-Branch", "Straight Tee", "Cross Tee", "T Branch", "Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Rectangular Angled Branch", "Conical Wye Round"]

__all__ = [
    # Constants
    "TOLERANCE", "CATEGORIES", "PROFILES", "CONSTRUCTIONS", "TEE_TYPES",
    # Utilities
    "get_placement", "get_profile_wire", "get_vane_profile",
    "get_junction_points", "build_simple_paths", "fillet_wire_path", "create_profile",
    "fuse_shapes",
    # Fittings
    "build_straight_duct", "build_elbow", "build_drop_elbow",
    "build_tee", "build_offset", "build_route",
    "build_converging_wye_elbow", "build_converging_wye_round_junction",
    "build_wye_conical_with_collars", "build_circular_wye",
    "build_tee_rect_main_round_branch", "build_tee_rect_main_rect_branch",
    "build_tee_rect_angled_branch", "build_dovetail_wye",
    "build_rectangular_wye_geometry", "get_wye_polygon",
    # Helpers
    "make_rect_face", "make_swept_branch_solid", "make_yz_face",
    "analyze_route_segments",
]

def _compute_fitting_frame(primary_segment_direction, up_hint=None):
    # ORIENTATION: Universal right-handed frame calculation
    forward = primary_segment_direction.normalize()
    if up_hint is None:
        up = FreeCAD.Vector(0, 0, 1)
    else:
        up = up_hint.normalize()
        
    right = forward.cross(up)
    
    # Degenerate frame fallback
    if right.Length < 0.001:
        fallback_up = FreeCAD.Vector(0, 1, 0) if abs(forward.y) < 0.9 else FreeCAD.Vector(1, 0, 0)
        right = forward.cross(fallback_up).normalize()
    else:
        right = right.normalize()
        
    # Recompute up to guarantee perfect orthogonality
    up = right.cross(forward).normalize()
    
    return forward, right, up

#UTILITIES
def get_placement(center, v_z, v_y):
    # ORIENTATION: Route legacy get_placement through the new universal frame
    forward, right, up = _compute_fitting_frame(v_z, v_y)
    m = FreeCAD.Matrix()
    m.A11 = right.x; m.A12 = forward.x; m.A13 = up.x; m.A14 = center.x
    m.A21 = right.y; m.A22 = forward.y; m.A23 = up.y; m.A24 = center.y
    m.A31 = right.z; m.A32 = forward.z; m.A33 = up.z; m.A34 = center.z
    return FreeCAD.Placement(m)

def get_profile_wire(width, depth, thickness, point, tangent, up_vec, profile_type, corner_radius=0):
    t = thickness
    w = max(width - 2*t, 0.1)
    d = max(depth - 2*t, 0.1)
    rad = corner_radius
    if rad > 0: rad = max(rad - t, 0.0)
    return create_profile(w, d, rad, point, tangent, up_vec, profile_type)

def get_vane_profile(width, depth, point, tangent, up_vec):
    return create_profile(width, depth, 0.0, point, tangent, up_vec, "Rectangular")

def get_junction_points(edges):
    """Find junction points where more than 2 edges meet."""
    endpoints = []
    for e in edges:
        endpoints.append(e.valueAt(e.FirstParameter))
        endpoints.append(e.valueAt(e.LastParameter))
    unique_pts = []
    for pt in endpoints:
        if not any(pt.isEqual(u, TOLERANCE) for u in unique_pts):
            unique_pts.append(pt)
    junctions = []
    for pt in unique_pts:
        count = sum(1 for p in endpoints if pt.isEqual(p, TOLERANCE))
        if count > 2:
            junctions.append(pt)
    return junctions


def build_simple_paths(edges, junctions):
    """Break edges at junctions and build continuous paths."""
    broken_edges = []
    for e in edges:
        if not hasattr(e.Curve, 'TypeId') or e.Curve.TypeId != 'Part::GeomLine':
            broken_edges.append(e)
            continue
        
        p_s = e.valueAt(e.FirstParameter)
        p_e = e.valueAt(e.LastParameter)
        splits = []
        for jp in junctions:
            if e.distToShape(Part.Vertex(jp))[0] < TOLERANCE and not jp.isEqual(p_s, TOLERANCE) and not jp.isEqual(p_e, TOLERANCE):
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

    paths = []
    unprocessed = broken_edges[:]
    while unprocessed:
        e = unprocessed.pop(0)
        path = [e]
        while True:
            p_end = path[-1].valueAt(path[-1].LastParameter)
            if any(p_end.isEqual(jp, TOLERANCE) for jp in junctions): break
            found = False
            for i, nxt in enumerate(unprocessed):
                if nxt.valueAt(nxt.FirstParameter).isEqual(p_end, TOLERANCE):
                    path.append(nxt); unprocessed.pop(i); found = True; break
                elif nxt.valueAt(nxt.LastParameter).isEqual(p_end, TOLERANCE):
                    path.append(Part.makeLine(nxt.valueAt(nxt.LastParameter), nxt.valueAt(nxt.FirstParameter)))
                    unprocessed.pop(i); found = True; break
            if not found: break
            
        while True:
            p_start = path[0].valueAt(path[0].FirstParameter)
            if any(p_start.isEqual(jp, TOLERANCE) for jp in junctions): break
            found = False
            for i, prv in enumerate(unprocessed):
                if prv.valueAt(prv.LastParameter).isEqual(p_start, TOLERANCE):
                    path.insert(0, prv); unprocessed.pop(i); found = True; break
                elif prv.valueAt(prv.FirstParameter).isEqual(p_start, TOLERANCE):
                    path.insert(0, Part.makeLine(prv.valueAt(prv.LastParameter), prv.valueAt(prv.FirstParameter)))
                    unprocessed.pop(i); found = True; break
            if not found: break
        paths.append(path)
    return paths


def fillet_wire_path(edges, sketch_normal, w, offset_val, calc_inner_rad):
    """Apply fillet/rounded corners to a path of edges."""
    if len(edges) < 2: return edges
    pts = [edges[0].valueAt(edges[0].FirstParameter)]
    for e in edges: pts.append(e.valueAt(e.LastParameter))
    
    final_edges = []
    p_start_node = pts[0]
    
    for i in range(1, len(pts)-1):
        p_corner = pts[i]
        p_next = pts[i+1]
        
        v1 = (pts[i-1] - p_corner).normalize()
        v2 = (p_next - p_corner).normalize()
        angle = v1.getAngle(v2)
        
        if angle < 0.01 or angle > 3.13:
            if (p_corner - p_start_node).Length > TOLERANCE:
                final_edges.append(Part.makeLine(p_start_node, p_corner))
            p_start_node = p_corner
            continue
            
        # True 3D turn detection: project the cross product of the incoming
        # and outgoing vectors onto the sketch normal.  The old 2D cross_Z
        # shortcut (v1.x*v2.y - v1.y*v2.x) only works for flat XY-plane
        # sketches; this version is correct for any sketch orientation.
        v_in = -v1  # vector pointing INTO the corner along the incoming edge
        turn_axis = v_in.cross(v2)
        is_left_turn = turn_axis.dot(sketch_normal) > 0
        
        if is_left_turn:
            actual_path_radius = calc_inner_rad + (w / 2.0) + offset_val
        else:
            actual_path_radius = calc_inner_rad + (w / 2.0) - offset_val
        
        actual_path_radius = max(0.1, actual_path_radius)
        
        bisector = (v1 + v2).normalize()
        deflection = math.pi - angle
        T_required = actual_path_radius * math.tan(deflection / 2.0)
        
        L1 = (p_corner - p_start_node).Length
        L2 = (p_next - p_corner).Length
        
        if T_required > min(L1, L2) * 0.49:
            min_len = T_required * 2.05
            raise ValueError(
                f"A sketch segment is mathematically too short to be filleted!\n\n"
                f"To safely route a duct of this size around this corner without crushing, "
                f"the straight segment must be at least {min_len:.1f} mm long.\n\n"
                f"Found a segment of only {min(L1, L2):.1f} mm.\n"
                f"Please lengthen your sketch lines or reduce the duct dimensions."
            )

        p_tan1 = p_corner + v1 * T_required
        p_tan2 = p_corner + v2 * T_required
        
        if (p_tan1 - p_start_node).Length > TOLERANCE: 
            final_edges.append(Part.makeLine(p_start_node, p_tan1))
            
        dist_O = T_required / math.sin(deflection / 2.0)
        O = p_corner + bisector * dist_O
        mid_arc_pt = O - bisector * actual_path_radius
        
        arc = Part.Arc(p_tan1, mid_arc_pt, p_tan2).toShape()
        final_edges.append(arc)
        p_start_node = p_tan2
        
    if (pts[-1] - p_start_node).Length > TOLERANCE: 
        final_edges.append(Part.makeLine(p_start_node, pts[-1]))
        
    return final_edges


def create_profile(w, h, radius, start_pt, tangent, sketch_normal, shape_type):
    """Create a duct profile (rectangular, rounded rectangular, or round/circular)."""
    Z_new = tangent.normalize()
    Y_new = sketch_normal.normalize()
    X_new = Y_new.cross(Z_new).normalize()
    if X_new.Length < 0.0001:
        Y_new = FreeCAD.Vector(1, 0, 0) if abs(Z_new.x) < 0.9 else FreeCAD.Vector(0, 1, 0)
        X_new = Y_new.cross(Z_new).normalize()

    mat = FreeCAD.Matrix(X_new.x, Y_new.x, Z_new.x, start_pt.x, X_new.y, Y_new.y, Z_new.y, start_pt.y, X_new.z, Y_new.z, Z_new.z, start_pt.z, 0, 0, 0, 1)

    # Support both "Round" and "Circular" for round profile
    if shape_type in ("Round", "Circular"):
        circ = Part.Circle(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), w/2.0)
        wire = Part.Wire([Part.Edge(circ)])
        wire.Placement = FreeCAD.Placement(mat)
        return wire
        
    if shape_type == "Rectangular": radius = 0.001 

    if radius <= 0.001:
        p1 = FreeCAD.Vector(-w/2, -h/2, 0); p2 = FreeCAD.Vector(w/2, -h/2, 0)
        p3 = FreeCAD.Vector(w/2, h/2, 0); p4 = FreeCAD.Vector(-w/2, h/2, 0)
        wire = Part.Wire(Part.makePolygon([p1, p2, p3, p4, p1]))
    else:
        r = min(radius, (w/2.0) - TOLERANCE, (h/2.0) - TOLERANCE)
        c1 = FreeCAD.Vector(-w/2+r, -h/2+r, 0); c2 = FreeCAD.Vector(w/2-r, -h/2+r, 0)
        c3 = FreeCAD.Vector(w/2-r, h/2-r, 0); c4 = FreeCAD.Vector(-w/2+r, h/2-r, 0)
        Z_dir = FreeCAD.Vector(0, 0, 1)
        arc1 = Part.Edge(Part.Circle(c1, Z_dir, r), math.radians(180), math.radians(270))
        arc2 = Part.Edge(Part.Circle(c2, Z_dir, r), math.radians(270), math.radians(360))
        arc3 = Part.Edge(Part.Circle(c3, Z_dir, r), math.radians(0), math.radians(90))
        arc4 = Part.Edge(Part.Circle(c4, Z_dir, r), math.radians(90), math.radians(180))
        edge1 = Part.makeLine(FreeCAD.Vector(-w/2+r, -h/2, 0), FreeCAD.Vector(w/2-r, -h/2, 0))
        edge2 = Part.makeLine(FreeCAD.Vector(w/2, -h/2+r, 0), FreeCAD.Vector(w/2, h/2-r, 0))
        edge3 = Part.makeLine(FreeCAD.Vector(w/2-r, h/2, 0), FreeCAD.Vector(-w/2+r, h/2, 0))
        edge4 = Part.makeLine(FreeCAD.Vector(-w/2, h/2-r, 0), FreeCAD.Vector(-w/2, -h/2+r, 0))
        wire = Part.Wire([arc1, edge1, arc2, edge2, arc3, edge3, arc4, edge4])
        
    wire.Placement = FreeCAD.Placement(mat)
    return wire


def fuse_shapes(shape_list):
    """Optimized fusion of multiple shapes."""
    if not shape_list:
        return None
    if len(shape_list) == 1:
        return shape_list[0].removeSplitter()
    try:
        master = shape_list[0]
        for i in range(1, len(shape_list)): master = master.fuse(shape_list[i])
        return master.removeSplitter()
    except:
        master = shape_list[0]
        for s in shape_list[1:]: master = Part.makeSolid(master).fuse(Part.makeSolid(s))
        return master.removeSplitter()
    
#Duct FITINGS and PARTS
def build_straight_duct(center, normal, up_vec, w1, d1, w2, d2, length, thickness, profile1, profile2, corner_radius=0, alignment="Concentric"):
    # ORIENTATION: Save world inputs
    world_center, world_normal, world_up = center, normal, up_vec
    
    # ORIENTATION: Transform into local frame BEFORE generating geometry
    center = FreeCAD.Vector(0,0,0)
    normal = FreeCAD.Vector(0,1,0) # Trunk aligns to -Y, flow to +Y
    up_vec = FreeCAD.Vector(0,0,1) # Depth is Z
    
    # CRITICAL FIX: Ensure a minimum 1.0mm length so the Lofting engine never throws an Insufficient Separation error!
    length = max(length, 1.0)
    offset_vec = FreeCAD.Vector(0,0,0)
    if alignment != "Concentric":
        right_vec = up_vec.cross(normal).normalize()
        if right_vec.Length < 0.001: right_vec = FreeCAD.Vector(1,0,0)
        if "Top Flat" in alignment: offset_vec += up_vec * (d1 - d2) / 2.0
        elif "Bottom Flat" in alignment: offset_vec -= up_vec * (d1 - d2) / 2.0
        elif "Right Flat" in alignment: offset_vec += right_vec * (w1 - w2) / 2.0
        elif "Left Flat" in alignment: offset_vec -= right_vec * (w1 - w2) / 2.0

    P_end = center + normal * length + offset_vec
    start_out = get_profile_wire(w1, d1, 0.0, center, normal, up_vec, profile1, corner_radius)
    start_in = get_profile_wire(w1, d1, thickness, center, normal, up_vec, profile1, corner_radius)
    end_out = get_profile_wire(w2, d2, 0.0, P_end, normal, up_vec, profile2, corner_radius)
    end_in = get_profile_wire(w2, d2, thickness, P_end, normal, up_vec, profile2, corner_radius)

    outer_solid = Part.makeLoft([start_out, end_out], True, False)
    inner_solid = Part.makeLoft([start_in, end_in], True, False)
    
    solid = outer_solid.cut(inner_solid)

    # ORIENTATION: Apply inverse frame transform
    forward, right, up = _compute_fitting_frame(world_normal, world_up)
    m = FreeCAD.Matrix(right.x, forward.x, up.x, world_center.x,
                       right.y, forward.y, up.y, world_center.y,
                       right.z, forward.z, up.z, world_center.z,
                       0, 0, 0, 1)
    solid.Placement = FreeCAD.Placement(m)
    return solid

def build_elbow(center, normal, up_vec, w1, d1, w2, d2, angle, radius, construction, gores=3, vanes=0, thickness=0, profile="Rectangular", corner_radius=0):
    # ORIENTATION: Save world inputs
    world_center, world_normal, world_up = center, normal, up_vec
    
    # ORIENTATION: Transform into local frame BEFORE generating geometry
    center = FreeCAD.Vector(0,0,0)
    normal = FreeCAD.Vector(0,1,0) # Trunk aligns to -Y, flow to +Y
    up_vec = FreeCAD.Vector(0,0,1) # Depth is Z

    turn_axis = up_vec
    arc_center_dir = turn_axis.cross(normal).normalize()
    if angle < 0: arc_center_dir = -arc_center_dir

    # // STEP: Determine centerline bend radius based on construction type
    w_max = max(w1, w2)
    if construction == "Smooth":
        safe_bend_radius = w_max * 1.0
    elif construction == "Segmented":
        # 0.1mm safety buffer prevents 0-radius singularity crashes in the lofting engine!
        safe_bend_radius = max(radius, (w_max / 2.0) + 0.1)
    else:
        safe_bend_radius = max(radius, w_max / 2.0)
        
    arc_center = center + (arc_center_dir * safe_bend_radius)
    rot_end = FreeCAD.Rotation(turn_axis, angle)

    vec_start = center - arc_center
    dir_start = vec_start.normalize()
    duct_solid = None
    vanes_solids = []

    if construction == "Mitered":
        # UNIFIED ARCHITECTURE: 'center' is now the pulled-back start point!
        pb = safe_bend_radius * math.tan(math.radians(abs(angle)) / 2.0)
        route_vertex = center + normal * pb
        
        dir_out = rot_end.multVec(normal)
        
        # Build the faces outwards from the vertex to meet the pulled-back straight ducts
        p_start = center
        p_end = route_vertex + dir_out * pb
        
        # PERFECT OUTER EDGE MAPPING
        right_1 = -arc_center_dir
        right_2 = rot_end.multVec(right_1)
        
        def get_miter_corner(w1_val, w2_val, is_outer):
            sign = 1 if is_outer else -1
            w1_eff = sign * w1_val / 2.0
            w2_eff = sign * w2_val / 2.0
            denom = dir_out.dot(right_1)
            if abs(denom) < 1e-5: return route_vertex + right_1 * w1_eff
            u = (w1_eff - right_2.dot(right_1) * w2_eff) / denom
            return route_vertex + right_2 * w2_eff + dir_out * u
            
        C_out = get_miter_corner(w1, w2, True)
        C_in = get_miter_corner(w1, w2, False)
        C_mid = (C_out + C_in) / 2.0
        W_miter = (C_out - C_in).Length
        
        right_miter = (C_out - C_in).normalize()
        normal_miter = turn_axis.cross(right_miter).normalize()
        if normal_miter.dot(normal) < 0: normal_miter = -normal_miter
        D_miter = (d1 + d2) / 2.0
        
        w1_in = max(w1 - 2*thickness, 0.1)
        w2_in = max(w2 - 2*thickness, 0.1)
        C_out_in = get_miter_corner(w1_in, w2_in, True)
        C_in_in = get_miter_corner(w1_in, w2_in, False)
        C_mid_in = (C_out_in + C_in_in) / 2.0
        W_miter_in = (C_out_in - C_in_in).Length
        D_miter_in = max(D_miter - 2*thickness, 0.1)
        
        prof_start_out = get_profile_wire(w1, d1, 0.0, p_start, normal, up_vec, profile, corner_radius)
        prof_start_in = get_profile_wire(w1, d1, thickness, p_start, normal, up_vec, profile, corner_radius)
        
        prof_mid_out = get_profile_wire(W_miter, D_miter, 0.0, C_mid, normal_miter, up_vec, profile, corner_radius)
        prof_mid_in = get_profile_wire(W_miter_in, D_miter_in, 0.0, C_mid_in, normal_miter, up_vec, profile, corner_radius)
        
        prof_end_out = get_profile_wire(w2, d2, 0.0, p_end, dir_out, up_vec, profile, corner_radius)
        prof_end_in = get_profile_wire(w2, d2, thickness, p_end, dir_out, up_vec, profile, corner_radius)
        
        seg1_out = Part.makeLoft([prof_start_out, prof_mid_out], True, False)
        seg2_out = Part.makeLoft([prof_mid_out, prof_end_out], True, False)
        outer_solid = seg1_out.fuse(seg2_out).removeSplitter()
        
        seg1_in = Part.makeLoft([prof_start_in, prof_mid_in], True, False)
        seg2_in = Part.makeLoft([prof_mid_in, prof_end_in], True, False)
        inner_solid = seg1_in.fuse(seg2_in).removeSplitter()
        
        ext_in_start = Part.Face(prof_start_in).extrude(normal * -5.0)
        ext_in_end = Part.Face(prof_end_in).extrude(dir_out * 5.0)
        inner_solid = inner_solid.fuse([ext_in_start, ext_in_end])
        
        duct_solid = outer_solid.cut(inner_solid).removeSplitter()

    elif construction == "Segmented":
        N = gores
        beta = angle / (2.0 * (N - 1))
        beta_rad = math.radians(beta)

        angles_list = [0.0]
        for i in range(1, N): angles_list.append((2*i - 1) * beta)
        angles_list.append(angle)

        profs_out = []; profs_in = []
        for v_idx, a in enumerate(angles_list):
            rot_a  = FreeCAD.Rotation(turn_axis, a)
            norm_a = rot_a.multVec(normal)
            up_a   = rot_a.multVec(up_vec)

            frac   = a / angle if angle != 0 else 0
            w_curr = w1 + (w2 - w1) * frac
            d_curr = d1 + (d2 - d1) * frac

            if a <= 0.01 or a >= angle - 0.01:
                R_eff = safe_bend_radius; W_eff = w_curr
            else:
                R_eff = safe_bend_radius / math.cos(beta_rad); W_eff = w_curr / math.cos(beta_rad)

            pt_a = arc_center + rot_a.multVec(dir_start * R_eff)

            profs_out.append(get_profile_wire(W_eff, d_curr, 0.0,       pt_a, norm_a, up_a, profile, corner_radius))
            profs_in.append( get_profile_wire(W_eff, d_curr, thickness,  pt_a, norm_a, up_a, profile, corner_radius))

        seg_lofts_out = [Part.makeLoft([profs_out[i], profs_out[i+1]], True, False) for i in range(len(angles_list) - 1)]
        seg_lofts_in  = [Part.makeLoft([profs_in[i],  profs_in[i+1]],  True, False) for i in range(len(angles_list) - 1)]

        outer_solid = seg_lofts_out[0].fuse(seg_lofts_out[1:]) if len(seg_lofts_out) > 1 else seg_lofts_out[0]
        inner_solid = seg_lofts_in[0].fuse(seg_lofts_in[1:])   if len(seg_lofts_in)  > 1 else seg_lofts_in[0]

        ext_in_start = Part.Face(profs_in[0]).extrude(normal * -5.0)
        ext_in_end = Part.Face(profs_in[-1]).extrude(rot_end.multVec(normal) * 5.0)
        duct_solid = outer_solid.removeSplitter().cut(inner_solid.fuse([ext_in_start, ext_in_end]).removeSplitter())

        if vanes > 0 and profile != "Circular":
            joint_angles = angles_list[1:-1]

            for j_ang in joint_angles:
                rot_joint = FreeCAD.Rotation(turn_axis, j_ang)
                up_joint = rot_joint.multVec(up_vec)

                rad_joint = rot_joint.multVec(dir_start)

                frac_j = j_ang / angle if angle != 0 else 0
                w_curr = w1 + (w2 - w1) * frac_j
                d_curr = d1 + (d2 - d1) * frac_j

                W_joint = w_curr / math.cos(beta_rad)
                R_eff_joint = safe_bend_radius / math.cos(beta_rad)

                joint_center = arc_center + rad_joint * R_eff_joint

                vane_thickness = max(thickness, 1.0) if thickness > 0 else 1.0
                inner_depth = max(d_curr - 2 * thickness, 0.1)

                vane_spacing = W_joint / (vanes + 1.0)
                vane_R = min(max(vane_spacing * 0.75, 10.0), 100.0)

                vane_turn_angle = 2.0 * beta

                for v_idx in range(1, vanes + 1):
                    frac_v = v_idx / (vanes + 1.0)

                    vane_pt = joint_center + rad_joint * (-W_joint / 2.0 + W_joint * frac_v)
                    arc_center_v = vane_pt - rad_joint * vane_R

                    rot_back = FreeCAD.Rotation(turn_axis, -vane_turn_angle / 2.0)
                    rot_fwd = FreeCAD.Rotation(turn_axis, vane_turn_angle / 2.0)

                    v_rad_start = rot_back.multVec(rad_joint)
                    v_rad_end = rot_fwd.multVec(rad_joint)

                    p_in_start = arc_center_v + v_rad_start * (vane_R - vane_thickness / 2.0)
                    p_in_mid = arc_center_v + rad_joint * (vane_R - vane_thickness / 2.0)
                    p_in_end = arc_center_v + v_rad_end * (vane_R - vane_thickness / 2.0)

                    p_out_start = arc_center_v + v_rad_start * (vane_R + vane_thickness / 2.0)
                    p_out_mid = arc_center_v + rad_joint * (vane_R + vane_thickness / 2.0)
                    p_out_end = arc_center_v + v_rad_end * (vane_R + vane_thickness / 2.0)

                    try:
                        arc_inner = Part.Arc(p_in_start, p_in_mid, p_in_end).toShape()
                        line_end = Part.makeLine(p_in_end, p_out_end)
                        arc_outer = Part.Arc(p_out_end, p_out_mid, p_out_start).toShape()
                        line_start = Part.makeLine(p_out_start, p_in_start)

                        vane_wire = Part.Wire([arc_inner, line_end, arc_outer, line_start])

                        v_solid = Part.Face(vane_wire).extrude(up_joint * inner_depth)
                        v_solid.translate(-up_joint * (inner_depth / 2.0))

                        vanes_solids.append(v_solid)
                    except Exception as e:
                        FreeCAD.Console.PrintError(f"Vane creation failed: {e}\n")

    else:
        profs_out = []; profs_in = []
        steps = max(6, int(abs(angle) / 15.0))

        for i in range(steps + 1):
            frac = i / float(steps)
            rot = FreeCAD.Rotation(turn_axis, angle * frac)

            p_cur   = arc_center + rot.multVec(dir_start * safe_bend_radius)
            norm_cur = rot.multVec(normal)
            up_cur   = rot.multVec(up_vec)
            w_cur = w1 + (w2 - w1) * frac
            d_cur = d1 + (d2 - d1) * frac

            profs_out.append(get_profile_wire(w_cur, d_cur, 0.0,       p_cur, norm_cur, up_cur, profile, corner_radius))
            profs_in.append( get_profile_wire(w_cur, d_cur, thickness,  p_cur, norm_cur, up_cur, profile, corner_radius))

        duct_solid = Part.makeLoft(profs_out, True, False).cut(Part.makeLoft(profs_in, True, False))

        if vanes > 0 and profile != "Circular":
            for v_idx in range(1, vanes + 1):
                frac_v = v_idx / (vanes + 1.0)
                s_start = -w1/2.0 + frac_v * w1
                s_end = -w2/2.0 + frac_v * w2

                vane_profs = []
                for i in range(steps + 1):
                    frac = i / float(steps)
                    rot = FreeCAD.Rotation(turn_axis, angle * frac)
                    v_rad_cur = safe_bend_radius + (s_start + (s_end - s_start) * frac)

                    v_prof = get_vane_profile(thickness, max(d1 + (d2 - d1) * frac - 2*thickness, 0.1), arc_center + rot.multVec(dir_start * v_rad_cur), rot.multVec(normal), rot.multVec(up_vec))
                    vane_profs.append(v_prof)
                vanes_solids.append(Part.makeLoft(vane_profs, True, False))

    if vanes_solids:
        duct_solid = duct_solid.fuse(vanes_solids).removeSplitter()

    # ORIENTATION: Apply inverse frame transform
    forward, right, up = _compute_fitting_frame(world_normal, world_up)
    m = FreeCAD.Matrix(right.x, forward.x, up.x, world_center.x,
                       right.y, forward.y, up.y, world_center.y,
                       right.z, forward.z, up.z, world_center.z,
                       0, 0, 0, 1)
    duct_solid.Placement = FreeCAD.Placement(m)
    return duct_solid

def build_drop_elbow(center, normal, base_up, roll_angle, w1, d1, w2, d2, h, l, thickness, profile, corner_radius):
    # ORIENTATION: Save world inputs
    world_center, world_normal, world_up = center, normal, base_up
    
    # ORIENTATION: Transform into local frame BEFORE generating geometry
    center = FreeCAD.Vector(0,0,0)
    normal = FreeCAD.Vector(0,1,0) # Trunk aligns to -Y, flow to +Y
    base_up = FreeCAD.Vector(0,0,1) # Depth is Z

    l = max(l, 0.1)
    l_exit = max(h, 0.1) if h > 0.1 else l

    V_in = normal.normalize()
    right = base_up.cross(V_in)
    if right.Length < 0.001: right = FreeCAD.Vector(1, 0, 0) if abs(V_in.x) < 0.5 else FreeCAD.Vector(0, 1, 0)
    right = right.normalize()
    V_mid = FreeCAD.Rotation(V_in, roll_angle).multVec(right).normalize()
    V_out = V_in.cross(V_mid).normalize()

    P0 = center; P1 = P0 + V_in * l; P2 = P1 + V_mid * l
    O_V = 100.0; ovlp = 0.1

    def extrude_seg(w, d, t, P_start, V_dir, up_dir, L_total):
        return Part.Face(get_profile_wire(w, d, t, P_start, V_dir, up_dir, profile, corner_radius)).extrude(V_dir * L_total)

    def make_cutter(P, N):
        Z = FreeCAD.Vector(0, 0, 1)
        axis = Z.cross(N)
        rot = FreeCAD.Rotation(axis, math.degrees(Z.getAngle(N))) if axis.Length > 0.001 else (FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 180) if N.z < 0 else FreeCAD.Rotation())
        p1 = FreeCAD.Vector(-5000, -5000, 0); p2 = FreeCAD.Vector(5000, -5000, 0)
        p3 = FreeCAD.Vector(5000, 5000, 0); p4 = FreeCAD.Vector(-5000, 5000, 0)
        face = Part.Face(Part.Wire(Part.makePolygon([p1, p2, p3, p4, p1])))
        face.Placement = FreeCAD.Placement(P, rot)
        return face.extrude(N * 5000)

    w_mid = (w1 + w2) / 2.0; d_mid = (d1 + d2) / 2.0

    seg1_out = extrude_seg(w1, d1, 0.0, P0 - V_in * 5.0, V_in, base_up, 5.0 + l + O_V).cut(make_cutter(P1 + (V_in + V_mid).normalize() * ovlp, (V_in + V_mid).normalize()))
    seg1_in  = extrude_seg(w1, d1, thickness, P0 - V_in * 5.0, V_in, base_up, 5.0 + l + O_V).cut(make_cutter(P1 + (V_in + V_mid).normalize() * ovlp, (V_in + V_mid).normalize()))

    seg2_out_j1 = extrude_seg(w_mid, d_mid, 0.0, P1 - V_mid * O_V, V_mid, base_up, O_V + l + O_V).cut(make_cutter(P1 - (V_in + V_mid).normalize() * ovlp, -(V_in + V_mid).normalize()))
    seg2_in_j1  = extrude_seg(w_mid, d_mid, thickness, P1 - V_mid * O_V, V_mid, base_up, O_V + l + O_V).cut(make_cutter(P1 - (V_in + V_mid).normalize() * ovlp, -(V_in + V_mid).normalize()))

    seg2_out_final = seg2_out_j1.cut(make_cutter(P2 + (V_mid + V_out).normalize() * ovlp, (V_mid + V_out).normalize()))
    seg2_in_final  = seg2_in_j1.cut(make_cutter(P2 + (V_mid + V_out).normalize() * ovlp, (V_mid + V_out).normalize()))

    seg3_out_final = extrude_seg(w2, d2, 0.0, P2 - V_out * O_V, V_out, V_mid, O_V + l_exit + 5.0).cut(make_cutter(P2 - (V_mid + V_out).normalize() * ovlp, -(V_mid + V_out).normalize()))
    seg3_in_final  = extrude_seg(w2, d2, thickness, P2 - V_out * O_V, V_out, V_mid, O_V + l_exit + 5.0).cut(make_cutter(P2 - (V_mid + V_out).normalize() * ovlp, -(V_mid + V_out).normalize()))

    final_solid = seg1_out.fuse([seg2_out_final, seg3_out_final]).removeSplitter().cut(seg1_in.fuse([seg2_in_final, seg3_in_final ]).removeSplitter())

    # ORIENTATION: Apply inverse frame transform
    forward, right, up = _compute_fitting_frame(world_normal, world_up)
    m = FreeCAD.Matrix(right.x, forward.x, up.x, world_center.x,
                       right.y, forward.y, up.y, world_center.y,
                       right.z, forward.z, up.z, world_center.z,
                       0, 0, 0, 1)
    final_solid.Placement = FreeCAD.Placement(m)
    return final_solid

def analyze_route_segments(route_segments, center, normal, right_vec, up_vec):
    if not route_segments or len(route_segments) < 2:
        return normal, [right_vec], False

    connected_segments = []
    for start, end, length in route_segments:
        start_dist = (start - center).Length
        end_dist = (end - center).Length

        if start_dist < 1.0 or end_dist < 1.0:
            direction = (end - start).normalize()
            if start_dist < 1.0:
                direction = -direction 
            connected_segments.append((direction, length))

    if len(connected_segments) < 2:
        return normal, [right_vec], False

    connected_segments.sort(key=lambda x: x[1], reverse=True)

    trunk_vector = connected_segments[0][0]
    branch_vectors = [seg[0] for seg in connected_segments[1:]]

    trunk_dot_normal = abs(trunk_vector.dot(normal))
    is_swapped = trunk_dot_normal < 0.707

    return trunk_vector, branch_vectors, is_swapped

def build_tee(center, normal, up_vec, right_vec, w1, d1, w2, d2, w3, d3, w4, d4, tee_type, angle, radius, length, thickness, profile, corner_radius, vanes=0, **kwargs):
    w1, d1 = _to_float(w1), _to_float(d1)
    w2, d2 = _to_float(w2), _to_float(d2)
    w3, d3 = _to_float(w3), _to_float(d3)
    w4, d4 = _to_float(w4), _to_float(d4)
    length       = max(_to_float(length), 0.1)
    radius       = _to_float(radius)
    thickness    = _to_float(thickness)
    angle        = _to_float(angle)
    corner_radius = _to_float(corner_radius)

    branch_collar = 0.0

    try:
        if tee_type == "Rectangular Dovetail Wye":
            return build_dovetail_wye(center, normal, up_vec, w1, d1, w3, d3, w4, d4, length, kwargs.get('branch_length', length), thickness)

        elif tee_type == "Converging Wye":
            w_branch = max(w3, w4); h_branch = max(d3, d4)
            return build_converging_wye_elbow(center, normal, up_vec, w1, d1, w_branch, h_branch, radius, length, branch_collar, thickness)

        elif tee_type == "Rectangular Angled Branch":
            w_branch = max(w3, w4); h_branch = max(d3, d4)
            return build_tee_rect_angled_branch(center, normal, up_vec, w1, d1, w_branch, h_branch, angle, length, branch_collar, thickness)

        if tee_type in ["Straight Tee", "Cross Tee", "T Branch"]:
            # ORIENTATION: Universal Orientation Frame
            forward, right_dir, up = _compute_fitting_frame(normal, up_vec)
            m = FreeCAD.Matrix(right_dir.x, forward.x, up.x, center.x,
                               right_dir.y, forward.y, up.y, center.y,
                               right_dir.z, forward.z, up.z, center.z,
                               0, 0, 0, 1)
            placement = FreeCAD.Placement(m)
            
            if profile == "Circular":
                r1_out = w1/2.0; r1_in = max(0.1, r1_out - thickness)
                r3_out = w3/2.0; r3_in = max(0.1, r3_out - thickness)
                r4_out = w4/2.0; r4_in = max(0.1, r4_out - thickness)

                main_out = Part.makeCylinder(r1_out, length, FreeCAD.Vector(0,0,-length/2.0), FreeCAD.Vector(0,0,1))
                main_in = Part.makeCylinder(r1_in, length+2, FreeCAD.Vector(0,0,-length/2.0-1), FreeCAD.Vector(0,0,1))
                shapes_out = [main_out]; shapes_in = [main_in]

                b1_out = Part.makeCylinder(r3_out, branch_collar + w1/2.0, FreeCAD.Vector(0,0,0), FreeCAD.Vector(1,0,0))
                b1_in = Part.makeCylinder(r3_in, branch_collar + w1/2.0 + 2, FreeCAD.Vector(-1,0,0), FreeCAD.Vector(1,0,0))
                shapes_out.append(b1_out); shapes_in.append(b1_in)

                if tee_type == "Cross Tee":
                    b2_out = Part.makeCylinder(r4_out, branch_collar + w1/2.0, FreeCAD.Vector(0,0,0), FreeCAD.Vector(-1,0,0))
                    b2_in = Part.makeCylinder(r4_in, branch_collar + w1/2.0 + 2, FreeCAD.Vector(1,0,0), FreeCAD.Vector(-1,0,0))
                    shapes_out.append(b2_out); shapes_in.append(b2_in)
            else:
                main_out = Part.makeBox(w1, d1, length)
                main_out.translate(FreeCAD.Vector(-w1/2.0, -d1/2.0, -length/2.0))
                main_in = Part.makeBox(w1 - 2*thickness, d1 - 2*thickness, length + 2.0)
                main_in.translate(FreeCAD.Vector(-w1/2.0 + thickness, -d1/2.0 + thickness, -length/2.0 - 1.0))
                shapes_out = [main_out]; shapes_in = [main_in]

                b1_out = Part.makeBox(branch_collar, d3, w3)
                b1_out.translate(FreeCAD.Vector(w1/2.0, -d3/2.0, -w3/2.0))
                b1_in = Part.makeBox(branch_collar + 2.0, d3 - 2*thickness, w3 - 2*thickness)
                b1_in.translate(FreeCAD.Vector(w1/2.0 - 1.0, -d3/2.0 + thickness, -w3/2.0 + thickness))
                shapes_out.append(b1_out); shapes_in.append(b1_in)

                if tee_type == "Cross Tee":
                    b2_out = Part.makeBox(branch_collar, d4, w4)
                    b2_out.translate(FreeCAD.Vector(-w1/2.0 - branch_collar, -d4/2.0, -w4/2.0))
                    b2_in = Part.makeBox(branch_collar + 2.0, d4 - 2*thickness, w4 - 2*thickness)
                    b2_in.translate(FreeCAD.Vector(-w1/2.0 - branch_collar - 1.0, -d4/2.0 + thickness, -w4/2.0 + thickness))
                    shapes_out.append(b2_out); shapes_in.append(b2_in)

            outer = shapes_out[0].fuse(shapes_out[1:]).removeSplitter()
            inner = shapes_in[0].fuse(shapes_in[1:])
            final_duct = outer.cut(inner).removeSplitter()
            
            # ORIENTATION: Align Legacy Z-Trunk to Canonical Y-Trunk
            rot_mat = FreeCAD.Matrix(1, 0, 0, 0,
                                     0, 0, 1, 0,
                                     0,-1, 0, 0,
                                     0, 0, 0, 1)
            final_duct = final_duct.transformGeometry(rot_mat)
            final_duct.Placement = placement
            return final_duct

        elif "Y-Branch" in tee_type:
            # FIX 1: Explicitly flush cached defaults so they don't bleed into the y-branch
            if not w3 or w3 == 100.0: w3 = w1
            if not d3 or d3 == 100.0: d3 = d1
            if not w4 or w4 == 100.0: w4 = w1
            if not d4 or d4 == 100.0: d4 = d1

            # ORIENTATION: Transform inputs to local frame BEFORE generating geometry
            old_center, old_normal, old_up, old_right = center, normal, up_vec, right_vec
            center = FreeCAD.Vector(0,0,0)
            normal = FreeCAD.Vector(0,1,0) # Trunk Y
            up_vec = FreeCAD.Vector(0,0,1) # Depth Z
            right_vec = FreeCAD.Vector(1,0,0) # Lateral X
            
            # CRITICAL FIX: The geometry engine builds purely from the origin! 
            # (The Middleman function handles all world-space coordinate shifting).
            C_split_center = center + right_vec * ((w4 - w3) / 2.0)

            # --- 1. LOFT-FREE TRUNK TAPER BLOCK ---
            def make_taper_block(w_start, w_end, d_depth, t_length, offset_y):
                p1 = C_split_center - normal * t_length - right_vec * (w_start / 2.0)
                p2 = C_split_center - normal * t_length + right_vec * (w_start / 2.0)
                p3 = C_split_center + normal * offset_y + right_vec * (w_end / 2.0)
                p4 = C_split_center + normal * offset_y - right_vec * (w_end / 2.0)
                wire = Part.makePolygon([p1, p2, p3, p4, p1])
                return Part.Face(wire).extrude(up_vec * d_depth).translate(-up_vec * (d_depth / 2.0))

            t_arm_len = max(length, 0.1)
            w_split = w3 + w4
            
            # 0.1 overlap ensures it physically intersects the branches (fixes kissing edges)
            trunk_out = make_taper_block(w1, w_split, d1, t_arm_len, 0.1) 
            
            w1_in = max(w1 - 2*thickness, 0.1)
            w_split_in = max(w_split - 2*thickness, 0.1)
            d1_in = max(d1 - 2*thickness, 0.1)
            
            # Stops exactly at 0.0 to prevent the void from piercing the curved branch walls
            trunk_in = make_taper_block(w1_in, w_split_in, d1_in, t_arm_len, 0.0) 

            # --- 2. LOFT-FREE REVOLVED BRANCHES ---
            def build_revolved_branch(w_b, d_b, angle_b, sign, offset_w):
                p_start = C_split_center + right_vec * offset_w
                R_center = radius + w_b / 2.0
                arc_C = p_start + right_vec * (sign * R_center)

                # Generate 2D Profile Faces and Revolve them around the arc center
                prof_out_wire = get_profile_wire(w_b, d_b, 0.0, p_start, normal, up_vec, profile, corner_radius)
                prof_in_wire = get_profile_wire(w_b, d_b, thickness, p_start, normal, up_vec, profile, corner_radius)
                
                axis = -up_vec if sign > 0 else up_vec
                
                rev_out = Part.Face(prof_out_wire).revolve(arc_C, axis, angle_b)
                rev_in = Part.Face(prof_in_wire).revolve(arc_C, axis, angle_b)
                
                # Straight arm extensions
                rot = FreeCAD.Rotation(up_vec, -sign * angle_b)
                norm_end = rot.multVec(normal)
                p_end = arc_C + rot.multVec(right_vec * (-sign * R_center))
                
                prof_end_out = get_profile_wire(w_b, d_b, 0.0, p_end, norm_end, up_vec, profile, corner_radius)
                prof_end_in = get_profile_wire(w_b, d_b, thickness, p_end, norm_end, up_vec, profile, corner_radius)
                
                b_arm_len = max(kwargs.get('branch_length', length), 0.1)
                arm_out = Part.Face(prof_end_out).extrude(norm_end * b_arm_len)
                arm_in = Part.Face(prof_end_in).extrude(norm_end * b_arm_len)
                
                return rev_out.fuse(arm_out).removeSplitter(), rev_in.fuse(arm_in).removeSplitter()

            solid_L_out, solid_L_in = build_revolved_branch(w3, d3, angle, -1, -w3 / 2.0)
            solid_R_out, solid_R_in = build_revolved_branch(w4, d4, angle, 1, w4 / 2.0)

            # --- 3. FINAL BOOLEAN ASSEMBLY ---
            outer_fusion = trunk_out.fuse([solid_L_out, solid_R_out]).removeSplitter()
            inner_fusion = trunk_in.fuse([solid_L_in, solid_R_in]).removeSplitter()
            
            final_duct = outer_fusion.cut(inner_fusion)
            
            # ORIENTATION: Apply inverse frame transform
            forward, right_dir, up = _compute_fitting_frame(old_normal, old_up)
            m = FreeCAD.Matrix(right_dir.x, forward.x, up.x, old_center.x,
                               right_dir.y, forward.y, up.y, old_center.y,
                               right_dir.z, forward.z, up.z, old_center.z,
                               0, 0, 0, 1)
            final_duct.Placement = FreeCAD.Placement(m)
            return final_duct

        return None

    except Exception as e:
        import traceback
        FreeCAD.Console.PrintError(f"Error building {tee_type}: {str(e)}\n{traceback.format_exc()}\n")
        return None

def build_converging_wye_round_junction(center, normal, up_vec, right_vec, main_diameter, branch_diameter, angle_deg, length, thickness):
    # ORIENTATION: Save world inputs
    world_center, world_normal, world_up = center, normal, up_vec
    
    # ORIENTATION: Transform into local frame BEFORE generating geometry
    center = FreeCAD.Vector(0,0,0)
    normal = FreeCAD.Vector(0,1,0) # Trunk aligns to -Y, flow to +Y
    up_vec = FreeCAD.Vector(0,0,1) # Depth is Z
    right_vec = FreeCAD.Vector(1,0,0) # Lateral X

    normal = normal.normalize()
    up_vec = up_vec.normalize()
    right_vec = right_vec.normalize()

    r_main_out = main_diameter / 2.0
    r_main_in = r_main_out - thickness
    r_branch_out = branch_diameter / 2.0
    r_branch_in = r_branch_out - thickness

    start_main = center - normal * (length / 2.0)

    main_outer = Part.makeCylinder(r_main_out, length, start_main, normal)
    main_inner = Part.makeCylinder(r_main_in, length, start_main, normal)

    angle_rad = math.radians(angle_deg)

    if abs(angle_deg - 90) < 0.1:
        angle_rad = math.radians(89.9)

    branch_dir = normal * math.cos(angle_rad) + right_vec * math.sin(angle_rad)
    branch_dir = branch_dir.normalize()

    start_branch = center - branch_dir * length

    branch_outer = Part.makeCylinder(r_branch_out, length, start_branch, branch_dir)
    branch_inner = Part.makeCylinder(r_branch_in, length, start_branch, branch_dir)

    outer_shell = main_outer.fuse([branch_outer])
    inner_void = main_inner.fuse([branch_inner])
    final_duct = outer_shell.cut(inner_void).removeSplitter()

    # ORIENTATION: Apply inverse frame transform
    forward, right_dir, up = _compute_fitting_frame(world_normal, world_up)
    m = FreeCAD.Matrix(right_dir.x, forward.x, up.x, world_center.x,
                       right_dir.y, forward.y, up.y, world_center.y,
                       right_dir.z, forward.z, up.z, world_center.z,
                       0, 0, 0, 1)
    final_duct.Placement = FreeCAD.Placement(m)
    return final_duct

def build_wye_conical_with_collars(center, normal, up_vec, d_s, d_b, angle_deg, inlet_len, reducer_len, outlet_len, branch_length, thickness, d_c=None):
    # ORIENTATION: Compute Universal Frame
    forward, right_dir, up = _compute_fitting_frame(normal, up_vec)
    m = FreeCAD.Matrix(right_dir.x, forward.x, up.x, center.x,
                       right_dir.y, forward.y, up.y, center.y,
                       right_dir.z, forward.z, up.z, center.z,
                       0, 0, 0, 1)
    placement = FreeCAD.Placement(m)
    
    if d_c is None:
        d_c = d_s * 2.0

    r_s_out, r_s_in = (d_s / 2.0), (d_s / 2.0) - thickness
    r_c_out, r_c_in = (d_c / 2.0), (d_c / 2.0) - thickness
    r_b_out, r_b_in = (d_b / 2.0), (d_b / 2.0) - thickness

    z_start_reducer = -reducer_len / 2.0
    z_end_reducer = reducer_len / 2.0

    z_start_inlet = z_start_reducer - inlet_len
    z_end_outlet = z_end_reducer + outlet_len

    inlet_out = Part.makeCylinder(r_s_out, inlet_len, FreeCAD.Vector(0, 0, z_start_inlet), FreeCAD.Vector(0, 0, 1))
    reducer_out = Part.makeCone(r_s_out, r_c_out, reducer_len, FreeCAD.Vector(0, 0, z_start_reducer), FreeCAD.Vector(0, 0, 1))
    outlet_out = Part.makeCylinder(r_c_out, outlet_len, FreeCAD.Vector(0, 0, z_end_reducer), FreeCAD.Vector(0, 0, 1))

    dz = 0.5
    inlet_in = Part.makeCylinder(r_s_in, inlet_len + dz, FreeCAD.Vector(0, 0, z_start_inlet - dz), FreeCAD.Vector(0, 0, 1))
    outlet_in = Part.makeCylinder(r_c_in, outlet_len + dz, FreeCAD.Vector(0, 0, z_end_reducer), FreeCAD.Vector(0, 0, 1))

    slope = (r_c_in - r_s_in) / reducer_len
    r_s_in_ext = max(0.01, r_s_in - (slope * dz))
    r_c_in_ext = r_c_in + (slope * dz)
    reducer_in = Part.makeCone(r_s_in_ext, r_c_in_ext, reducer_len + 2*dz, FreeCAD.Vector(0, 0, z_start_reducer - dz), FreeCAD.Vector(0, 0, 1))

    main_shell = inlet_out.fuse([reducer_out, outlet_out])
    main_void = inlet_in.fuse([reducer_in, outlet_in])

    angle_rad = math.radians(angle_deg)
    branch_vec = FreeCAD.Vector(math.sin(angle_rad), 0, -math.cos(angle_rad))
    total_branch_len = r_c_out + branch_length

    branch_origin = FreeCAD.Vector(0, 0, 0)

    branch_out = Part.makeCylinder(r_b_out, total_branch_len, branch_origin, branch_vec)
    branch_in = Part.makeCylinder(r_b_in, total_branch_len + 2*dz, branch_origin - branch_vec * dz, branch_vec)

    final_duct = main_shell.fuse([branch_out]).cut(main_void.fuse([branch_in])).removeSplitter()
    
    # ORIENTATION: Align from Legacy (Trunk Z) to Canonical (Trunk -Y, Branches +Y)
    rot_mat = FreeCAD.Matrix(1, 0, 0, 0,
                             0, 0,-1, 0,
                             0, 1, 0, 0,
                             0, 0, 0, 1)
    final_duct = final_duct.transformGeometry(rot_mat)
    final_duct.Placement = placement
    return final_duct

def get_profile_circle(radius, center, normal, up_vec):
    p1 = center + up_vec * radius
    circle = Part.makeCircle(radius, center, normal)
    return Part.Wire(circle)

def build_tee_rect_main_round_branch(center, normal, up_vec, right_vec, W1, D1, W3, TeeLength, thickness):
    # ORIENTATION: Universal Orientation Frame
    forward, right_dir, up = _compute_fitting_frame(normal, up_vec)
    m = FreeCAD.Matrix(right_dir.x, forward.x, up.x, center.x,
                       right_dir.y, forward.y, up.y, center.y,
                       right_dir.z, forward.z, up.z, center.z,
                       0, 0, 0, 1)
    placement = FreeCAD.Placement(m)
    
    main_out = Part.makeBox(W1, D1, TeeLength)
    main_out.translate(FreeCAD.Vector(-W1/2, -D1/2, -TeeLength/2))

    mw_in = W1 - 2 * thickness
    mh_in = D1 - 2 * thickness
    main_in = Part.makeBox(mw_in, mh_in, TeeLength + 2)
    main_in.translate(FreeCAD.Vector(-mw_in/2, -mh_in/2, -(TeeLength + 2)/2))

    r_out = W3 / 2.0
    r_in = r_out - thickness

    embed = min(0.1, thickness / 2.0)
    start_x_out = (W3 / 2.0) - embed
    branch_out = Part.makeCylinder(r_out, TeeLength + embed, FreeCAD.Vector(start_x_out, 0, 0), FreeCAD.Vector(1, 0, 0))

    start_x_in = (W1 / 2.0) - thickness - 1.0
    branch_in = Part.makeCylinder(r_in, TeeLength + thickness + 2.0, FreeCAD.Vector(start_x_in, 0, 0), FreeCAD.Vector(1, 0, 0))

    outer_shell = main_out.fuse([branch_out])
    inner_void = main_in.fuse([branch_in])
    final_duct = outer_shell.cut(inner_void).removeSplitter()

    # ORIENTATION: Align from Legacy (Trunk Z, Depth Y) to Canonical (Trunk -Y, Depth Z)
    rot_mat = FreeCAD.Matrix(1, 0, 0, 0,
                             0, 0, 1, 0,
                             0,-1, 0, 0,
                             0, 0, 0, 1)
    final_duct = final_duct.transformGeometry(rot_mat)
    final_duct.Placement = placement
    return final_duct

def build_tee_rect_main_rect_branch(center, normal, up_vec, right_vec, W1, D1, W3, D3, TeeLength, thickness):
    # ORIENTATION: Universal Orientation Frame
    forward, right_dir, up = _compute_fitting_frame(normal, up_vec)
    m = FreeCAD.Matrix(right_dir.x, forward.x, up.x, center.x,
                       right_dir.y, forward.y, up.y, center.y,
                       right_dir.z, forward.z, up.z, center.z,
                       0, 0, 0, 1)
    placement = FreeCAD.Placement(m)

    main_out = Part.makeBox(W1, D1, TeeLength)
    main_out.translate(FreeCAD.Vector(-W1/2, -D1/2, -TeeLength/2))

    mw_in = W1 - 2 * thickness
    mh_in = D1 - 2 * thickness
    main_in = Part.makeBox(mw_in, mh_in, TeeLength + 2)
    main_in.translate(FreeCAD.Vector(-mw_in/2, -mh_in/2, -(TeeLength + 2)/2))

    embed = min(0.1, thickness / 2.0)
    start_x_out = (W3 / 2.0) - embed

    branch_out = Part.makeBox(TeeLength + embed, D3, W3)
    branch_out.translate(FreeCAD.Vector(start_x_out, -D3/2, -W3/2))

    start_x_in = (W1 / 2.0) - thickness - 1.0
    bw_in = W3 - 2 * thickness
    bh_in = D3 - 2 * thickness

    branch_in = Part.makeBox(TeeLength + thickness + 2.0, bh_in, bw_in)
    branch_in.translate(FreeCAD.Vector(start_x_in, -bh_in/2, -bw_in/2))

    outer_shell = main_out.fuse([branch_out])
    inner_void = main_in.fuse([branch_in])
    final_duct = outer_shell.cut(inner_void).removeSplitter()

    # ORIENTATION: Align from Legacy (Trunk Z, Depth Y) to Canonical (Trunk -Y, Depth Z)
    rot_mat = FreeCAD.Matrix(1, 0, 0, 0,
                             0, 0, 1, 0,
                             0,-1, 0, 0,
                             0, 0, 0, 1)
    final_duct = final_duct.transformGeometry(rot_mat)
    final_duct.Placement = placement
    return final_duct

def build_offset(center, normal, up_vec, w1, d1, w2, d2, distance, length, construction="Smooth", thickness=0, profile="Rectangular", corner_radius=0):
    # ORIENTATION: Save world inputs
    world_center, world_normal, world_up = center, normal, up_vec
    
    # ORIENTATION: Transform into local frame BEFORE generating geometry
    center = FreeCAD.Vector(0,0,0)
    normal = FreeCAD.Vector(0,1,0) # Trunk aligns to -Y, flow to +Y
    up_vec = FreeCAD.Vector(0,0,1) # Depth is Z

    O = distance
    L = length
    start_out = get_profile_wire(w1, d1, 0.0, center, normal, up_vec, profile, corner_radius)

    if construction in ["Mitered", "Segmented"] and abs(O) >= 0.1:
        P0 = center
        if construction == "Segmented":
            P1 = P0 + normal * (L / 3.0)
            P2 = P1 + normal * (L / 3.0) + up_vec * O
            P3 = P0 + normal * L + up_vec * O
        else:
            P1 = P0 + normal * (L / 2.0)
            P2 = P1 + up_vec * O
            P3 = P0 + normal * L + up_vec * O

        V_in = normal
        V_mid = (P2 - P1).normalize()
        V_out = normal

        local_X = up_vec.cross(normal).normalize()

        N1 = (V_in + V_mid).normalize()
        theta1 = V_in.getAngle(V_mid)
        stretch1 = 1.0 / math.cos(theta1 / 2.0)
        up1 = N1.cross(local_X).normalize()

        N2 = (V_mid + V_out).normalize()
        theta2 = V_mid.getAngle(V_out)
        stretch2 = 1.0 / math.cos(theta2 / 2.0)
        up2 = N2.cross(local_X).normalize()

        prof_0_out = get_profile_wire(w1, d1, 0.0, P0, V_in, up_vec, profile, corner_radius)
        prof_1_out = get_profile_wire(w1, d1 * stretch1, 0.0, P1, N1, up1, profile, corner_radius)
        prof_2_out = get_profile_wire(w2, d2 * stretch2, 0.0, P2, N2, up2, profile, corner_radius)
        prof_3_out = get_profile_wire(w2, d2, 0.0, P3, V_out, up_vec, profile, corner_radius)

        prof_0_in = get_profile_wire(w1, d1, thickness, P0, V_in, up_vec, profile, corner_radius)
        prof_1_in = get_profile_wire(w1, d1 * stretch1, thickness, P1, N1, up1, profile, corner_radius)
        prof_2_in = get_profile_wire(w2, d2 * stretch2, thickness, P2, N2, up2, profile, corner_radius)
        prof_3_in = get_profile_wire(w2, d2, thickness, P3, V_out, up_vec, profile, corner_radius)

        seg1_out = Part.makeLoft([prof_0_out, prof_1_out], True, True)
        seg2_out = Part.makeLoft([prof_1_out, prof_2_out], True, True)
        seg3_out = Part.makeLoft([prof_2_out, prof_3_out], True, True)
        outer = seg1_out.fuse([seg2_out, seg3_out]).removeSplitter()

        seg1_in = Part.makeLoft([prof_0_in, prof_1_in], True, True)
        seg2_in = Part.makeLoft([prof_1_in, prof_2_in], True, True)
        seg3_in = Part.makeLoft([prof_2_in, prof_3_in], True, True)
        inner = seg1_in.fuse([seg2_in, seg3_in])

        ext_in_start = Part.Face(prof_0_in).extrude(V_in * -5.0)
        ext_in_end = Part.Face(prof_3_in).extrude(V_out * 5.0)
        inner = inner.fuse([ext_in_start, ext_in_end])

        final_solid = outer.cut(inner.removeSplitter())
    else:
        if abs(O) < 0.1:
            start_in = get_profile_wire(w1, d1, thickness, center, normal, up_vec, profile, corner_radius)
            P_end = center + normal * L
            end_out = get_profile_wire(w2, d2, 0.0, P_end, normal, up_vec, profile, corner_radius)
            end_in = get_profile_wire(w2, d2, thickness, P_end, normal, up_vec, profile, corner_radius)
            outer_solid = Part.makeLoft([start_out, end_out], True, False)
            inner_solid = Part.makeLoft([start_in, end_in], True, False)
            final_solid = outer_solid.cut(inner_solid)
        else:
            R_val = (O**2 + L**2) / (4.0 * abs(O))
            P_mid = center + normal * (L/2.0) + up_vec * (O/2.0)
            P_end = center + normal * L + up_vec * O

            C1_arc = center + up_vec * math.copysign(R_val, O)
            C2_arc = P_end - up_vec * math.copysign(R_val, O)

            v1_s = center - C1_arc
            v1_e = P_mid - C1_arc
            v1_m = (v1_s + v1_e).normalize() * R_val
            arc1 = Part.Arc(center, C1_arc + v1_m, P_mid).toShape()

            v2_s = P_mid - C2_arc
            v2_e = P_end - C2_arc
            v2_m = (v2_s + v2_e).normalize() * R_val
            arc2 = Part.Arc(P_mid, C2_arc + v2_m, P_end).toShape()

            local_X = up_vec.cross(normal).normalize()
            profs_out = []
            profs_in = []
            steps = 6

            arc1_p0   = arc1.FirstParameter
            arc1_span = arc1.LastParameter - arc1_p0
            arc2_p0   = arc2.FirstParameter
            arc2_span = arc2.LastParameter - arc2_p0

            for i in range(steps):
                t        = i / float(steps)
                p_cur    = arc1.valueAt(arc1_p0 + t * arc1_span)
                norm_cur = arc1.tangentAt(arc1_p0 + t * arc1_span).normalize()
                if norm_cur.dot(normal) < 0: norm_cur = -norm_cur

                up_cur = norm_cur.cross(local_X).normalize()
                if up_cur.dot(up_vec) < 0: up_cur = -up_cur

                global_frac = t * 0.5
                w_cur = w1 + (w2 - w1) * global_frac
                d_cur = d1 + (d2 - d1) * global_frac

                profs_out.append(get_profile_wire(w_cur, d_cur, 0.0,       p_cur, norm_cur, up_cur, profile, corner_radius))
                profs_in.append( get_profile_wire(w_cur, d_cur, thickness,  p_cur, norm_cur, up_cur, profile, corner_radius))

            for i in range(steps + 1):
                t        = i / float(steps)
                p_cur    = arc2.valueAt(arc2_p0 + t * arc2_span)
                norm_cur = arc2.tangentAt(arc2_p0 + t * arc2_span).normalize()
                if norm_cur.dot(normal) < 0: norm_cur = -norm_cur

                up_cur = norm_cur.cross(local_X).normalize()
                if up_cur.dot(up_vec) < 0: up_cur = -up_cur

                global_frac = 0.5 + t * 0.5
                w_cur = w1 + (w2 - w1) * global_frac
                d_cur = d1 + (d2 - d1) * global_frac

                profs_out.append(get_profile_wire(w_cur, d_cur, 0.0,       p_cur, norm_cur, up_cur, profile, corner_radius))
                profs_in.append( get_profile_wire(w_cur, d_cur, thickness,  p_cur, norm_cur, up_cur, profile, corner_radius))

            outer_solid = Part.makeLoft(profs_out, True, False)
            inner_solid = Part.makeLoft(profs_in, True, False)
            final_solid = outer_solid.cut(inner_solid)

    # ORIENTATION: Apply inverse frame transform
    forward, right, up = _compute_fitting_frame(world_normal, world_up)
    m = FreeCAD.Matrix(right.x, forward.x, up.x, world_center.x,
                       right.y, forward.y, up.y, world_center.y,
                       right.z, forward.z, up.z, world_center.z,
                       0, 0, 0, 1)
    final_solid.Placement = FreeCAD.Placement(m)
    return final_solid

def build_route(w1, d1, w2, d2, w3, d3, w4, d4, thickness, profile, construction, corner_radius, bend_radius, vanes_count, path_obj_list, gores=5, tee_type="Straight Tee", main_length=0.1, branch_length=0.1):
    if not path_obj_list: return None
    edges = []
    for item in path_obj_list:
        obj = item[0] if isinstance(item, (tuple, list)) else item
        subnames = item[1] if isinstance(item, (tuple, list)) and len(item) > 1 else []
        if isinstance(subnames, str): subnames = [subnames]
        if not obj or not hasattr(obj, "Shape"): continue
        if subnames:
            for subname in subnames:
                try:
                    shape = obj.Shape.getElement(subname)
                    if hasattr(shape, "Edges"): edges.extend(shape.Edges)
                    elif shape.ShapeType == "Edge": edges.append(shape)
                except: pass
        else:
            try:
                if hasattr(obj.Shape, "Edges"): edges.extend(obj.Shape.Edges)
            except: pass

    if not edges: return None

    raw_lines = []
    for edge in edges:
        if hasattr(edge, "Curve") and 'Line' in str(type(edge.Curve).__name__):
            raw_lines.append((edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)))
        elif hasattr(edge, "Vertexes") and len(edge.Vertexes) >= 2:
            raw_lines.append((edge.Vertexes[0].Point, edge.Vertexes[-1].Point))
    if not raw_lines: return None

    route_up = FreeCAD.Vector(0,0,1)
    found_plane = False
    for i in range(len(raw_lines)):
        for j in range(i+1, len(raw_lines)):
            v1 = (raw_lines[i][1] - raw_lines[i][0]).normalize()
            v2 = (raw_lines[j][1] - raw_lines[j][0]).normalize()
            cv = v1.cross(v2)
            if cv.Length > 0.01:
                route_up = cv.normalize()
                found_plane = True; break
        if found_plane: break
    if route_up.z < 0 and abs(route_up.z) > 0.5: route_up = -route_up

    TOLERANCE = 1.0
    nodes = []
    def get_node_id(pt):
        for i, n in enumerate(nodes):
            if (pt - n).Length < TOLERANCE: return i
        nodes.append(pt)
        return len(nodes) - 1

    vertices = {}
    edge_sizes = {}
    mapped_lines = []
    orig_dirs = {}

    for p1, p2 in raw_lines:
        n1 = get_node_id(p1)
        n2 = get_node_id(p2)
        if n1 != n2:
            mapped_lines.append((n1, n2))
            if n1 not in vertices: vertices[n1] = {'pt': nodes[n1], 'vecs': [], 'neighbors': []}
            if n2 not in vertices: vertices[n2] = {'pt': nodes[n2], 'vecs': [], 'neighbors': []}
            v_1to2 = (nodes[n2] - nodes[n1]).normalize()
            v_2to1 = (nodes[n1] - nodes[n2]).normalize()
            orig_dirs[(n1, n2)] = v_1to2
            orig_dirs[(n2, n1)] = v_2to1
            vertices[n1]['vecs'].append(v_1to2); vertices[n1]['neighbors'].append(n2)
            vertices[n2]['vecs'].append(v_2to1); vertices[n2]['neighbors'].append(n1)
            edge_sizes[tuple(sorted([n1, n2]))] = (w1, d1)

    shapes = []
    pullbacks = {}
    custom_ports = {}
    shifts = []

    for node_id, data in vertices.items():
        pt = data['pt']; vecs = data['vecs']; neighbors = data['neighbors']
        degree = len(vecs)

        if degree == 3 or degree == 4:
            v_col1 = None; v_col2 = None; v_perp = None
            for i in range(degree):
                for j in range(i+1, degree):
                    if abs(vecs[i].getAngle(vecs[j]) - math.pi) < 0.1:
                        v_col1 = vecs[i]; v_col2 = vecs[j]
                        branches = [v for k, v in enumerate(vecs) if k not in (i,j)]
                        v_perp = branches[0] if branches else None
                        break
                if v_col1: break

            bullhead_types = ["Y-Branch", "Rectangular Dovetail Wye", "Rectangular Wye", "Circular Wye"]

            if v_col1 and v_perp:
                if any(b in tee_type for b in bullhead_types):
                    v_m2 = v_perp; v_b1 = v_col1
                else:
                    v_m2 = v_col2; v_b1 = v_perp
            else:
                min_ang = 999; b1 = 0; b2 = 1
                for i in range(degree):
                    for j in range(i+1, degree):
                        ang = vecs[i].getAngle(vecs[j])
                        if ang < min_ang: min_ang = ang; b1 = i; b2 = j
                trunk_idx = [k for k in range(3) if k not in (b1, b2)][0]
                v_m2 = vecs[trunk_idx]; v_b1 = vecs[b1]

            base_normal = -v_m2.normalize()
            temp_up = route_up if route_up.Length > 0.001 else FreeCAD.Vector(0,0,1)
            
            base_x = base_normal.cross(temp_up).normalize()
            if base_x.Length < 0.001: 
                base_x = FreeCAD.Vector(1,0,0)
                
            sketch_normal = base_x.cross(base_normal).normalize()

            br_ang = 90.0 if not v_b1 else math.degrees(base_normal.getAngle(v_b1))
            is_branch_right = v_b1.dot(base_x) > 0 if v_b1 else False

            br_ang = 90.0 if not v_b1 else math.degrees(base_normal.getAngle(v_b1))
            is_branch_right = v_b1.dot(base_x) > 0 if v_b1 else False
            
            if degree == 3 and not any(b in tee_type for b in bullhead_types):
                if not is_branch_right:
                    sketch_normal = -sketch_normal
                    base_x = -base_x

            br_rad = min(w1, w3) * 0.5
            t_len = main_length if main_length > 0.001 else 0.1
            b_len = branch_length if branch_length > 0.001 else 0.1
            
           # // STEP: Set correct center for fittings so branches align with sketch lines
            if "Dovetail" in tee_type:
                t_center = pt - base_normal * w1
            elif "Y-Branch" in tee_type:
                w_b_max = max(w3, w4)
                R_center_max = br_rad + (w_b_max / 2.0)
                ang_rad = math.radians(br_ang)
                Y_shift = R_center_max * math.tan(ang_rad / 2.0) - (w_b_max / 2.0) / math.tan(ang_rad) if ang_rad > 0.001 else 0.0
                t_center = pt - base_normal * Y_shift
            else:
                t_center = pt

            if any(b in tee_type for b in bullhead_types):
                for i, v in enumerate(vecs):
                    nbr = neighbors[i]
                    if abs(v.dot(base_normal)) > 0.9: 
                        # // STEP: Trunk pullback
                        if "Dovetail" in tee_type: pb_tee = w1 + t_len
                        elif "Y-Branch" in tee_type: 
                            w_b_max = max(w3, w4)
                            R_center_max = br_rad + (w_b_max / 2.0)
                            ang_rad = math.radians(br_ang)
                            Y_shift = R_center_max * math.tan(ang_rad / 2.0) - (w_b_max / 2.0) / math.tan(ang_rad) if ang_rad > 0.001 else 0.0
                            pb_tee = Y_shift + t_len
                        else: pb_tee = t_len / 2.0
                        pullbacks[(node_id, nbr)] = pb_tee
                        continue

                    is_right = v.dot(base_x) > 0
                    edge_sizes[tuple(sorted([node_id, nbr]))] = (w4, d4) if is_right else (w3, d3)
                    
                    # // STEP: Branch pullbacks for bullheads
                    if "Dovetail" in tee_type:
                        w_b = w4 if is_right else w3
                        pb_branch = 1.5 * w1 - (w_b / 2.0) + b_len
                    elif "Y-Branch" in tee_type:
                        w_b = w4 if is_right else w3
                        R_center = br_rad + (w_b / 2.0)
                        ang_rad = math.radians(br_ang)
                        Y_shift = R_center * math.tan(ang_rad / 2.0) - (w_b / 2.0) / math.tan(ang_rad) if ang_rad > 0.001 else 0.0
                        p_end_x = w_b / 2.0 + R_center * (1.0 - math.cos(ang_rad))
                        p_end_y = -Y_shift + R_center * math.sin(ang_rad)
                        dist = p_end_x * math.sin(ang_rad) + p_end_y * math.cos(ang_rad)
                        pb_branch = dist + b_len
                    else:
                        pb_branch = t_len + b_len
                    pullbacks[(node_id, nbr)] = pb_branch
            else:
                for i, v in enumerate(vecs):
                    nbr = neighbors[i]
                    edge_id = tuple(sorted([node_id, nbr]))
                    if abs(v.dot(base_normal)) > 0.9: 
                        pullbacks[(node_id, nbr)] = t_len / 2.0
                    else:
                        is_right = v.dot(base_x) > 0
                        edge_sizes[edge_id] = (w4, d4) if is_right else (w3, d3)

                        # v2.8.2 FIX: Removed custom_ports for Converging Wye to keep sketch lines as centerlines

                        if "Angled Branch" in tee_type:
                            hyp = (w1 / 2.0) / math.sin(math.radians(br_ang)) if br_ang > 0.1 else 0
                            pullbacks[(node_id, nbr)] = hyp + ((w4 if is_right else w3) / 2.0) + b_len
                        else:
                            pullbacks[(node_id, nbr)] = (w1 / 2.0) + b_len

            t_style = tee_type if degree == 3 else "Cross Tee"
            try:
                tee = build_tee(t_center, base_normal, sketch_normal, base_x, w1, d1, w2, d2, w3, d3, w4, d4, t_style, br_ang, br_rad, t_len, thickness, profile, corner_radius, vanes_count)
                if tee: shapes.append(tee)
            except: pass

    tee_groups = {}
    for t_node, b_node, s_vec in shifts:
        if t_node not in tee_groups: tee_groups[t_node] = []
        tee_groups[t_node].append((b_node, s_vec))

    for t_node, branch_shifts in tee_groups.items():
        visited = {t_node}
        for b_node, s_vec in branch_shifts:
            queue = deque([b_node])
            while queue:
                curr = queue.popleft()
                if curr not in visited:
                    visited.add(curr)
                    nodes[curr] = nodes[curr] + s_vec
                    vertices[curr]['pt'] = nodes[curr]
                    for nbr in vertices[curr]['neighbors']:
                        if nbr not in visited: queue.append(nbr)

    for node_id, data in vertices.items():
        pt = data['pt']; vecs = data['vecs']; neighbors = data['neighbors']
        degree = len(vecs)
        if degree == 2:
            v_in = -vecs[0]; v_out = vecs[1]
            angle_deg = math.degrees(v_in.getAngle(v_out))
            if angle_deg < 0.1 or abs(angle_deg - 180) < 0.1:
                continue

            nbr1 = None; nbr2 = None
            for n in neighbors:
                if orig_dirs[(node_id, n)].getAngle(vecs[0]) < 0.01: nbr1 = n
                elif orig_dirs[(node_id, n)].getAngle(vecs[1]) < 0.01: nbr2 = n

            cross_vec = v_in.cross(v_out)
            elbow_up = cross_vec.normalize() if cross_vec.Length > 0.001 else route_up

            w_e1, d_e1 = edge_sizes[tuple(sorted([node_id, nbr1]))] if nbr1 is not None else edge_sizes[tuple(sorted([node_id, neighbors[0]]))]
            w_e2, d_e2 = edge_sizes[tuple(sorted([node_id, nbr2]))] if nbr2 is not None else edge_sizes[tuple(sorted([node_id, neighbors[0]]))]
            w_max = max(w_e1, w_e2)

            if construction == "Smooth":
                r = w_max * 1.0
            elif construction == "Segmented":
                r = max(bend_radius, (w_max / 2.0) + 0.1)
            else:
                r = max(bend_radius, w_max / 2.0)
                
            pb = r * math.tan(math.radians(angle_deg) / 2.0)

            if nbr1 is not None: pullbacks[(node_id, nbr1)] = pb
            if nbr2 is not None: pullbacks[(node_id, nbr2)] = pb

            # UNIFIED ARCHITECTURE: All elbows anchor identically to the Pullback
            p_elbow_start = pt - v_in * pb
            try:
                elbow = build_elbow(p_elbow_start, v_in, elbow_up, w_e1, d_e1, w_e2, d_e2, angle_deg, r, construction, gores, vanes_count, thickness, profile, corner_radius)
                if elbow: shapes.append(elbow)
            except: pass

    processed_edges = set()
    for n1, n2 in mapped_lines:
        edge_id = tuple(sorted([n1, n2]))
        if edge_id in processed_edges: continue
        processed_edges.add(edge_id)

        v_dir_orig = orig_dirs[(n1, n2)]

        if (n1, n2) in custom_ports: p_start, v_dir_eff = custom_ports[(n1, n2)]
        else:
            p_start = nodes[n1] + v_dir_orig * pullbacks.get((n1, n2), 0.0)
            v_dir_eff = v_dir_orig

        if (n2, n1) in custom_ports: p_end, _ = custom_ports[(n2, n1)]
        else:
            p_end = nodes[n2] - v_dir_eff * pullbacks.get((n2, n1), 0.0)

        vec_span = p_end - p_start
        length = vec_span.Length

        if length > 0.01:
            w_edge, d_edge = edge_sizes[edge_id]
            v_dir_actual = vec_span.normalize()

            straight_up = route_up - route_up.dot(v_dir_actual) * v_dir_actual
            if straight_up.Length < 0.001: straight_up = FreeCAD.Vector(0,0,1)
            else: straight_up.normalize()

            try:
                straight = build_straight_duct(p_start, v_dir_actual, straight_up, w_edge, d_edge, w_edge, d_edge, length, thickness, profile, profile, corner_radius)
                if straight: shapes.append(straight)
            except: pass

    if not shapes: return None
    if len(shapes) == 1: return shapes[0]
    try: return Part.makeCompound(shapes)
    except: return shapes[0]

def build_tee_rect_angled_branch(center, normal, up_vec, w_m, h_m, w_b, h_b, angle_deg, L_m, branch_collar_length, thickness):
    # ORIENTATION: Universal Orientation Frame
    forward, right_dir, up = _compute_fitting_frame(normal, up_vec)
    m = FreeCAD.Matrix(right_dir.x, forward.x, up.x, center.x,
                       right_dir.y, forward.y, up.y, center.y,
                       right_dir.z, forward.z, up.z, center.z,
                       0, 0, 0, 1)
    placement = FreeCAD.Placement(m)
    
    main_out = Part.makeBox(w_m, h_m, L_m)
    main_out.translate(FreeCAD.Vector(-w_m/2.0, -h_m/2.0, -L_m/2.0))

    dz = 2.0
    main_in = Part.makeBox(w_m - 2*thickness, h_m - 2*thickness, L_m + 2*dz)
    main_in.translate(FreeCAD.Vector(-(w_m - 2*thickness)/2.0, -(h_m - 2*thickness)/2.0, -L_m/2.0 - dz))

    angle_rad = math.radians(angle_deg)
    dist_to_wall = (w_m / 2.0) / math.sin(angle_rad)
    total_branch_len = dist_to_wall + (w_b / 2.0) + branch_collar_length

    branch_out = Part.makeBox(w_b, h_b, total_branch_len)
    branch_out.translate(FreeCAD.Vector(-w_b/2.0, -h_b/2.0, 0))

    branch_in = Part.makeBox(w_b - 2*thickness, h_b - 2*thickness, total_branch_len + 2*dz)
    branch_in.translate(FreeCAD.Vector(-(w_b - 2*thickness)/2.0, -(h_b - 2*thickness)/2.0, -dz))

    rot_angle = 180.0 - angle_deg
    branch_out.rotate(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,1,0), rot_angle)
    branch_in.rotate(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,1,0), rot_angle)

    outer_shell = main_out.fuse([branch_out])
    inner_void = main_in.fuse([branch_in])

    final_duct = outer_shell.cut(inner_void).removeSplitter()
    
    # ORIENTATION: Align from Legacy (Trunk Z, Depth Y) to Canonical (Trunk -Y, Depth Z)
    rot_mat = FreeCAD.Matrix(1, 0, 0, 0,
                             0, 0, 1, 0,
                             0,-1, 0, 0,
                             0, 0, 0, 1)
    final_duct = final_duct.transformGeometry(rot_mat)
    final_duct.Placement = placement

    return final_duct

def make_rect_face(x_min, x_max, y_min, y_max, z):
    p1 = FreeCAD.Vector(x_min, y_min, z)
    p2 = FreeCAD.Vector(x_max, y_min, z)
    p3 = FreeCAD.Vector(x_max, y_max, z)
    p4 = FreeCAD.Vector(x_min, y_max, z)
    wire = Part.makePolygon([p1, p2, p3, p4, p1])
    return Part.Face(wire)

def build_dovetail_wye(center, normal, up_vec, W, D, W3, D3, W4, D4, length, branch_length, thickness):
    """
    Builds a True Swept Collinear Dovetail Wye using robust Primitives (Revolves).
    Adapts independently to branch sizes (W3 x D3 and W4 x D4) without using Lofts.
    """
    forward, right_dir, up = _compute_fitting_frame(normal, up_vec)
    m = FreeCAD.Matrix(right_dir.x, forward.x, up.x, center.x,
                       right_dir.y, forward.y, up.y, center.y,
                       right_dir.z, forward.z, up.z, center.z,
                       0, 0, 0, 1)
    placement = FreeCAD.Placement(m)
    
    L_m = max(float(length), 0.1)
    L_b = max(float(branch_length), 0.1)
    t = thickness
    dz = 2.0

    # 1. Trunk Block
    trunk_out = Part.makeBox(W, L_m, D)
    trunk_out.translate(FreeCAD.Vector(-W/2.0, -L_m, -D/2.0))
    
    W_in = max(W - 2*t, 0.1)
    D_in = max(D - 2*t, 0.1)
    trunk_in = Part.makeBox(W_in, L_m + dz, D_in)
    trunk_in.translate(FreeCAD.Vector(-W_in/2.0, -L_m - dz/2.0, -D_in/2.0))

    def make_xz_face(x_min, x_max, z_min, z_max):
        # Creates a profile face on the XZ plane to be revolved around the Z axis
        p1 = FreeCAD.Vector(x_min, 0, z_min)
        p2 = FreeCAD.Vector(x_max, 0, z_min)
        p3 = FreeCAD.Vector(x_max, 0, z_max)
        p4 = FreeCAD.Vector(x_min, 0, z_max)
        return Part.Face(Part.makePolygon([p1, p2, p3, p4, p1]))

    # --- 2. Right Branch (W4, D4) ---
    W4_in = max(W4 - 2*t, 0.1)
    D4_in = max(D4 - 2*t, 0.1)
    R_in_R = W - W4/2.0
    R_out_R = W + W4/2.0 + 0.1 # 0.1mm overlap prevents boolean kissing-edge crashes at the crotch
    C_R_x = W/2.0 + R_in_R

    face_r_out = make_xz_face(C_R_x - R_out_R, C_R_x - R_in_R, -D4/2.0, D4/2.0)
    curve_r_out = face_r_out.revolve(FreeCAD.Vector(C_R_x, 0, 0), FreeCAD.Vector(0,0,1), -90)

    face_r_in = make_xz_face(C_R_x - R_out_R + t, C_R_x - R_in_R - t, -D4_in/2.0, D4_in/2.0)
    curve_r_in = face_r_in.revolve(FreeCAD.Vector(C_R_x, 0, 0), FreeCAD.Vector(0,0,1), -90)

    collar_r_out = Part.makeBox(L_b, W4, D4)
    collar_r_out.translate(FreeCAD.Vector(C_R_x, R_in_R, -D4/2.0))

    collar_r_in = Part.makeBox(L_b + dz, W4_in, D4_in)
    collar_r_in.translate(FreeCAD.Vector(C_R_x - dz/2.0, R_in_R + t, -D4_in/2.0))

    # --- 3. Left Branch (W3, D3) ---
    W3_in = max(W3 - 2*t, 0.1)
    D3_in = max(D3 - 2*t, 0.1)
    R_in_L = W - W3/2.0
    R_out_L = W + W3/2.0 + 0.1 # 0.1mm overlap
    C_L_x = -W/2.0 - R_in_L

    face_l_out = make_xz_face(C_L_x + R_in_L, C_L_x + R_out_L, -D3/2.0, D3/2.0)
    curve_l_out = face_l_out.revolve(FreeCAD.Vector(C_L_x, 0, 0), FreeCAD.Vector(0,0,1), 90)

    face_l_in = make_xz_face(C_L_x + R_in_L + t, C_L_x + R_out_L - t, -D3_in/2.0, D3_in/2.0)
    curve_l_in = face_l_in.revolve(FreeCAD.Vector(C_L_x, 0, 0), FreeCAD.Vector(0,0,1), 90)

    collar_l_out = Part.makeBox(L_b, W3, D3)
    collar_l_out.translate(FreeCAD.Vector(C_L_x - L_b, R_in_L, -D3/2.0))

    collar_l_in = Part.makeBox(L_b + dz, W3_in, D3_in)
    collar_l_in.translate(FreeCAD.Vector(C_L_x - L_b - dz/2.0, R_in_L + t, -D3_in/2.0))

    # --- 4. Final Boolean Assembly ---
    outer_shell = trunk_out.fuse([curve_r_out, collar_r_out, curve_l_out, collar_l_out])
    inner_void = trunk_in.fuse([curve_r_in, collar_r_in, curve_l_in, collar_l_in])

    final_duct = outer_shell.cut(inner_void).removeSplitter()
    final_duct.Placement = placement
    return final_duct

def make_swept_branch_solid(W_b, H_b, L_b, R, t, embed, dz, is_inner=False):
    y = -H_b/2.0 + (t if is_inner else 0)
    h_ext = H_b - (2*t if is_inner else 0)

    R = max(R, t + 1.0)

    if not is_inner:
        p0 = FreeCAD.Vector(-embed, y, -W_b/2.0)
        p1 = FreeCAD.Vector(R + L_b, y, -W_b/2.0)
        p2 = FreeCAD.Vector(R + L_b, y, W_b/2.0)
        p3 = FreeCAD.Vector(R, y, W_b/2.0)

        p_mid = FreeCAD.Vector(R - R*math.cos(math.pi/4), y, W_b/2.0 + R - R*math.sin(math.pi/4))
        p4 = FreeCAD.Vector(0, y, W_b/2.0 + R)
        p5 = FreeCAD.Vector(-embed, y, W_b/2.0 + R)

        edges = [
            Part.makeLine(p0, p1),
            Part.makeLine(p1, p2),
            Part.makeLine(p2, p3),
            Part.Edge(Part.Arc(p3, p_mid, p4)),
            Part.makeLine(p4, p5),
            Part.makeLine(p5, p0)
        ]
    else:
        p0 = FreeCAD.Vector(-t - dz, y, -W_b/2.0 + t)
        p1 = FreeCAD.Vector(R + L_b + dz, y, -W_b/2.0 + t)
        p2 = FreeCAD.Vector(R + L_b + dz, y, W_b/2.0 - t)
        p3 = FreeCAD.Vector(R, y, W_b/2.0 - t)

        R_in = R + t
        p_mid = FreeCAD.Vector(R - R_in*math.cos(math.pi/4), y, W_b/2.0 + R - R_in*math.sin(math.pi/4))

        p4 = FreeCAD.Vector(-t, y, W_b/2.0 + R)
        p5 = FreeCAD.Vector(-t - dz, y, W_b/2.0 + R)

        edges = [
            Part.makeLine(p0, p1),
            Part.makeLine(p1, p2),
            Part.makeLine(p2, p3),
            Part.Edge(Part.Arc(p3, p_mid, p4)),
            Part.makeLine(p4, p5),
            Part.makeLine(p5, p0)
        ]

    wire = Part.Wire(edges)
    face = Part.Face(wire)
    solid = face.extrude(FreeCAD.Vector(0, h_ext, 0))
    return solid

def make_yz_face(x, y_min, y_max, z_min, z_max):
    p1 = FreeCAD.Vector(x, y_min, z_min)
    p2 = FreeCAD.Vector(x, y_max, z_min)
    p3 = FreeCAD.Vector(x, y_max, z_max)
    p4 = FreeCAD.Vector(x, y_min, z_max)
    wire = Part.makePolygon([p1, p2, p3, p4, p1])
    return Part.Face(wire)

def build_converging_wye_elbow(center, normal, up_vec, W_m, H_m, W_b, H_b, R, L_m, L_b, thickness):
    # ORIENTATION: Universal Orientation Frame
    forward, right_dir, up = _compute_fitting_frame(normal, up_vec)
    m = FreeCAD.Matrix(right_dir.x, forward.x, up.x, center.x,
                       right_dir.y, forward.y, up.y, center.y,
                       right_dir.z, forward.z, up.z, center.z,
                       0, 0, 0, 1)
    placement = FreeCAD.Placement(m)
    
    t = thickness
    dz = 2.0

    main_out = Part.makeBox(W_m, H_m, L_m)
    main_out.translate(FreeCAD.Vector(-W_m/2.0, -H_m/2.0, -L_m/2.0))

    main_in = Part.makeBox(W_m - 2*t, H_m - 2*t, L_m + 2*dz)
    main_in.translate(FreeCAD.Vector(-W_m/2.0 + t, -H_m/2.0 + t, -L_m/2.0 - dz))

    C_x = W_m/2.0 + R

    face_out = make_yz_face(C_x, -H_b/2.0, H_b/2.0, -R - W_b, -R)
    curve_out = face_out.revolve(FreeCAD.Vector(C_x, 0, 0), FreeCAD.Vector(0, 1, 0), 90)

    face_in = make_yz_face(C_x, -H_b/2.0 + t, H_b/2.0 - t, -R - W_b + t, -R - t)
    curve_in = face_in.revolve(FreeCAD.Vector(C_x, 0, 0), FreeCAD.Vector(0, 1, 0), 90)

    collar_out = Part.makeBox(L_b, H_b, W_b)
    collar_out.translate(FreeCAD.Vector(C_x, -H_b/2.0, -R - W_b))

    collar_in = Part.makeBox(L_b + dz, H_b - 2*t, W_b - 2*t)
    collar_in.translate(FreeCAD.Vector(C_x - dz, -H_b/2.0 + t, -R - W_b + t))

    outer_shell = main_out.fuse([curve_out, collar_out])
    inner_void = main_in.fuse([curve_in, collar_in])

    final_duct = outer_shell.cut(inner_void).removeSplitter()
    
    # ORIENTATION: Align from Legacy (Trunk Z, Depth Y) to Canonical (Trunk -Y, Depth Z)
    rot_mat = FreeCAD.Matrix(1, 0, 0, 0,
                             0, 0, 1, 0,
                             0,-1, 0, 0,
                             0, 0, 0, 1)
    final_duct = final_duct.transformGeometry(rot_mat)
    final_duct.Placement = placement

    return final_duct

def get_wye_polygon(main_w, branch_w, main_l, branch_l, angle_deg):
    theta = math.radians(angle_deg)

    p_main_tl = FreeCAD.Vector(-main_w/2, main_l, 0)
    p_main_tr = FreeCAD.Vector(main_w/2, main_l, 0)
    p_split_l = FreeCAD.Vector(-main_w/2, 0, 0)
    p_split_r = FreeCAD.Vector(main_w/2, 0, 0)

    dx_out = branch_l * math.sin(theta)
    dy_out = branch_l * math.cos(theta)
    p_b1_out = FreeCAD.Vector(main_w/2 + dx_out, -dy_out, 0)

    dx_in = branch_w * math.cos(theta)
    dy_in = branch_w * math.sin(theta)
    p_b1_in = FreeCAD.Vector(p_b1_out.x - dx_in, p_b1_out.y - dy_in, 0)

    p_b2_out = FreeCAD.Vector(-main_w/2 - dx_out, -dy_out, 0)
    p_b2_in = FreeCAD.Vector(p_b2_out.x + dx_in, p_b2_out.y - dy_in, 0)

    y_crotch = p_b1_in.y + (p_b1_in.x / math.tan(theta))
    p_crotch = FreeCAD.Vector(0, y_crotch, 0)

    return Part.makePolygon([
        p_main_tl, p_main_tr, p_split_r, p_b1_out, p_b1_in,
        p_crotch,
        p_b2_in, p_b2_out, p_split_l, p_main_tl
    ])

def build_rectangular_wye_geometry(main_w, branch_w, height, main_l, branch_l, angle_deg, thickness):
    outer_wire = get_wye_polygon(
        main_w + 2*thickness,
        branch_w + 2*thickness,
        main_l,
        branch_l,
        angle_deg
    )
    outer_solid = Part.Face(outer_wire).extrude(FreeCAD.Vector(0, 0, height + 2*thickness))
    outer_solid.translate(FreeCAD.Vector(0, 0, -thickness))

    cut_overshoot = thickness + 5.0
    void_wire = get_wye_polygon(
        main_w,
        branch_w,
        main_l + cut_overshoot,
        branch_l + cut_overshoot,
        angle_deg
    )
    void_solid = Part.Face(void_wire).extrude(FreeCAD.Vector(0, 0, height))

    duct_shell = outer_solid.cut(void_solid)
    
    # ORIENTATION: Align to Canonical Local Frame (Trunk -Y, Branches +Y)
    # Legacy builds Trunk +Y, Branches -Y. Rotate 180 around Z.
    rot_180 = FreeCAD.Matrix(-1, 0, 0, 0,
                              0,-1, 0, 0,
                              0, 0, 1, 0,
                              0, 0, 0, 1)
    duct_shell = duct_shell.transformGeometry(rot_180)
    return duct_shell

def build_circular_wye(D_main, D_b1, D_b2, L_trans, L_collar, theta_1, theta_2, thickness):
    R_mo = D_main / 2.0;  R_mi = R_mo - thickness
    R_1o = D_b1  / 2.0;   R_1i = max(0.1, R_1o - thickness)
    R_2o = D_b2  / 2.0;   R_2i = max(0.1, R_2o - thickness)

    UP  = FreeCAD.Vector(0, 0, 1)
    eps = 0.0

    def get_dir(angle_deg):
        rad = math.radians(angle_deg)
        return FreeCAD.Vector(math.cos(rad), math.sin(rad), 0)

    def frame(normal):
        n    = normal.normalize()
        proj = n.dot(UP)
        e1   = FreeCAD.Vector(UP.x - n.x*proj, UP.y - n.y*proj, UP.z - n.z*proj)
        if e1.Length < 1e-6:
            e1 = FreeCAD.Vector(0, 1, 0)
        e1 = e1.normalize()
        e2 = n.cross(e1).normalize()
        return e1, e2

    def make_4arc_wire(center, normal, radius):
        e1, e2 = frame(normal)
        edges  = []
        for q in range(4):
            a0, a1 = q * math.pi/2, (q+1) * math.pi/2
            am = (a0 + a1) / 2.0
            def pt(a, _e1=e1, _e2=e2, _c=center, _r=radius):
                ca, sa = math.cos(a), math.sin(a)
                return FreeCAD.Vector(
                    _c.x + _r*(ca*_e1.x + sa*_e2.x),
                    _c.y + _r*(ca*_e1.y + sa*_e2.y),
                    _c.z + _r*(ca*_e1.z + sa*_e2.z),
                )
            edges.append(Part.Arc(pt(a0), pt(am), pt(a1)).toShape())
        return Part.Wire(edges)

    def loft_solid(c1, n1, r1, c2, n2, r2):
        return Part.makeLoft(
            [make_4arc_wire(c1, n1, r1),
             make_4arc_wire(c2, n2, r2)],
            True, False
        )

    def make_cyl(radius, length, pos, angle_deg):
        cyl = Part.makeCylinder(radius, length)
        rot = (FreeCAD.Rotation(FreeCAD.Vector(0,0,1), angle_deg)
               * FreeCAD.Rotation(FreeCAD.Vector(0,1,0), 90))
        cyl.Placement = FreeCAD.Placement(pos, rot)
        return cyl

    dir_m = get_dir(0)
    dir_1 = get_dir(theta_1)
    dir_2 = get_dir(theta_2)

    origin = FreeCAD.Vector(0, 0, 0)
    pos_b1 = FreeCAD.Vector(dir_1.x*L_trans, dir_1.y*L_trans, 0)
    pos_b2 = FreeCAD.Vector(dir_2.x*L_trans, dir_2.y*L_trans, 0)

    cb1_start = FreeCAD.Vector(pos_b1.x - dir_1.x*eps, pos_b1.y - dir_1.y*eps, 0)
    cb2_start = FreeCAD.Vector(pos_b2.x - dir_2.x*eps, pos_b2.y - dir_2.y*eps, 0)

    trunk_o  = make_cyl(R_mo, L_collar + eps, FreeCAD.Vector(-L_collar, 0, 0), 0)
    loft1_o  = loft_solid(origin, dir_m, R_mo, pos_b1, dir_1, R_1o)
    loft2_o  = loft_solid(origin, dir_m, R_mo, pos_b2, dir_2, R_2o)
    col_b1_o = make_cyl(R_1o, L_collar + eps, cb1_start, theta_1)
    col_b2_o = make_cyl(R_2o, L_collar + eps, cb2_start, theta_2)

    outer = trunk_o.fuse([loft1_o, loft2_o, col_b1_o, col_b2_o])

    trunk_i  = make_cyl(R_mi, L_collar + eps, FreeCAD.Vector(-L_collar, 0, 0), 0)
    loft1_i  = loft_solid(origin, dir_m, R_mi, pos_b1, dir_1, R_1i)
    loft2_i  = loft_solid(origin, dir_m, R_mi, pos_b2, dir_2, R_2i)
    col_b1_i = make_cyl(R_1i, L_collar + eps, cb1_start, theta_1)
    col_b2_i = make_cyl(R_2i, L_collar + eps, cb2_start, theta_2)

    inner = trunk_i.fuse([loft1_i, loft2_i, col_b1_i, col_b2_i])

    final_duct = outer.cut(inner).removeSplitter()
    
    # ORIENTATION: Align to Canonical Local Frame (Trunk -Y, Branches +Y)
    # Legacy builds Trunk X, Branches X.
    rot_90 = FreeCAD.Matrix(0, 1, 0, 0,
                            1, 0, 0, 0,
                            0, 0,-1, 0,
                            0, 0, 0, 1)
    final_duct = final_duct.transformGeometry(rot_90)
    return final_duct