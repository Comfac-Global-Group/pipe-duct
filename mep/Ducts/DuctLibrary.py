import FreeCAD as App
import FreeCADGui as Gui
import Part
import math

try:
    import Ducts.DuctGeometryUtils as DuctGeometryUtils
    from Ducts.DuctGeometryUtils import (
        build_straight_duct,
        build_elbow,
        build_tee,
        build_offset,
        build_converging_wye_round_junction,
        build_tee_rect_main_round_branch,
        build_tee_rect_main_rect_branch,
        build_tee_rect_angled_branch,
        build_dovetail_wye,
        build_converging_wye_elbow,
        build_wye_conical_with_collars,
        build_rectangular_wye_geometry,
        build_drop_elbow,
        build_circular_wye,
        CATEGORIES, PROFILES, CONSTRUCTIONS, TEE_TYPES
    )
except ImportError:
    App.Console.PrintError("Error: Could not find DuctGeometryUtils.py. Ensure it is in the same directory.\n")
    build_straight_duct = None
    build_elbow = None
    build_tee = None
    build_offset = None
    build_converging_wye_round_junction = None
    build_tee_rect_main_round_branch = None
    build_tee_rect_main_rect_branch = None
    build_tee_rect_angled_branch = None
    build_dovetail_wye = None
    build_converging_wye_elbow = None
    build_wye_conical_with_collars = None
    build_rectangular_wye_geometry = None
    build_drop_elbow = None
    build_circular_wye = None

from compat import QtWidgets, QtCore, QtGui

# ==============================================================================
# 1. GEOMETRY ENGINE (Wrapper)
# ==============================================================================
def build_duct_shape(obj):
    def _f(val): return float(val.Value if hasattr(val, 'Value') else val)
    
    W = _f(obj.W1)
    D = _f(obj.D1) if obj.Profile != "Circular" else W
    T = _f(obj.Thickness)
    
    W2 = _f(obj.W2)
    D2 = _f(obj.D2) if getattr(obj, "Profile2", obj.Profile) != "Circular" else W2
    W3 = _f(obj.W3)
    D3 = _f(obj.D3) if obj.Profile != "Circular" else W3
    W4 = _f(obj.W4)
    D4 = _f(obj.D4) if obj.Profile != "Circular" else W4
    
    roll_ang = _f(obj.RollAngle)
    st_len = _f(obj.StraightLength)
    b_ang = _f(obj.BendAngle)
    b_rad = _f(obj.BendRadius)
    gores = int(obj.Gores)
    vanes_count = int(obj.SplitterVanes)
    br_ang = _f(obj.BranchAngle)
    br_rad = _f(obj.BranchRadius)
    t_len = _f(obj.TeeLength)
    off_dist = _f(obj.OffsetDist)
    off_len = _f(obj.OffsetLen)
    
    rot_roll = App.Rotation(obj.BaseNormal, roll_ang)
    rolled_X = rot_roll.multVec(obj.BaseX)
    rolled_Y = rot_roll.multVec(obj.BaseY)
    
    corner_rad = _f(obj.CornerRadius) if obj.Profile == "Rounded Rectangular" else 0.0  
        
    # --------------------------------------------------------------------------
    # v2.7.0: Simplified Straight/Transition Block (Baked Coordinates)
    # --------------------------------------------------------------------------
    if obj.Category in ["Straight", "Transitions"]:
        local_center = obj.BaseCenter
        local_len = st_len
        
        w_eff_1 = W; d_eff_1 = D
        w_eff_2 = W2 if obj.Category == "Transitions" else W
        d_eff_2 = D2 if obj.Category == "Transitions" else D
        
        if hasattr(obj, "IsRouted") and obj.IsRouted:
            # Absolute Coordinate Baking. No dynamic pullbacks required!
            local_center = obj.RouteP1
            # CRITICAL FIX: Enforce 1.0mm minimum length during live updates!
            local_len = max((obj.RouteP2 - obj.RouteP1).Length, 1.0) 

        align = getattr(obj, "Alignment", "Concentric") if obj.Category == "Transitions" else "Concentric"
        prof1 = obj.Profile
        prof2 = getattr(obj, "Profile2", prof1) if obj.Category == "Transitions" else prof1
        
        return build_straight_duct(local_center, obj.BaseNormal, rolled_Y, w_eff_1, d_eff_1, w_eff_2, d_eff_2, local_len, T, prof1, prof2, corner_rad, align)
        
    # --------------------------------------------------------------------------
    # ELBOWS & TEES & OFFSETS
    # --------------------------------------------------------------------------
    elif obj.Category == "Elbow":
        # UNIVERSAL ANCHOR: BaseCenter is ALWAYS the centerline intersection.
        shift_center = obj.RouteVertex if (hasattr(obj, "IsRouted") and obj.IsRouted) else obj.BaseCenter
        w_max = max(W, W2) if W2 else W
        
        if obj.Construction == "Mitered":
            r = w_max / 2.0
            pullback = r * math.tan(math.radians(abs(b_ang)) / 2.0)
            local_center = shift_center
        elif obj.Construction == "Smooth":
            r = w_max * 1.0
            pullback = r * math.tan(math.radians(abs(b_ang)) / 2.0)
            local_center = shift_center - obj.BaseNormal * pullback
        else:
            r = max(b_rad, (w_max / 2.0) + 0.1)
            pullback = r * math.tan(math.radians(abs(b_ang)) / 2.0)
            local_center = shift_center - obj.BaseNormal * pullback
            
        return build_elbow(local_center, obj.BaseNormal, rolled_Y, W, D, W2, D2, b_ang, b_rad, obj.Construction, gores, vanes_count, T, obj.Profile, corner_rad)
    
    elif obj.Category == "Tee":
        if hasattr(obj, "MainLength") and hasattr(obj, "BranchLength"):
            main_len = float(obj.MainLength.Value if hasattr(obj.MainLength, 'Value') else obj.MainLength)
            branch_len = float(obj.BranchLength.Value if hasattr(obj.BranchLength, 'Value') else obj.BranchLength)
        else:
            main_len = t_len; branch_len = t_len
            
        # UNIVERSAL ANCHOR: BaseCenter is ALWAYS the centerline intersection.
        shift_center = obj.RouteVertex if (hasattr(obj, "IsRouted") and obj.IsRouted) else obj.BaseCenter
        
        if "Dovetail" in obj.TeeType:
            local_center = shift_center - obj.BaseNormal * W
        elif "Y-Branch" in obj.TeeType:
            w_b_max = max(W3, W4)
            br_rad_val = float(obj.BranchRadius.Value if hasattr(obj.BranchRadius, 'Value') else obj.BranchRadius) if hasattr(obj, 'BranchRadius') else w_b_max * 0.5
            br_ang_val = float(obj.BranchAngle.Value if hasattr(obj.BranchAngle, 'Value') else obj.BranchAngle) if hasattr(obj, 'BranchAngle') else 90.0
            
            R_center = br_rad_val + (w_b_max / 2.0)
            ang_rad = math.radians(br_ang_val)
            
            Y_shift = R_center * math.tan(ang_rad / 2.0) - (w_b_max / 2.0) / math.tan(ang_rad) if ang_rad > 0.001 else 0.0
            local_center = shift_center - obj.BaseNormal * Y_shift
        else:
            local_center = shift_center
        
        if obj.TeeType == "Converging Wye Round":
            wye_angle = int(obj.WyeBranchAngle) if hasattr(obj, "WyeBranchAngle") else 45
            return build_converging_wye_round_junction(local_center, obj.BaseNormal, rolled_Y, rolled_X, W, W3, wye_angle, main_len, T)
        
        if obj.TeeType == "Circular Wye":
            return build_circular_wye(W, W3, W4, branch_len, main_len, 45, -45, T)
        
        if obj.TeeType == "Rect Main Round Branch":
            return build_tee_rect_main_round_branch(local_center, obj.BaseNormal, rolled_Y, rolled_X, W, D, W3, main_len, T)
        
        if obj.TeeType == "Rect Main Rect Branch":
            return build_tee_rect_main_rect_branch(local_center, obj.BaseNormal, rolled_Y, rolled_X, W, D, W3, D3, main_len, T)
        
        if obj.TeeType == "Rectangular Angled Branch":
            angle_deg = 45; branch_collar = W3 * 0.5; t_len_adj = main_len + 175
            return build_tee_rect_angled_branch(local_center, obj.BaseNormal, rolled_Y, W, D, W3, D3, angle_deg, t_len_adj, branch_collar, T)
        
        if obj.TeeType == "Conical Wye Round":
            d_s = W; d_b = W3; d_c = W2 if W2 >= W else W * 2
            diff_r = abs(d_s - d_b)
            reducer_len = max((diff_r / 2.0) / math.tan(math.radians(30.0) / 2.0), 1.0) * 2
            return build_wye_conical_with_collars(local_center, obj.BaseNormal, rolled_Y, d_s, d_b, 45, main_len, reducer_len, branch_len, 80, T, d_c)
        
        if obj.TeeType == "Rectangular Dovetail Wye":
            return build_dovetail_wye(local_center, obj.BaseNormal, rolled_Y, W, D, W3, D3, W4, D4, main_len, branch_len, T)
        
        if obj.TeeType == "Rectangular Wye":
            wye_angle = int(obj.WyeBranchAngle) if hasattr(obj, "WyeBranchAngle") else 45
            return build_rectangular_wye_geometry(W, W3, D, main_len, branch_len, wye_angle, T)
        
        if obj.TeeType == "Converging Wye":
            return build_converging_wye_elbow(local_center, obj.BaseNormal, rolled_Y, W, D, W3, D3, W, main_len, branch_len, T)
        
        if obj.TeeType == "Y-Branch" and obj.Profile == "Circular":
            return build_circular_wye(W, W3, W3, branch_len, main_len, 45, -45, T)
        
        route_segments = None
        if hasattr(obj, "IsRouted") and obj.IsRouted and hasattr(obj, "PathEdges"):
            route_segments = [(edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter), edge.Length) 
                            for edge in obj.PathEdges if edge.Length > 0.001]
        
        return build_tee(local_center, obj.BaseNormal, rolled_Y, rolled_X, W, D, W2, D2, W3, D3, W4, D4, 
                        obj.TeeType, br_ang, br_rad, main_len, T, obj.Profile, corner_rad, vanes_count, 
                        route_segments=route_segments, branch_length=branch_len)
        
    elif obj.Category == "Offset":
        return build_offset(obj.BaseCenter, obj.BaseNormal, rolled_Y, W, D, W2, D2, off_dist, off_len, obj.Construction, T, obj.Profile, corner_rad)
    
    elif obj.Category == "Drop/Rise Elbow":
        h = _f(obj.DropH); l = max(_f(obj.DropL), 0.1)
        return build_drop_elbow(obj.BaseCenter, obj.BaseNormal, obj.BaseY, roll_ang, W, D, W2, D2, h, l, T, obj.Profile, corner_rad)

    elif obj.Category == "Route (Follow Edges)":
        try: from Ducts.DuctGeometryUtils import build_route
        except ImportError: pass
        
        # v2.8.0 FIX: Extract the exact UI lengths and pass them to the Preview Engine!
        m_len = float(obj.MainLength.Value if hasattr(obj.MainLength, 'Value') else obj.MainLength) if hasattr(obj, 'MainLength') else 0.1
        b_len = float(obj.BranchLength.Value if hasattr(obj.BranchLength, 'Value') else obj.BranchLength) if hasattr(obj, 'BranchLength') else 0.1

        return build_route(W, D, W2, D2, W3, D3, W4, D4, T, obj.Profile, obj.Construction, corner_rad, b_rad, vanes_count, obj.PathEdges, gores, obj.TeeType, m_len, b_len)

# ==============================================================================
# 2. PARAMETRIC FEATURE PROXY
# ==============================================================================
class ParametricDuct:
    def __init__(self, obj):
        obj.Proxy = self
        # v1.7.2 Defensive Check: If properties already exist (due to Groups or Undo/Redo), skip adding them!
        if hasattr(obj, "Category"):
            self.update_visibility(obj)
            return
        
        obj.addProperty("App::PropertyEnumeration", "Category", "1. Setup").Category = ["Straight", "Transitions", "Elbow", "Tee", "Offset", "Drop/Rise Elbow", "Route (Follow Edges)"]
        obj.addProperty("App::PropertyEnumeration", "Profile", "1. Setup").Profile = ["Rectangular", "Circular"]
        obj.addProperty("App::PropertyEnumeration", "Profile2", "1. Setup").Profile2 = ["Rectangular", "Circular"] 
        obj.addProperty("App::PropertyEnumeration", "Construction", "1. Setup").Construction = ["Smooth", "Segmented", "Mitered"]
        obj.addProperty("App::PropertyEnumeration", "TeeType", "1. Setup").TeeType = ["Y-Branch", "Straight Tee", "Cross Tee", "T Branch", "Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Rectangular Angled Branch", "Rectangular Dovetail Wye", "Converging Wye", "Conical Wye Round", "Rectangular Wye", "Circular Wye"]
        obj.addProperty("App::PropertyEnumeration", "Alignment", "1. Setup").Alignment = ["Concentric", "Eccentric (Top Flat)", "Eccentric (Bottom Flat)", "Eccentric (Left Flat)", "Eccentric (Right Flat)"]

        obj.addProperty("App::PropertyLength", "W1", "2. Main Dimensions")
        obj.addProperty("App::PropertyLength", "D1", "2. Main Dimensions")
        obj.addProperty("App::PropertyLength", "W2", "2. Main Dimensions")
        obj.addProperty("App::PropertyLength", "D2", "2. Main Dimensions")
        obj.addProperty("App::PropertyLength", "Thickness", "2. Main Dimensions")
        obj.addProperty("App::PropertyLength", "CornerRadius", "2. Main Dimensions")

        obj.addProperty("App::PropertyLength", "W3", "3. Branch Dimensions")
        obj.addProperty("App::PropertyLength", "D3", "3. Branch Dimensions")
        obj.addProperty("App::PropertyLength", "W4", "3. Branch Dimensions")
        obj.addProperty("App::PropertyLength", "D4", "3. Branch Dimensions")

        obj.addProperty("App::PropertyLength", "StraightLength", "4. Fitting Parameters")
        obj.addProperty("App::PropertyAngle", "RollAngle", "4. Fitting Parameters")
        obj.addProperty("App::PropertyAngle", "BendAngle", "4. Fitting Parameters")
        obj.addProperty("App::PropertyLength", "BendRadius", "4. Fitting Parameters")
        obj.addProperty("App::PropertyInteger", "Gores", "4. Fitting Parameters").Gores = 5
        obj.addProperty("App::PropertyInteger", "SplitterVanes", "4. Fitting Parameters")
        obj.addProperty("App::PropertyAngle", "BranchAngle", "4. Fitting Parameters")
        obj.addProperty("App::PropertyLength", "BranchRadius", "4. Fitting Parameters")
        obj.addProperty("App::PropertyEnumeration", "WyeBranchAngle", "4. Fitting Parameters").WyeBranchAngle = ["15","30","45", "90"]
        obj.addProperty("App::PropertyLength", "TeeLength", "4. Fitting Parameters")
        obj.addProperty("App::PropertyLength", "MainLength", "2. Main Dimensions")
        obj.addProperty("App::PropertyLength", "BranchLength", "3. Branch Dimensions")
        obj.addProperty("App::PropertyLength", "OffsetDist", "4. Fitting Parameters")
        obj.addProperty("App::PropertyLength", "OffsetLen", "4. Fitting Parameters")
        obj.addProperty("App::PropertyLength", "DropH", "4. Fitting Parameters").DropH = 0.0
        obj.addProperty("App::PropertyLength", "DropL", "4. Fitting Parameters").DropL = 200.0

        obj.addProperty("App::PropertyBool", "AutoTransitionLength", "5. Automation").AutoTransitionLength = True
        obj.addProperty("App::PropertyAngle", "TransitionAngle", "5. Automation").TransitionAngle = 30.0
        obj.addProperty("App::PropertyBool", "AutoDropSize", "5. Automation").AutoDropSize = False

        obj.addProperty("App::PropertyVector", "BaseCenter", "6. Internal Placement")
        obj.addProperty("App::PropertyVector", "BaseNormal", "6. Internal Placement")
        obj.addProperty("App::PropertyVector", "BaseX", "6. Internal Placement")
        obj.addProperty("App::PropertyVector", "BaseY", "6. Internal Placement")
        
        obj.addProperty("App::PropertyLinkSubListGlobal", "PathEdges", "6. Internal Placement")
        obj.addProperty("App::PropertyBool", "IsRouted", "6. Internal Placement").IsRouted = False
        obj.addProperty("App::PropertyVector", "RouteP1", "6. Internal Placement").RouteP1 = App.Vector(0,0,0)
        obj.addProperty("App::PropertyVector", "RouteP2", "6. Internal Placement").RouteP2 = App.Vector(0,0,0)
        obj.addProperty("App::PropertyVector", "RouteVertex", "6. Internal Placement").RouteVertex = App.Vector(0,0,0)
        obj.addProperty("App::PropertyLink", "StartFitting", "6. Internal Placement")
        obj.addProperty("App::PropertyLink", "EndFitting", "6. Internal Placement")

        internal_props = ["BaseCenter", "BaseNormal", "BaseX", "BaseY", "IsRouted", "RouteP1", "RouteP2", "RouteVertex", "StartFitting", "EndFitting", "PathEdges"]
        for p in internal_props: obj.setEditorMode(p, 2)
        self.update_visibility(obj)

    def onChanged(self, fp, prop):
        if not (hasattr(fp, "W1") and hasattr(fp, "W2") and hasattr(fp, "D1") and hasattr(fp, "D2")): return
            
        if prop in ["W1", "D1", "W2", "D2", "TransitionAngle", "AutoTransitionLength", "Profile", "Profile2", "Alignment"]:
            if getattr(fp, "Category", "") == "Transitions" and getattr(fp, "AutoTransitionLength", False):
                prof1 = getattr(fp, "Profile", "Rectangular")
                prof2 = getattr(fp, "Profile2", prof1)
                w1 = fp.W1.Value; d1 = fp.D1.Value if prof1 != "Circular" else w1
                w2 = fp.W2.Value; d2 = fp.D2.Value if prof2 != "Circular" else w2
                
                w1_eff = w1; d1_eff = d1
                w2_eff = w2; d2_eff = d2
                if prof1 == "Circular" and prof2 != "Circular":
                    w2_eff = 1.13 * math.sqrt(w2 * d2); d2_eff = w2_eff
                elif prof1 != "Circular" and prof2 == "Circular":
                    w1_eff = 1.13 * math.sqrt(w1 * d1); d1_eff = w1_eff
                
                theta_deg = getattr(fp, "TransitionAngle", 30.0)
                theta_rad = math.radians(theta_deg)
                align = getattr(fp, "Alignment", "Concentric")
                
                diff_w = abs(w1_eff - w2_eff)
                diff_d = abs(d1_eff - d2_eff)
                
                if align == "Concentric":
                    req_L_w = (diff_w / 2.0) / math.tan(theta_rad / 2.0) if theta_rad > 0.001 and diff_w > 0 else 0
                    req_L_d = (diff_d / 2.0) / math.tan(theta_rad / 2.0) if theta_rad > 0.001 and diff_d > 0 else 0
                else:
                    max_off_w = diff_w if "Left" in align or "Right" in align else diff_w / 2.0
                    max_off_d = diff_d if "Top" in align or "Bottom" in align else diff_d / 2.0
                    ang_w = theta_rad if "Left" in align or "Right" in align else theta_rad / 2.0
                    ang_d = theta_rad if "Top" in align or "Bottom" in align else theta_rad / 2.0
                    req_L_w = max_off_w / math.tan(ang_w) if ang_w > 0.001 and max_off_w > 0 else 0
                    req_L_d = max_off_d / math.tan(ang_d) if ang_d > 0.001 and max_off_d > 0 else 0
                    
                fp.StraightLength = max(req_L_w, req_L_d, 1.0)
                
        if prop in ["W1", "D1", "AutoDropSize"]:
            if getattr(fp, "Category", "") == "Drop/Rise Elbow" and getattr(fp, "AutoDropSize", False):
                d1_val = fp.D1.Value if fp.Profile != "Circular" else fp.W1.Value
                fp.DropH = -d1_val * 1.5
                fp.DropL = d1_val * 2.0

        # CRITICAL FIX 1: Dynamically scale the Bend Radius if the Width changes OR the Construction changes
        if prop in ["Construction", "W1", "W2"]:
            if getattr(fp, "Category", "") in ["Elbow", "Route (Follow Edges)"]:
                # Find the largest width of the elbow to prevent miter clipping
                w_max = fp.W1.Value
                if hasattr(fp, "W2"): w_max = max(w_max, fp.W2.Value)
                
                if fp.Construction == "Smooth":
                    if hasattr(fp, "BendRadius"): fp.BendRadius = w_max * 1.0
                elif fp.Construction in ["Mitered", "Segmented"]:
                    # Do NOT forcefully crush the radius! Only clamp it if it drops below the safe minimum.
                    if hasattr(fp, "BendRadius") and fp.BendRadius < w_max / 2.0: 
                        fp.BendRadius = w_max / 2.0

        # USER ARCHITECTURE: Auto-sync branch dimensions when changing Tee Types!
        if prop in ["TeeType", "W1", "D1"]:
            if getattr(fp, "Category", "") == "Tee":
                t_type = getattr(fp, "TeeType", "")
                w1_val = fp.W1.Value if hasattr(fp.W1, 'Value') else getattr(fp, "W1", 100.0)
                d1_val = fp.D1.Value if hasattr(fp.D1, 'Value') else getattr(fp, "D1", 100.0)
                
                w_b_eff = w1_val
                if t_type in ["Y-Branch", "Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Rectangular Angled Branch", "Converging Wye", "Conical Wye Round", "Rectangular Wye", "Circular Wye"]:
                    w_b_eff = w1_val / 2.0
                    if hasattr(fp, "W3"): fp.W3 = w_b_eff
                    if hasattr(fp, "W4"): fp.W4 = w_b_eff
                elif t_type == "Rectangular Dovetail Wye":
                    if hasattr(fp, "W3"): fp.W3 = w_b_eff
                    if hasattr(fp, "W4"): fp.W4 = w_b_eff
                    
                if t_type in ["Rect Main Rect Branch", "Rectangular Angled Branch", "Rectangular Wye", "Rectangular Dovetail Wye"]:
                    if hasattr(fp, "D3"): fp.D3 = d1_val
                    if hasattr(fp, "D4"): fp.D4 = d1_val

                # CRITICAL FIX 5: Sync BranchRadius so Y-Branches shrink tightly when branches halve!
                if hasattr(fp, "BranchRadius"):
                    fp.BranchRadius = w_b_eff * 0.5

        if prop in ["Category", "Profile", "Profile2", "Construction", "TeeType", "AutoTransitionLength", "AutoDropSize"]:
            self.update_visibility(fp)

    def update_visibility(self, obj):
        if not hasattr(obj, "OffsetLen"): return
        def set_vis(prop_name, is_visible):
            if hasattr(obj, prop_name): obj.setEditorMode(prop_name, 0 if is_visible else 2)

        cat = obj.Category
        prof = obj.Profile
        const = obj.Construction
        tee_type = obj.TeeType
        is_circ = (prof == "Circular")

        set_vis("CornerRadius", prof == "Rounded Rectangular")
        set_vis("D1", not is_circ)

        # Alignment, TransitionAngle, AutoTransitionLength only for Transitions category
        set_vis("Alignment", cat == "Transitions")
        set_vis("TransitionAngle", cat == "Transitions")
        set_vis("AutoTransitionLength", cat == "Transitions")
        
        if cat == "Transitions" and getattr(obj, "AutoTransitionLength", False):
            if hasattr(obj, "StraightLength"): obj.setEditorMode("StraightLength", 1) 
        else:
            set_vis("StraightLength", cat in ["Straight", "Transitions"])

        set_vis("BendAngle", cat == "Elbow")
        set_vis("BendRadius", cat == "Elbow" and const == "Segmented")
        # Construction visibility - hide for Straight and Transitions in data tab
        set_vis("Construction", cat not in ["Straight", "Transitions"])
        set_vis("Gores", cat in ["Elbow", "Offset", "Route (Follow Edges)"] and const == "Segmented")
        set_vis("SplitterVanes", (cat == "Elbow" or (cat == "Tee" and tee_type == "T Branch")) and not is_circ)

        set_vis("TeeType", cat == "Tee")
        set_vis("BranchAngle", cat == "Tee" and tee_type == "Converging Wye Round")
        set_vis("BranchRadius", cat == "Tee")
        set_vis("TeeLength", cat == "Tee" and tee_type not in ["Rectangular Wye", "Converging Wye Round", "Conical Wye Round", "Converging Wye", "Rectangular Angled Branch", "Rectangular Dovetail Wye", "Rect Main Round Branch", "Rect Main Rect Branch", "Circular Wye"])
        set_vis("MainLength", cat == "Tee")
        set_vis("BranchLength", cat == "Tee")
        set_vis("WyeBranchAngle", cat == "Tee" and tee_type in ["Rectangular Wye", "Converging Wye Round", "Conical Wye Round", "Converging Wye", "Rectangular Angled Branch", "Rectangular Dovetail Wye"])

        set_vis("OffsetDist", cat == "Offset")
        set_vis("OffsetLen", cat == "Offset")
        
        set_vis("AutoDropSize", cat == "Drop/Rise Elbow")
        if cat == "Drop/Rise Elbow" and getattr(obj, "AutoDropSize", False):
            obj.setEditorMode("DropH", 1)
            obj.setEditorMode("DropL", 1)
        else:
            set_vis("DropH", cat == "Drop/Rise Elbow")
            set_vis("DropL", cat == "Drop/Rise Elbow")

        hide_trunk_exit = (cat == "Tee" and (tee_type == "Y-Branch" or tee_type == "T Branch" or tee_type == "Converging Wye Round" or tee_type == "Rect Main Round Branch" or tee_type == "Rect Main Rect Branch" or tee_type == "Rectangular Angled Branch" or tee_type == "Rectangular Dovetail Wye" or tee_type == "Converging Wye" or tee_type == "Rectangular Wye" or tee_type == "Circular Wye")) or cat == "Route (Follow Edges)"
        set_vis("W2", not hide_trunk_exit)
        set_vis("D2", not hide_trunk_exit and not is_circ)

        set_vis("W3", cat == "Tee")
        set_vis("D3", cat == "Tee" and not is_circ and tee_type not in ["Converging Wye Round", "Circular Wye"])
        show_opp_branch = cat == "Tee" and tee_type in ["Y-Branch", "Cross Tee", "Conical Wye Round", "Circular Wye"]
        set_vis("W4", show_opp_branch)
        set_vis("D4", show_opp_branch and not is_circ)

    def execute(self, obj):
        try:
            # v2.8.9 TOPOLOGICAL GRAPH SENSOR (Corrected Pullback Vectors)
            def _f(val): return float(val.Value if hasattr(val, 'Value') else val)
            cat = getattr(obj, "Category", "")
            
            if cat in ["Straight", "Transitions", "Elbow", "Tee"]:
                neighbors = [] 
                
                # 1. Build the topological graph
                neighbors_raw = [] 
                
                def _get_obj(prop):
                    if not prop: return None
                    if isinstance(prop, str) and hasattr(App.ActiveDocument, prop): return getattr(App.ActiveDocument, prop)
                    if hasattr(prop, "Name"): return prop
                    return None

                # CRITICAL FIX 1: Helper to extract true 3D endpoints whether Routed or Manual!
                def _get_true_endpoints(d_obj):
                    if getattr(d_obj, "IsRouted", False) and hasattr(d_obj, "RouteP1"):
                        return d_obj.RouteP1, d_obj.RouteP2
                    else:
                        d_len = _f(getattr(d_obj, "StraightLength", getattr(d_obj, "Length", 100.0)))
                        return d_obj.BaseCenter, d_obj.BaseCenter + d_obj.BaseNormal * d_len

                # A) Forward explicit links
                if cat in ["Straight", "Transitions"]:
                    s_fit = _get_obj(getattr(obj, "StartFitting", None))
                    e_fit = _get_obj(getattr(obj, "EndFitting", None))
                    if s_fit: neighbors_raw.append((s_fit, "START", "UNKNOWN"))
                    if e_fit: neighbors_raw.append((e_fit, "END", "UNKNOWN"))

                # B) Reverse explicit links & Spatial Proximity
                if hasattr(App, "ActiveDocument") and App.ActiveDocument:
                    my_ports = {}
                    if cat == "Transitions":
                        t_len_sp = _f(getattr(obj, "StraightLength", 0.0))
                        my_ports["START"] = obj.BaseCenter
                        my_ports["END"] = obj.BaseCenter + obj.BaseNormal * t_len_sp
                    elif cat in ["Elbow", "Tee"]:
                        my_ports["CENTER"] = obj.BaseCenter

                    closest_end_obj = None
                    min_axial_dist = float('inf')
                    closest_end_nbr_port = None

                    for doc_obj in App.ActiveDocument.Objects:
                        if doc_obj == obj: continue
                        d_cat = getattr(doc_obj, "Category", "")
                        
                        if d_cat in ["Straight", "Transitions"]:
                            ds_fit = _get_obj(getattr(doc_obj, "StartFitting", None))
                            de_fit = _get_obj(getattr(doc_obj, "EndFitting", None))
                            
                            if ds_fit == obj:
                                neighbors_raw.append((doc_obj, "END", "START"))
                                continue
                            elif de_fit == obj:
                                neighbors_raw.append((doc_obj, "START", "END"))
                                continue
                                
                            # 2. COLLINEAR RAYCAST SCANNER (Reads true endpoints!)
                            if cat == "Transitions" and d_cat == "Straight":
                                dp1, dp2 = _get_true_endpoints(doc_obj)
                                tol = 2.0
                                
                                if (dp1 - my_ports["START"]).Length < tol: 
                                    neighbors_raw.append((doc_obj, "START", "START"))
                                elif (dp2 - my_ports["START"]).Length < tol: 
                                    neighbors_raw.append((doc_obj, "START", "END"))
                                    
                                for dp, pt_type in [(dp1, "START"), (dp2, "END")]:
                                    vec = dp - my_ports["START"]
                                    axial = vec.dot(obj.BaseNormal)
                                    radial = (vec - obj.BaseNormal * axial).Length
                                    
                                    if radial < tol and axial > tol:
                                        if axial < min_axial_dist:
                                            min_axial_dist = axial
                                            closest_end_obj = doc_obj
                                            closest_end_nbr_port = pt_type

                    if closest_end_obj:
                        neighbors_raw.append((closest_end_obj, "END", closest_end_nbr_port))

                # Remove duplicates
                neighbors = []
                seen = set()
                for n in reversed(neighbors_raw):
                    if n[0].Name not in seen:
                        seen.add(n[0].Name)
                        neighbors.insert(0, n)

                # 2. PUSH dimensions and pullbacks to neighbors
                for nbr, my_port, nbr_port in neighbors:
                    n_cat = getattr(nbr, "Category", "")

                    # --- A. DIMENSION PUSHING (Fittings dictate sizes) ---
                    out_w, out_d = _f(obj.W1), _f(obj.D1)
                    
                    if cat == "Transitions":
                        if my_port == "END": 
                            out_w, out_d = _f(obj.W2), (_f(obj.D2) if getattr(obj, "Profile2", obj.Profile) != "Circular" else _f(obj.W2))
                    elif cat == "Tee":
                        v_align = nbr.BaseNormal if nbr_port == "START" else -nbr.BaseNormal
                        if abs(v_align.dot(obj.BaseNormal)) > 0.9:
                            out_w, out_d = _f(obj.W1), _f(obj.D1)
                        elif v_align.dot(obj.BaseX) > 0:
                            out_w, out_d = _f(obj.W4), _f(obj.D4)
                        else:
                            out_w, out_d = _f(obj.W3), _f(obj.D3)
                    elif cat == "Elbow":
                        v_align = nbr.BaseNormal if nbr_port == "START" else -nbr.BaseNormal
                        if abs(v_align.dot(obj.BaseNormal)) > 0.9:
                            out_w, out_d = _f(obj.W1), _f(obj.D1)
                        else:
                            out_w, out_d = _f(obj.W2) if hasattr(obj, "W2") else _f(obj.W1), _f(obj.D2) if hasattr(obj, "D2") else _f(obj.D1)

                    if n_cat == "Straight":
                        # CRITICAL FIX: Straight ducts must uniformly update BOTH ends to avoid tapering!
                        if abs(_f(nbr.W1) - out_w) > 0.001: nbr.W1 = out_w
                        if abs(_f(nbr.D1) - out_d) > 0.001: nbr.D1 = out_d
                        if abs(_f(nbr.W2) - out_w) > 0.001: nbr.W2 = out_w
                        if abs(_f(nbr.D2) - out_d) > 0.001: nbr.D2 = out_d
                    elif n_cat == "Transitions":
                        if nbr_port == "START" or nbr_port == "UNKNOWN":
                            if abs(_f(nbr.W1) - out_w) > 0.001: nbr.W1 = out_w
                            if abs(_f(nbr.D1) - out_d) > 0.001: nbr.D1 = out_d
                        if nbr_port == "END":
                            if abs(_f(nbr.W2) - out_w) > 0.001: nbr.W2 = out_w
                            if abs(_f(nbr.D2) - out_d) > 0.001: nbr.D2 = out_d
                    elif n_cat in ["Elbow", "Tee"]:
                        v_my_out = obj.BaseNormal if my_port == "START" else -obj.BaseNormal
                        if abs(v_my_out.dot(nbr.BaseNormal)) > 0.9:
                            if abs(_f(nbr.W1) - out_w) > 0.001: nbr.W1 = out_w
                            if abs(_f(nbr.D1) - out_d) > 0.001: nbr.D1 = out_d
                        else:
                            if abs(_f(nbr.W2) - out_w) > 0.001: nbr.W2 = out_w
                            if abs(_f(nbr.D2) - out_d) > 0.001: nbr.D2 = out_d

                    # --- B. POSITIONAL PULLBACK PUSHING (Fittings dictate positions) ---
                    if n_cat in ["Straight", "Transitions"] and nbr_port != "UNKNOWN":
                        
                        if getattr(obj, "IsRouted", False) and hasattr(obj, "RouteVertex"):
                            anchor_pt = obj.RouteVertex
                        else:
                            anchor_pt = obj.BaseCenter
                            if cat == "Tee":
                                t_type_anc = getattr(obj, "TeeType", "Straight Tee")
                                if "Dovetail" in t_type_anc:
                                    anchor_pt = obj.BaseCenter + obj.BaseNormal * _f(obj.W1)
                                elif "Y-Branch" in t_type_anc:
                                    w_b_max_anc = max(_f(obj.W3), _f(obj.W4)) if hasattr(obj, "W3") else _f(obj.W1)/2.0
                                    br_rad_anc = _f(getattr(obj, "BranchRadius", w_b_max_anc * 0.5))
                                    br_ang_anc = _f(getattr(obj, "BranchAngle", 90.0))
                                    R_c_anc = br_rad_anc + (w_b_max_anc / 2.0)
                                    a_rad_anc = math.radians(br_ang_anc)
                                    Y_shift_anc = R_c_anc * math.tan(a_rad_anc / 2.0) - (w_b_max_anc / 2.0) / math.tan(a_rad_anc) if a_rad_anc > 0.001 else 0.0
                                    anchor_pt = obj.BaseCenter + obj.BaseNormal * Y_shift_anc

                        v_dir = nbr.BaseNormal if nbr_port == "START" else -nbr.BaseNormal
                        pb = None
                        new_p = None
                        
                        if cat == "Elbow":
                            w_max = max(_f(obj.W1), _f(obj.W2)) if hasattr(obj, "W2") else _f(obj.W1)
                            if getattr(obj, "Construction", "Smooth") == "Smooth":
                                r = w_max * 1.0
                            elif getattr(obj, "Construction", "Smooth") == "Segmented":
                                r = max(_f(obj.BendRadius), (w_max / 2.0) + 0.1)
                            else:
                                r = max(_f(obj.BendRadius), w_max / 2.0)
                            pb = r * math.tan(math.radians(abs(_f(obj.BendAngle))) / 2.0)
                            
                        elif cat == "Tee":
                            t_type = getattr(obj, "TeeType", "Straight Tee")
                            t_len = _f(obj.MainLength) if _f(obj.MainLength) > 0.001 else _f(obj.TeeLength)
                            b_len = _f(obj.BranchLength) if _f(obj.BranchLength) > 0.001 else _f(obj.TeeLength)
                            bullhead_types = ["Y-Branch", "Rectangular Dovetail Wye", "Rectangular Wye", "Circular Wye"]
                            
                            is_trunk = abs(v_dir.dot(obj.BaseNormal)) > 0.9
                            
                            if any(b in t_type for b in bullhead_types):
                                if "Dovetail" in t_type:
                                    if not is_trunk:
                                        w_b = _f(obj.W4) if v_dir.dot(obj.BaseX) > 0 else _f(obj.W3)
                                        pb = 1.5 * _f(obj.W1) - (w_b / 2.0) + b_len 
                                    else:
                                        pb = _f(obj.W1) + t_len
                                elif "Y-Branch" in t_type:
                                    w_b_max = max(_f(obj.W3), _f(obj.W4))
                                    br_rad_val = _f(getattr(obj, "BranchRadius", w_b_max * 0.5))
                                    br_ang_val = _f(getattr(obj, "BranchAngle", 90.0))
                                    R_center_max = br_rad_val + (w_b_max / 2.0)
                                    ang_rad = math.radians(br_ang_val)
                                    Y_shift = R_center_max * math.tan(ang_rad / 2.0) - (w_b_max / 2.0) / math.tan(ang_rad) if ang_rad > 0.001 else 0.0
                                    
                                    if not is_trunk:
                                        w_b = _f(obj.W4) if v_dir.dot(obj.BaseX) > 0 else _f(obj.W3)
                                        R_center = br_rad_val + (w_b / 2.0)
                                        dist = (w_b / 2.0) / math.sin(ang_rad) + R_center * math.tan(ang_rad / 2.0) if ang_rad > 0.001 else 0.0
                                        pb = dist + b_len
                                    else:
                                        pb = Y_shift + t_len
                                else:
                                    pb = t_len if is_trunk else (t_len + b_len)
                            else:
                                if is_trunk:
                                    pb = t_len / 2.0
                                else:
                                    if "Converging Wye" in t_type:
                                        pb = (_f(obj.W1) / 2.0) + _f(getattr(obj, "BranchRadius", 50.0)) + b_len
                                    elif "Angled Branch" in t_type:
                                        br_ang = _f(getattr(obj, "BranchAngle", 45.0))
                                        hyp = (_f(obj.W1) / 2.0) / math.sin(math.radians(br_ang)) if br_ang > 0.1 else 0
                                        w_b = _f(obj.W4) if v_dir.dot(obj.BaseX) > 0 else _f(obj.W3)
                                        pb = hyp + (w_b / 2.0) + b_len
                                    else:
                                        pb = (_f(obj.W1) / 2.0) + b_len
                                        
                        elif cat == "Transitions":
                            # Pull length dynamically, handling AutoTransitionLength adjustments!
                            t_len = _f(getattr(obj, "StraightLength", getattr(obj, "Length", 0.0)))
                            if my_port == "START":
                                new_p = anchor_pt
                            elif my_port == "END":
                                new_p = anchor_pt + obj.BaseNormal * t_len

                        if pb is not None:
                            new_p = anchor_pt + v_dir * pb
                            
                        if new_p is not None:
                            # CRITICAL FIX 2: Connect the Hierarchy!
                            # Upgrade manual straight ducts to parametric Route lines so they can stretch dynamically!
                            if not getattr(nbr, "IsRouted", False):
                                ep1, ep2 = _get_true_endpoints(nbr)
                                nbr.RouteP1 = ep1
                                nbr.RouteP2 = ep2
                                nbr.IsRouted = True
                                
                            if nbr_port == "START":
                                if (nbr.RouteP1 - new_p).Length > 0.001: nbr.RouteP1 = new_p
                            elif nbr_port == "END":
                                if (nbr.RouteP2 - new_p).Length > 0.001: nbr.RouteP2 = new_p

            # Tell FreeCAD to actually draw the host shape
            obj.Shape = build_duct_shape(obj)
            
        except Exception as e: 
            import traceback
            App.Console.PrintError(f"Parametric Duct Recompute Error: {str(e)}\n{traceback.format_exc()}\n")

# ==============================================================================
# 3. UI TASK PANEL
# ==============================================================================
class DuctLibraryTaskPanel:
    def __init__(self):
        self.form = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(self.form)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.content_widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(self.content_widget)
        
        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)
        
        sel_ex = Gui.Selection.getSelectionEx()
        self.has_selection = False
        self.has_path_selection = False
        self.path_links = []
        
        if sel_ex:
            for sel in sel_ex:
                if sel.HasSubObjects:
                    for subname in sel.SubElementNames:
                        if subname.startswith("Edge"):
                            self.path_links.append((sel.Object, subname))
                            self.has_path_selection = True
                        elif subname.startswith("Face") and not self.has_selection:
                            self.has_selection = True
                            self.obj = sel.Object
                            self.face = sel.SubObjects[0]
                elif sel.Object and sel.Object.isDerivedFrom("Sketcher::SketchObject"):
                    for i in range(len(sel.Object.Shape.Edges)):
                        self.path_links.append((sel.Object, f"Edge{i+1}"))
                        self.has_path_selection = True
        
        if sel_ex and sel_ex[0].HasSubObjects and sel_ex[0].SubElementNames[0].startswith("Face"):
            self.has_selection = True
            self.obj = sel_ex[0].Object
            self.face = sel_ex[0].SubObjects[0]
            
            self.center = self.face.CenterOfMass
            self.normal = self.face.normalAt(0,0)
            
            self.local_X = None
            for edge in self.face.OuterWire.Edges:
                if hasattr(edge.Curve, 'Direction'):
                    self.local_X = edge.Curve.Direction
                    break
                    
            if self.local_X is None: 
                global_Z = App.Vector(0,0,1)
                self.local_X = App.Vector(1,0,0) if abs(self.normal.z) > 0.99 else self.normal.cross(global_Z).normalize()
                
            self.local_Y = self.normal.cross(self.local_X).normalize()
            
            pts = []
            for edge in self.face.OuterWire.Edges:
                pts.extend(edge.discretize(15)) 
                
            x_vals = [(pt - self.center).dot(self.local_X) for pt in pts]
            y_vals = [(pt - self.center).dot(self.local_Y) for pt in pts]
            
            self.detected_shape = "Rectangular"
            self.detected_radius = 0.0
            has_lines = False
            has_arcs = False
            for e in self.face.OuterWire.Edges:
                if hasattr(e, 'Curve'):
                    if e.Curve.TypeId == 'Part::GeomLine': has_lines = True
                    elif e.Curve.TypeId == 'Part::GeomCircle':
                        has_arcs = True
                        self.detected_radius = e.Curve.Radius
                        
            if has_lines and has_arcs: self.detected_shape = "Rounded Rectangular"
            elif has_arcs and not has_lines: self.detected_shape = "Circular"
            else: self.detected_shape = "Rectangular"

            if self.detected_shape == "Circular":
                self.W1 = round(self.detected_radius * 2.0, 2)
                self.D1 = self.W1
            else:
                max_x = -float('inf'); min_x = float('inf')
                max_y = -float('inf'); min_y = float('inf')
                for e in self.face.OuterWire.Edges:
                    for pt in e.discretize(20):
                        px = (pt - self.center).dot(self.local_X)
                        py = (pt - self.center).dot(self.local_Y)
                        max_x = max(max_x, px); min_x = min(min_x, px)
                        max_y = max(max_y, py); min_y = min(min_y, py)
                self.W1 = round(max(max_x - min_x, 10.0), 2)
                self.D1 = round(max(max_y - min_y, 10.0), 2)
        else:
            self.obj = None
            self.face = None
            self.center = App.Vector(0,0,0)
            self.normal = App.Vector(0,0,1)
            self.local_X = App.Vector(1,0,0)
            self.local_Y = App.Vector(0,1,0)
            self.W1 = 100.0
            self.D1 = 100.0
            self.detected_shape = "Rectangular"
            self.detected_radius = 0.0
            
        App.ActiveDocument.openTransaction("Create Duct Library Part")
        
        self.preview_obj = App.ActiveDocument.addObject("Part::Feature", "Preview_Duct")
        if self.preview_obj.ViewObject:
            self.preview_obj.ViewObject.Transparency = 50 
            self.preview_obj.ViewObject.ShapeColor = (0.8, 0.4, 0.1) 
        
        self.setup_ui()
        
        # Auto-select Match Selected Face when face is selected (after UI is set up)
        if self.has_selection:
            self.shape_combo.setCurrentText("Match Selected Face")
            # Auto-set target profile based on detected shape
            detected = getattr(self, 'detected_shape', 'Rectangular')
            if detected == 'Circular':
                self.shape2_combo.setCurrentText('Circular')
            else:
                self.shape2_combo.setCurrentText('Rectangular')
            # Update UI visibility and preview
            self.toggle_ui()
            self.update_preview()
        
    def setup_ui(self):
        # ==========================================
        # SECTION 1: DUCT SPECIFICATION
        # ==========================================
        self.spec_group = QtWidgets.QGroupBox("Duct Specification")
        spec_form = QtWidgets.QFormLayout(self.spec_group)
        
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.addItems(["Straight Duct", "Transitions", "Elbow", "Tee", "Offset", "Drop/Rise Elbow", "Route (Follow Edges)"])
        spec_form.addRow("Fitting Category:", self.category_combo)
        
        self.const_label = QtWidgets.QLabel("Construction:")
        self.const_combo = QtWidgets.QComboBox()
        self.const_combo.addItems(["Smooth", "Mitered", "Segmented"])
        spec_form.addRow(self.const_label, self.const_combo)
        
        self.tee_type_label = QtWidgets.QLabel("Tee Type:")
        self.tee_type_combo = QtWidgets.QComboBox()
        self.tee_type_combo.addItems(["Rectangular Dovetail Wye", "Y-Branch"])
        spec_form.addRow(self.tee_type_label, self.tee_type_combo)
        
        self.shape_combo = QtWidgets.QComboBox()
        self.shape_combo.addItems(["Rectangular", "Circular", "Match Selected Face"])
        spec_form.addRow("Base Profile:", self.shape_combo)
        
        self.target_profile_label = QtWidgets.QLabel("Target Profile:")
        self.shape2_combo = QtWidgets.QComboBox()
        self.shape2_combo.addItems(["Rectangular", "Circular"])
        spec_form.addRow(self.target_profile_label, self.shape2_combo)
        
        self.gores_label = QtWidgets.QLabel("Number of Gores:")
        self.gores_input = QtWidgets.QSpinBox()
        self.gores_input.setRange(3, 12)
        self.gores_input.setValue(5)
        spec_form.addRow(self.gores_label, self.gores_input)
        
        self.roll_input = QtWidgets.QDoubleSpinBox()
        self.roll_input.setRange(-180.0, 180.0)
        self.roll_input.setValue(0.0)
        self.roll_input.setSingleStep(90.0)
        self.roll_input.setSuffix(" °")
        spec_form.addRow("Roll Angle:", self.roll_input)
        
        self.vanes_label = QtWidgets.QLabel("Splitter Vanes:")
        self.vanes_input = QtWidgets.QSpinBox()
        self.vanes_input.setRange(0, 10)
        self.vanes_input.setValue(0)
        spec_form.addRow(self.vanes_label, self.vanes_input)
        
        self.t_input = QtWidgets.QDoubleSpinBox()
        self.t_input.setRange(0.1, 50.0)
        self.t_input.setValue(2.0)
        self.t_input.setSingleStep(0.5)
        self.t_input.setSuffix(" mm")
        spec_form.addRow("Wall Thickness:", self.t_input)
        
        self.layout.addWidget(self.spec_group)

        # ==========================================
        # SECTION 2: DUCT DIMENSIONS
        # ==========================================
        self.dims_group = QtWidgets.QGroupBox("Duct Dimensions")
        dims_layout = QtWidgets.QVBoxLayout(self.dims_group)
        
        # Main Trunk - W1/D1 side-by-side
        dim1_layout = QtWidgets.QHBoxLayout()
        w1_layout = QtWidgets.QVBoxLayout()
        self.w_label = QtWidgets.QLabel("Width/Diameter (W1):")
        w1_layout.addWidget(self.w_label)
        self.w_input = QtWidgets.QDoubleSpinBox()
        self.w_input.setRange(50.0, 10000.0)
        self.w_input.setValue(self.W1)
        self.w_input.setSingleStep(50.0)
        self.w_input.setSuffix(" mm")
        w1_layout.addWidget(self.w_input)
        dim1_layout.addLayout(w1_layout)

        d1_layout = QtWidgets.QVBoxLayout()
        self.d_label = QtWidgets.QLabel("Depth (D1):")
        d1_layout.addWidget(self.d_label)
        self.d_input = QtWidgets.QDoubleSpinBox()
        self.d_input.setRange(50.0, 10000.0)
        self.d_input.setValue(self.D1)
        self.d_input.setSingleStep(50.0)
        self.d_input.setSuffix(" mm")
        d1_layout.addWidget(self.d_input)
        dim1_layout.addLayout(d1_layout)
        dims_layout.addLayout(dim1_layout)
        
        # Main Length
        main_len_layout = QtWidgets.QHBoxLayout()
        self.main_len_label = QtWidgets.QLabel("Main Length:")
        main_len_layout.addWidget(self.main_len_label)
        self.main_len_input = QtWidgets.QDoubleSpinBox()
        self.main_len_input.setRange(0.0, 10000.0) # SET TO 0.0
        self.main_len_input.setValue(0.0)          # SET DEFAULT TO 0
        self.main_len_input.setSingleStep(50.0)
        self.main_len_input.setSuffix(" mm")
        main_len_layout.addWidget(self.main_len_input)
        dims_layout.addLayout(main_len_layout)
        
        # Target - W2/D2 side-by-side
        dim2_layout = QtWidgets.QHBoxLayout()
        w2_layout = QtWidgets.QVBoxLayout()
        self.w2_label = QtWidgets.QLabel("Target Width/Diameter (W2):")
        w2_layout.addWidget(self.w2_label)
        self.w2_input = QtWidgets.QDoubleSpinBox()
        self.w2_input.setRange(10.0, 10000.0)
        self.w2_input.setValue(self.W1)
        self.w2_input.setSingleStep(50.0)
        self.w2_input.setSuffix(" mm")
        w2_layout.addWidget(self.w2_input)
        dim2_layout.addLayout(w2_layout)

        d2_layout = QtWidgets.QVBoxLayout()
        self.d2_label = QtWidgets.QLabel("Target Depth (D2):")
        d2_layout.addWidget(self.d2_label)
        self.d2_input = QtWidgets.QDoubleSpinBox()
        self.d2_input.setRange(10.0, 10000.0)
        self.d2_input.setValue(self.D1)
        self.d2_input.setSingleStep(50.0)
        self.d2_input.setSuffix(" mm")
        d2_layout.addWidget(self.d2_input)
        dim2_layout.addLayout(d2_layout)
        dims_layout.addLayout(dim2_layout)
        
        # Straight-specific controls
        straight_widget = QtWidgets.QWidget()
        straight_v_layout = QtWidgets.QVBoxLayout(straight_widget)
        straight_v_layout.setContentsMargins(0,0,0,0)
        
        self.align_combo = QtWidgets.QComboBox()
        self.align_combo.addItems(["Concentric", "Eccentric (Top Flat)", "Eccentric (Bottom Flat)", "Eccentric (Left Flat)", "Eccentric (Right Flat)"])
        self.align_label = QtWidgets.QLabel("Transition Alignment:")
        straight_v_layout.addWidget(self.align_label)
        straight_v_layout.addWidget(self.align_combo)

        self.auto_len_cb = QtWidgets.QCheckBox("Auto-Calculate Length by SMACNA Angle")
        self.auto_len_cb.setChecked(False)
        straight_v_layout.addWidget(self.auto_len_cb)

        self.p_label = QtWidgets.QLabel("Max Divergence Angle (θ):")
        straight_v_layout.addWidget(self.p_label)
        self.p_input = QtWidgets.QDoubleSpinBox()
        self.p_input.setRange(1.0, 180.0)
        self.p_input.setValue(30.0)
        self.p_input.setSuffix(" °")
        straight_v_layout.addWidget(self.p_input)

        straight_v_layout.addWidget(QtWidgets.QLabel("Duct Length (L):"))
        self.straight_len_input = QtWidgets.QDoubleSpinBox()
        self.straight_len_input.setRange(1.0, 10000.0)
        self.straight_len_input.setValue(100.0)
        self.straight_len_input.setSingleStep(100.0)
        self.straight_len_input.setSuffix(" mm")
        straight_v_layout.addWidget(self.straight_len_input)
        
        dims_layout.addWidget(straight_widget)
        self.straight_frame = straight_widget  # Reference for toggle_ui
        
        # Elbow-specific controls
        elbow_widget = QtWidgets.QWidget()
        elbow_v_layout = QtWidgets.QVBoxLayout(elbow_widget)
        elbow_v_layout.setContentsMargins(0,0,0,0)
        
        elbow_v_layout.addWidget(QtWidgets.QLabel("Bend Angle:"))
        self.angle_input = QtWidgets.QDoubleSpinBox()
        self.angle_input.setRange(1.0, 180.0)
        self.angle_input.setValue(90.0)
        self.angle_input.setSuffix(" °")
        elbow_v_layout.addWidget(self.angle_input)

        self.b_label = QtWidgets.QLabel("Bend Radius:")
        elbow_v_layout.addWidget(self.b_label)
        self.b_input = QtWidgets.QDoubleSpinBox()
        self.b_input.setRange(1.0, 5000.0)
        self.b_input.setValue(100.0)
        self.b_input.setSuffix(" mm")
        elbow_v_layout.addWidget(self.b_input)
        
        dims_layout.addWidget(elbow_widget)
        self.elbow_frame = elbow_widget  # Reference for toggle_ui
        
        # Offset-specific controls
        offset_widget = QtWidgets.QWidget()
        offset_v_layout = QtWidgets.QVBoxLayout(offset_widget)
        offset_v_layout.setContentsMargins(0,0,0,0)
        
        offset_v_layout.addWidget(QtWidgets.QLabel("Offset Distance:"))
        self.off_dist_input = QtWidgets.QDoubleSpinBox()
        self.off_dist_input.setRange(-5000.0, 5000.0)
        self.off_dist_input.setValue(150.0)
        self.off_dist_input.setSingleStep(50.0)
        self.off_dist_input.setSuffix(" mm")
        offset_v_layout.addWidget(self.off_dist_input)

        offset_v_layout.addWidget(QtWidgets.QLabel("Offset Length:"))
        self.off_len_input = QtWidgets.QDoubleSpinBox()
        self.off_len_input.setRange(10.0, 10000.0)
        self.off_len_input.setValue(300.0)
        self.off_len_input.setSingleStep(50.0)
        self.off_len_input.setSuffix(" mm")
        offset_v_layout.addWidget(self.off_len_input)
        
        dims_layout.addWidget(offset_widget)
        self.offset_frame = offset_widget  # Reference for toggle_ui
        
        # Drop/Rise-specific controls
        drop_widget = QtWidgets.QWidget()
        drop_v_layout = QtWidgets.QVBoxLayout(drop_widget)
        drop_v_layout.setContentsMargins(0,0,0,0)
        
        self.auto_drop_cb = QtWidgets.QCheckBox("Auto-Calculate Drop Size (1.5x)")
        self.auto_drop_cb.setChecked(False)
        drop_v_layout.addWidget(self.auto_drop_cb)

        drop_v_layout.addWidget(QtWidgets.QLabel("Drop Height (Z-Axis):"))
        self.drop_h_input = QtWidgets.QDoubleSpinBox()
        self.drop_h_input.setRange(-5000.0, 5000.0)
        self.drop_h_input.setValue(-150.0)
        self.drop_h_input.setSingleStep(50.0)
        self.drop_h_input.setSuffix(" mm")
        drop_v_layout.addWidget(self.drop_h_input)

        drop_v_layout.addWidget(QtWidgets.QLabel("Forward Length:"))
        self.drop_l_input = QtWidgets.QDoubleSpinBox()
        self.drop_l_input.setRange(10.0, 10000.0)
        self.drop_l_input.setValue(200.0)
        self.drop_l_input.setSingleStep(50.0)
        self.drop_l_input.setSuffix(" mm")
        drop_v_layout.addWidget(self.drop_l_input)
        
        dims_layout.addWidget(drop_widget)
        self.drop_frame = drop_widget  # Reference for toggle_ui
        
        self.layout.addWidget(self.dims_group)

        # ==========================================
        # SECTION 3: BRANCH (only for Tee)
        # ==========================================
        self.branch_group = QtWidgets.QGroupBox("Branch")
        branch_layout = QtWidgets.QVBoxLayout(self.branch_group)
        
        # Branch 2 - W4/D4 side-by-side
        dim4_layout = QtWidgets.QHBoxLayout()
        w4_layout = QtWidgets.QVBoxLayout()
        self.w4_label = QtWidgets.QLabel("Branch 2 Width (W4):")
        w4_layout.addWidget(self.w4_label)
        self.w4_input = QtWidgets.QDoubleSpinBox()
        self.w4_input.setRange(50.0, 10000.0)
        self.w4_input.setValue(100.0)
        self.w4_input.setSingleStep(50.0)
        self.w4_input.setSuffix(" mm")
        w4_layout.addWidget(self.w4_input)
        dim4_layout.addLayout(w4_layout)

        d4_layout = QtWidgets.QVBoxLayout()
        self.d4_label = QtWidgets.QLabel("Branch 2 Depth (D4):")
        d4_layout.addWidget(self.d4_label)
        self.d4_input = QtWidgets.QDoubleSpinBox()
        self.d4_input.setRange(50.0, 10000.0)
        self.d4_input.setValue(100.0)
        self.d4_input.setSingleStep(50.0)
        self.d4_input.setSuffix(" mm")
        d4_layout.addWidget(self.d4_input)
        dim4_layout.addLayout(d4_layout)
        branch_layout.addLayout(dim4_layout)

        # Branch 1 - W3/D3 side-by-side
        dim3_layout = QtWidgets.QHBoxLayout()
        w3_layout = QtWidgets.QVBoxLayout()
        self.w3_label = QtWidgets.QLabel("Branch 1 Width (W3):")
        w3_layout.addWidget(self.w3_label)
        self.w3_input = QtWidgets.QDoubleSpinBox()
        self.w3_input.setRange(50.0, 10000.0)
        self.w3_input.setValue(100.0)
        self.w3_input.setSingleStep(50.0)
        self.w3_input.setSuffix(" mm")
        w3_layout.addWidget(self.w3_input)
        dim3_layout.addLayout(w3_layout)

        d3_layout = QtWidgets.QVBoxLayout()
        self.d3_label = QtWidgets.QLabel("Branch 1 Depth (D3):")
        d3_layout.addWidget(self.d3_label)
        self.d3_input = QtWidgets.QDoubleSpinBox()
        self.d3_input.setRange(50.0, 10000.0)
        self.d3_input.setValue(100.0)
        self.d3_input.setSingleStep(50.0)
        self.d3_input.setSuffix(" mm")
        d3_layout.addWidget(self.d3_input)
        dim3_layout.addLayout(d3_layout)
        branch_layout.addLayout(dim3_layout)

        # Branch Length
        branch_len_layout = QtWidgets.QHBoxLayout()
        self.branch_len_label = QtWidgets.QLabel("Branch Length:")
        branch_len_layout.addWidget(self.branch_len_label)
        self.branch_len_input = QtWidgets.QDoubleSpinBox()
        self.branch_len_input.setRange(0.0, 10000.0) # SET TO 0.0
        self.branch_len_input.setValue(0.0)          # SET DEFAULT TO 0
        self.branch_len_input.setSingleStep(50.0)
        self.branch_len_input.setSuffix(" mm")
        branch_len_layout.addWidget(self.branch_len_input)
        branch_layout.addLayout(branch_len_layout)

        # Branch Angle
        wye_angle_layout = QtWidgets.QHBoxLayout()
        self.wye_angle_label = QtWidgets.QLabel("Branch Angle:")
        wye_angle_layout.addWidget(self.wye_angle_label)
        self.wye_angle_combo = QtWidgets.QComboBox()
        self.wye_angle_combo.addItems(["45", "90"])
        self.wye_angle_combo.setCurrentText("45")
        wye_angle_layout.addWidget(self.wye_angle_combo)
        branch_layout.addLayout(wye_angle_layout)
        self.wye_angle_combo.currentIndexChanged.connect(self.update_preview)
        self.wye_angle_combo.currentIndexChanged.connect(self.on_wye_angle_changed)
        
        self.layout.addWidget(self.branch_group)

        # ==========================================
        # SECTION 4: CONVERGENCE/DIVERGENCE (Wye Types)
        # ==========================================
        self.wye_group = QtWidgets.QGroupBox("Convergence/Divergence")
        wye_layout = QtWidgets.QVBoxLayout(self.wye_group)
        
        wye_type_layout = QtWidgets.QHBoxLayout()
        self.wye_type_label = QtWidgets.QLabel("Wye Type:")
        wye_type_layout.addWidget(self.wye_type_label)
        self.wye_type_combo = QtWidgets.QComboBox()
        self.wye_type_combo.addItems(["Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Rectangular Angled Branch", "Conical Wye Round"])
        wye_type_layout.addWidget(self.wye_type_combo)
        wye_layout.addLayout(wye_type_layout)
        
        wye_angle_layout2 = QtWidgets.QHBoxLayout()
        self.wye_branch_angle_label = QtWidgets.QLabel("Branch Angle:")
        wye_angle_layout2.addWidget(self.wye_branch_angle_label)
        self.wye_branch_angle_combo = QtWidgets.QComboBox()
        self.wye_branch_angle_combo.addItems(["45", "90"])
        self.wye_branch_angle_combo.setCurrentText("45")
        wye_angle_layout2.addWidget(self.wye_branch_angle_combo)
        wye_layout.addLayout(wye_angle_layout2)
        
        self.layout.addWidget(self.wye_group)
        
        # ==========================================
        # 5. SIGNAL CONNECTIONS
        # ==========================================
        
        # THE AUTO-HALVING BRANCH LINK (Connect before preview!)
        self.w_input.valueChanged.connect(self.on_w_changed)

        self.category_combo.currentIndexChanged.connect(self.toggle_ui)
        self.category_combo.currentIndexChanged.connect(self.auto_calc_transition_length)
        self.category_combo.currentIndexChanged.connect(self.auto_calc_drop)
        self.category_combo.currentIndexChanged.connect(self.reset_roll_angle)
        # Fix #9: Reset inputs on Category change - REMOVED to preserve W2/D2 values when switching categories
        
        self.shape_combo.currentIndexChanged.connect(self.toggle_ui)
        self.shape_combo.currentIndexChanged.connect(self.update_preview)
        self.shape_combo.currentIndexChanged.connect(self.auto_calc_transition_length)
        self.shape2_combo.currentIndexChanged.connect(self.toggle_ui)
        self.shape2_combo.currentIndexChanged.connect(self.auto_calc_transition_length)
        
        self.const_combo.currentIndexChanged.connect(self.toggle_ui)
        self.const_combo.currentIndexChanged.connect(self.update_preview)
        
        self.tee_type_combo.currentIndexChanged.connect(self.on_tee_type_changed)

        self.auto_len_cb.stateChanged.connect(self.auto_calc_transition_length)
        self.p_input.valueChanged.connect(self.auto_calc_transition_length)
        
        self.w_input.valueChanged.connect(self.auto_calc_transition_length)
        self.w_input.valueChanged.connect(self.auto_calc_drop)
        self.d_input.valueChanged.connect(self.auto_calc_transition_length)
        self.d_input.valueChanged.connect(self.auto_calc_drop)
        self.d_input.valueChanged.connect(self.on_d_changed)
        
        self.auto_drop_cb.stateChanged.connect(self.auto_calc_drop)
        
        self.w2_input.valueChanged.connect(self.auto_calc_transition_length)
        self.d2_input.valueChanged.connect(self.auto_calc_transition_length)
        self.t_input.valueChanged.connect(self.update_preview)

        self.roll_input.valueChanged.connect(self.update_preview)

        self.align_combo.currentIndexChanged.connect(self.update_preview)
        self.straight_len_input.valueChanged.connect(self.update_preview)
        self.vanes_input.valueChanged.connect(self.update_preview)

        self.angle_input.valueChanged.connect(self.update_preview)
        self.b_input.valueChanged.connect(self.update_preview)
        self.gores_input.valueChanged.connect(self.update_preview)
        
        self.w3_input.valueChanged.connect(self.update_preview)
        self.d3_input.valueChanged.connect(self.update_preview)
        self.d3_input.valueChanged.connect(self.on_d3_changed)
        self.w4_input.valueChanged.connect(self.update_preview)
        self.d4_input.valueChanged.connect(self.update_preview)

        self.off_dist_input.valueChanged.connect(self.update_preview)
        self.off_len_input.valueChanged.connect(self.update_preview)
        self.drop_h_input.valueChanged.connect(self.update_preview)
        self.drop_l_input.valueChanged.connect(self.update_preview)
        
        self.main_len_input.valueChanged.connect(self.update_preview)
        self.branch_len_input.valueChanged.connect(self.update_preview)

        # Convergence/Divergence (Wye) signals
        self.wye_type_combo.currentIndexChanged.connect(self.on_wye_type_changed)
        self.wye_branch_angle_combo.currentIndexChanged.connect(self.update_preview)

        self.toggle_ui()
        self.update_preview()
        
        # Auto-select Route category if path/edges selected
        if self.has_path_selection:
            self.category_combo.setCurrentText("Route (Follow Edges)")

    def on_w_changed(self, *args):
        val = self.w_input.value()
        
        # Fix #3: When W changes for Offset category, also set D = W (one-way sync: W→D)
        if self.category_combo.currentText() == "Offset":
            self.d_input.blockSignals(True)
            self.d_input.setValue(val)
            self.d_input.blockSignals(False)
        
        if self.tee_type_combo.currentText() in ["Y-Branch", "Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Rectangular Angled Branch", "Conical Wye Round", "Rectangular Wye", "Circular Wye"]:
            self.w3_input.blockSignals(True)
            self.w4_input.blockSignals(True)    
            self.w3_input.setValue(val / 2.0)
            self.w4_input.setValue(val / 2.0)
            self.w3_input.blockSignals(False)
            self.w4_input.blockSignals(False)
            
        # FIX: Ensure Dovetail branches match the Main Width
        elif self.tee_type_combo.currentText() == "Rectangular Dovetail Wye":
            self.w3_input.blockSignals(True)
            self.w4_input.blockSignals(True)
            self.w3_input.setValue(val)
            self.w4_input.setValue(val)
            self.w3_input.blockSignals(False)
            self.w4_input.blockSignals(False)
            
            if self.tee_type_combo.currentText() == "Conical Wye Round":
                self.w2_input.blockSignals(True)
                self.w2_input.setValue(val * 2)  # W2 = W1 * 2
                self.w2_input.setMinimum(val)     # Enforce W2 >= W1
                self.w2_input.blockSignals(False)
                
                self.w3_input.blockSignals(True)
                self.w3_input.setValue(val / 2)   # W3 = W1 * 0.5 (branch diameter)
                self.w3_input.blockSignals(False)
            
            if self.tee_type_combo.currentText() in ["Rectangular Angled Branch", "Rectangular Wye", "Rectangular Dovetail Wye"]:
                self.d3_input.blockSignals(True)
                self.d3_input.setValue(self.d_input.value())  # D3 = D1
                self.d3_input.blockSignals(False)
                # FIX 1.1: Ensure D4 also matches D1 for dual-branch fittings
                if self.tee_type_combo.currentText() in ["Rectangular Wye", "Rectangular Dovetail Wye"]:
                    self.d4_input.blockSignals(True)
                    self.d4_input.setValue(self.d_input.value())  # D4 = D1
                    self.d4_input.blockSignals(False)
            
            # FIX 1.2: Removed Dovetail from this list so it stops overriding Branch Length!
            angled_tees = ["Rectangular Wye", "Converging Wye Round", "Conical Wye Round", "Converging Wye", "Rectangular Angled Branch"]
            if self.tee_type_combo.currentText() in angled_tees:
                self.on_wye_angle_changed()
        
        if self.tee_type_combo.currentText() == "Rect Main Rect Branch":
            d1_val = self.d_input.value()
            self.d3_input.blockSignals(True)
            self.d3_input.setValue(d1_val / 2.0)
            self.d3_input.blockSignals(False)
        
        self.update_preview()

    def on_d_changed(self, *args):
        if self.tee_type_combo.currentText() in ["Rect Main Rect Branch", "Conical Wye Round", "Rectangular Angled Branch", "Rectangular Wye", "Rectangular Dovetail Wye"]:
            d1_val = self.d_input.value()
            
            if self.tee_type_combo.currentText() == "Rect Main Rect Branch":
                self.d3_input.blockSignals(True)
                self.d3_input.setValue(d1_val / 2.0)
                self.d3_input.blockSignals(False)
            
            if self.tee_type_combo.currentText() == "Conical Wye Round":
                self.d2_input.blockSignals(True)
                self.d2_input.setValue(d1_val * 2)  # D2 = D1 * 2
                self.d2_input.blockSignals(False)
            
            if self.tee_type_combo.currentText() in ["Rectangular Angled Branch", "Rectangular Wye", "Rectangular Dovetail Wye"]:
                self.d3_input.blockSignals(True)
                self.d3_input.setValue(d1_val)  # D3 = D1
                self.d3_input.blockSignals(False)
                
            # FIX 1.1: Sync D4 with D1
            if self.tee_type_combo.currentText() in ["Rectangular Wye", "Rectangular Dovetail Wye"]:
                self.d4_input.blockSignals(True)
                self.d4_input.setValue(d1_val)  # D4 = D1
                self.d4_input.blockSignals(False)
            
            self.update_preview()
    
    def on_d3_changed(self, *args):
        if self.tee_type_combo.currentText() in ["Rectangular Wye", "Rectangular Dovetail Wye"]:
            d3_val = self.d3_input.value()
            self.d_input.blockSignals(True)
            self.d_input.setValue(d3_val)  # D1 = D3
            self.d_input.blockSignals(False)
            self.update_preview()
    
    def on_wye_angle_changed(self, *args):
        angled_tees = ["Rectangular Wye", "Converging Wye Round", "Conical Wye Round", "Converging Wye", "Rectangular Angled Branch", "Rectangular Dovetail Wye"]
        if self.tee_type_combo.currentText() in angled_tees:
            angle = int(self.wye_angle_combo.currentText())
            w3_val = self.w3_input.value()
            if angle == 45:
                min_branch_len = w3_val * 0.625
            elif angle == 30:
                min_branch_len = w3_val * 1.125
            elif angle == 15:
                min_branch_len = w3_val * 2.625
            else:
                min_branch_len = 100.0
            if self.branch_len_input.value() < min_branch_len:
                self.branch_len_input.blockSignals(True)
                self.branch_len_input.setValue(min_branch_len)
                self.branch_len_input.blockSignals(False)
            self.branch_len_input.setMinimum(min_branch_len)
            self.update_preview()

    def on_tee_type_changed(self, *args):
        tee_type = self.tee_type_combo.currentText()
        # Removed Dovetail Wye from this list!
        if tee_type in ["Y-Branch", "Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Rectangular Angled Branch", "Converging Wye", "Conical Wye Round", "Rectangular Wye", "Circular Wye"]:
            val = self.w_input.value()
            self.w3_input.blockSignals(True)
            self.w4_input.blockSignals(True)
            self.w3_input.setValue(val / 2.0)
            self.w4_input.setValue(val / 2.0)
            self.w3_input.blockSignals(False)
            self.w4_input.blockSignals(False)
            
        # FIX: Ensure Dovetail branches match the Main Width when selected
        elif tee_type == "Rectangular Dovetail Wye":
            val = self.w_input.value()
            self.w3_input.blockSignals(True)
            self.w4_input.blockSignals(True)
            self.w3_input.setValue(val)
            self.w4_input.setValue(val)
            self.w3_input.blockSignals(False)
            self.w4_input.blockSignals(False)
            
            if tee_type == "Conical Wye Round":
                self.w2_input.blockSignals(True)
                self.w2_input.setValue(val * 2)  # W2 = W1 * 2
                self.w2_input.blockSignals(False)
        
        if tee_type == "Rect Main Rect Branch":
            d1_val = self.d_input.value()
            self.d3_input.blockSignals(True)
            self.d3_input.setValue(d1_val / 2.0)
            self.d3_input.blockSignals(False)
        
        if tee_type in ["Rectangular Angled Branch", "Rectangular Wye", "Rectangular Dovetail Wye"]:
            d1_val = self.d_input.value()
            self.d3_input.blockSignals(True)
            self.d3_input.setValue(d1_val)  # D3 = D1
            self.d3_input.blockSignals(False)
            # FIX 1.1: Sync D4 with D1
            if tee_type in ["Rectangular Wye", "Rectangular Dovetail Wye"]:
                self.d4_input.blockSignals(True)
                self.d4_input.setValue(d1_val)  # D4 = D1
                self.d4_input.blockSignals(False)
        
        # FIX 1.2: Removed Dovetail from list
        if tee_type in ["Rectangular Wye", "Converging Wye Round", "Conical Wye Round", "Converging Wye", "Rectangular Angled Branch"]:
            self.on_wye_angle_changed()
        
        if tee_type == "Converging Wye Round":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Circular")
            self.shape_combo.blockSignals(False)
        
        if tee_type == "Circular Wye":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Circular")
            self.shape_combo.blockSignals(False)
        
        if tee_type == "Conical Wye Round":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Circular")
            self.shape_combo.blockSignals(False)
        
        if tee_type == "Rect Main Round Branch":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Rectangular")
            self.shape_combo.blockSignals(False)
        
        if tee_type == "Rect Main Rect Branch":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Rectangular")
            self.shape_combo.blockSignals(False)
        
        if tee_type == "Rectangular Angled Branch":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Rectangular")
            self.shape_combo.blockSignals(False)
        
        if tee_type == "Rectangular Dovetail Wye":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Rectangular")
            self.shape_combo.blockSignals(False)
        
        if tee_type == "Converging Wye":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Rectangular")
            self.shape_combo.blockSignals(False)
        
        # Fix #10: Conical Wye Round - W1 min 100, W2 min 150
        if tee_type == "Conical Wye Round":
            self.w_input.setMinimum(100)
            self.w2_input.setMinimum(150)
        else:
            self.w_input.setMinimum(50)
            self.w2_input.setMinimum(10)
        
        self.toggle_ui()
        self.update_preview()

    def on_wye_type_changed(self, *args):
        wye_type = self.wye_type_combo.currentText()
        
        # Also update the main tee_type_combo so geometry builder receives the right type
        self.tee_type_combo.blockSignals(True)
        self.tee_type_combo.setCurrentText(wye_type)
        self.tee_type_combo.blockSignals(False)
        
        # Set branch dimensions to half of W1 for standard Wyes
        if wye_type in ["Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Rectangular Angled Branch", "Conical Wye Round"]:
            val = self.w_input.value()
            self.w3_input.blockSignals(True)
            self.w3_input.setValue(val / 2.0)
            self.w3_input.blockSignals(False)
            
        # FIX: Set branch dimensions to full W1 for Dovetail
        elif wye_type == "Rectangular Dovetail Wye":
            val = self.w_input.value()
            self.w3_input.blockSignals(True)
            self.w3_input.setValue(val)
            self.w3_input.blockSignals(False)
            
            if wye_type == "Conical Wye Round":
                self.w2_input.blockSignals(True)
                self.w2_input.setValue(val * 2)
                """self.w2_input.setMinimum(val)"""
                self.w2_input.blockSignals(False)
        
        # Set D3 = D1 for rectangular branch types
        if wye_type in ["Rect Main Rect Branch", "Rectangular Angled Branch"]:
            d1_val = self.d_input.value()
            self.d3_input.blockSignals(True)
            self.d3_input.setValue(d1_val)
            self.d3_input.blockSignals(False)
        
        # Set profile based on wye type
        if wye_type == "Converging Wye Round":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Circular")
            self.shape_combo.blockSignals(False)
        elif wye_type == "Rect Main Round Branch":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Rectangular")
            self.shape_combo.blockSignals(False)
        elif wye_type in ["Rect Main Rect Branch", "Rectangular Angled Branch"]:
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Rectangular")
            self.shape_combo.blockSignals(False)
        elif wye_type == "Conical Wye Round":
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentText("Circular")
            self.shape_combo.blockSignals(False)
            
        # Branch angle options
        if wye_type == "Converging Wye Round":
            self.wye_branch_angle_combo.blockSignals(True)
            current = self.wye_branch_angle_combo.currentText()
            self.wye_branch_angle_combo.clear()
            self.wye_branch_angle_combo.addItems(["45", "90"])
            self.wye_branch_angle_combo.setCurrentText(current if current in ["45", "90"] else "45")
            self.wye_branch_angle_combo.blockSignals(False)
        elif wye_type == "Conical Wye Round":
            self.wye_branch_angle_combo.blockSignals(True)
            current = self.wye_branch_angle_combo.currentText()
            self.wye_branch_angle_combo.clear()
            self.wye_branch_angle_combo.addItems(["45"])
            self.wye_branch_angle_combo.setCurrentText(current if current in ["45"] else "45")
            self.wye_branch_angle_combo.blockSignals(False)
        else:
            self.wye_branch_angle_combo.blockSignals(True)
            current = self.wye_branch_angle_combo.currentText()
            self.wye_branch_angle_combo.clear()
            self.wye_branch_angle_combo.addItems(["45"])
            self.wye_branch_angle_combo.setCurrentText(current if current in ["45"] else "45")
            self.wye_branch_angle_combo.blockSignals(False)
        
        """# Min value fixes for Wye types
        if wye_type == "Conical Wye Round":
            self.w_input.setMinimum(100)
            self.w2_input.setMinimum(150)
        else:
            self.w_input.setMinimum(50)
            self.w2_input.setMinimum(10)"""
        
        self.toggle_ui()
        self.update_preview()

    def auto_calc_transition_length(self, *args):
        cat = self.category_combo.currentText()
        
        # Only run for Transitions category
        if cat != "Transitions":
            return
            
        is_auto = self.auto_len_cb.isChecked()
        self.p_label.setVisible(is_auto)
        self.p_input.setVisible(is_auto)
        self.straight_len_input.setEnabled(not is_auto)
        
        if is_auto and self.category_combo.currentText() == "Transitions":
            w1 = self.w_input.value()
            d1 = self.d_input.value() if self.shape_combo.currentText() != "Circular" else w1
            w2 = self.w2_input.value()
            d2 = self.d2_input.value() if self.shape_combo.currentText() != "Circular" else w2
            
            theta_rad = math.radians(self.p_input.value())
            align = self.align_combo.currentText()
            diff_w = abs(w1 - w2)
            diff_d = abs(d1 - d2)
            
            if align == "Concentric":
                req_L_w = (diff_w / 2.0) / math.tan(theta_rad / 2.0) if theta_rad > 0.001 and diff_w > 0 else 0
                req_L_d = (diff_d / 2.0) / math.tan(theta_rad / 2.0) if theta_rad > 0.001 and diff_d > 0 else 0
            else:
                max_off_w = diff_w if "Left" in align or "Right" in align else diff_w / 2.0
                max_off_d = diff_d if "Top" in align or "Bottom" in align else diff_d / 2.0
                ang_w = theta_rad if "Left" in align or "Right" in align else theta_rad / 2.0
                ang_d = theta_rad if "Top" in align or "Bottom" in align else theta_rad / 2.0
                req_L_w = max_off_w / math.tan(ang_w) if ang_w > 0.001 and max_off_w > 0 else 0
                req_L_d = max_off_d / math.tan(ang_d) if ang_d > 0.001 and max_off_d > 0 else 0
                
            calc_L = max(req_L_w, req_L_d, 1.0)
            self.straight_len_input.blockSignals(True)
            self.straight_len_input.setValue(calc_L)
            self.straight_len_input.blockSignals(False)
        self.update_preview()

    def auto_calc_drop(self, *args):
        is_auto = self.auto_drop_cb.isChecked()
        self.drop_h_input.setEnabled(not is_auto)
        self.drop_l_input.setEnabled(not is_auto)

        if is_auto and self.category_combo.currentText() == "Drop/Rise Elbow":
            d1 = self.d_input.value() if self.shape_combo.currentText() != "Circular" else self.w_input.value()
            self.drop_h_input.blockSignals(True)
            self.drop_l_input.blockSignals(True)
            self.drop_h_input.setValue(-d1 * 1.5)
            self.drop_l_input.setValue(d1 * 2.0)
            self.drop_h_input.blockSignals(False)
            self.drop_l_input.blockSignals(False)
        self.update_preview()

    def reset_roll_angle(self, *args):
        self.roll_input.blockSignals(True)
        self.roll_input.setValue(0.0)
        self.roll_input.blockSignals(False)
        self.update_preview()

    # Fix #9: Reset inputs on Category change
    def reset_inputs(self, *args):
        # Reset to default values
        self.w_input.setValue(100.0)
        self.d_input.setValue(100.0)
        self.w2_input.setValue(100.0)
        self.d2_input.setValue(100.0)
        self.t_input.setValue(2.0)
        self.roll_input.setValue(0.0)
        self.vanes_input.setValue(0)
        self.gores_input.setValue(5)
        self.angle_input.setValue(90.0)
        self.b_input.setValue(100.0)
        self.w3_input.setValue(100.0)
        self.d3_input.setValue(100.0)
        self.w4_input.setValue(100.0)
        self.d4_input.setValue(100.0)
        self.main_len_input.setValue(100.0)
        self.branch_len_input.setValue(100.0)
        self.off_dist_input.setValue(150.0)
        self.off_len_input.setValue(300.0)
        self.drop_h_input.setValue(-150.0)
        self.drop_l_input.setValue(200.0)
        self.straight_len_input.setValue(100.0)
        self.shape_combo.setCurrentText("Rectangular")
        self.shape2_combo.setCurrentText("Rectangular")
        self.const_combo.setCurrentText("Smooth")
        self.tee_type_combo.setCurrentText("Y-Branch")
        self.align_combo.setCurrentText("Concentric")
        self.wye_angle_combo.setCurrentText("45")
        self.auto_len_cb.setChecked(True)
        self.auto_drop_cb.setChecked(False)
        self.update_preview()

    def toggle_ui(self):
        cat = self.category_combo.currentText()
        shape = self.shape_combo.currentText()
        is_route = (cat == "Route (Follow Edges)")
        is_circ = (shape == "Circular" or shape == "Match Selected Face")
        tee_type = self.tee_type_combo.currentText()

        # D1 visibility - hide for Circular base profile (all categories)
        self.d_label.setVisible(not is_circ)
        self.d_input.setVisible(not is_circ)
        
        # W1 visibility - hide for Match Selected Face (use detected dimensions)
        show_w1 = shape != "Match Selected Face"
        self.w_label.setVisible(show_w1)
        self.w_input.setVisible(show_w1)

        # Show/hide category-specific frames in Duct Dimensions
        is_straight_or_transition = cat in ["Straight Duct", "Transitions"]
        self.straight_frame.setVisible(is_straight_or_transition)
        if not is_straight_or_transition:
            self.auto_len_cb.blockSignals(True)
            self.auto_len_cb.setChecked(False)
            self.auto_len_cb.blockSignals(False)
        self.elbow_frame.setVisible(cat == "Elbow" or is_route)
        self.offset_frame.setVisible(cat == "Offset")
        self.drop_frame.setVisible(cat == "Drop/Rise Elbow")

        # Show/hide Branch group (only for Tee category)
        self.branch_group.setVisible(cat == "Tee")

        # Show/hide Convergence/Divergence group (only for Tee category)
        self.wye_group.setVisible(cat == "Tee")
        
        # Wye group visibility based on category
        wye_type = self.wye_type_combo.currentText() if hasattr(self, 'wye_type_combo') else ""
        
        # Tee Type visibility - show for Tee and Route
        show_tee_type = (cat == "Tee" or is_route)
        self.tee_type_label.setVisible(show_tee_type)
        self.tee_type_combo.setVisible(show_tee_type)
        
        # Target Profile visibility - show only for Transitions
        show_target_profile = (cat == "Transitions")
        self.target_profile_label.setVisible(show_target_profile)
        self.shape2_combo.setVisible(show_target_profile)
        
        # Transition-specific controls visibility (Alignment, Auto-Length, Divergence Angle)
        # Only show for Transitions category
        is_transition = (cat == "Transitions")
        self.align_label.setVisible(is_transition)  # "Transition Alignment:"
        self.align_combo.setVisible(is_transition)
        self.auto_len_cb.setVisible(is_transition)
        self.p_label.setVisible(is_transition)  # Max Divergence Angle
        self.p_input.setVisible(is_transition)  # Max Divergence Angle
        
        const = self.const_combo.currentText()
        
        # Gores visibility - show when Segmented and not Offset
        show_gores = (const == "Segmented" and cat != "Offset")
        self.gores_label.setVisible(show_gores)
        self.gores_input.setVisible(show_gores)
        
        # Construction visibility - hide for Straight Duct and Transitions
        show_const = cat not in ["Straight Duct", "Transitions"]
        self.const_label.setVisible(show_const)
        self.const_combo.setVisible(show_const)
        
        # Splitter Vanes visibility - show for Elbow or Tee with T Branch
        show_vanes = (cat == "Elbow" or (cat == "Tee" and tee_type == "T Branch")) and not is_circ
        self.vanes_label.setVisible(show_vanes)
        self.vanes_input.setVisible(show_vanes)
        
        # W2/D2 visibility - hide for Straight Duct, show for Transitions and Tee
        hide_trunk_exit = (cat == "Straight Duct") or (cat == "Tee" and tee_type in ["Y-Branch", "T Branch", "Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Rectangular Angled Branch", "Rectangular Dovetail Wye", "Converging Wye", "Rectangular Wye", "Circular Wye"]) or is_route
        
        self.w2_label.setVisible(not hide_trunk_exit)
        self.w2_input.setVisible(not hide_trunk_exit)
        
        # For Transitions: use target profile from shape2_combo
        # For Straight Duct: same as base profile (no separate target)
        # For other categories: use base profile
        if cat == "Transitions":
            prof2 = self.shape2_combo.currentText()
        elif cat == "Straight Duct":
            prof2 = shape  # Same as base profile
        else:
            prof2 = shape
        
        is_circ2 = (prof2 == "Circular")
        self.d2_label.setVisible(not is_circ2 and not hide_trunk_exit)
        self.d2_input.setVisible(not is_circ2 and not hide_trunk_exit)
        
        # Bend radius visibility based on construction
        self.b_label.setVisible(const == "Segmented")
        self.b_input.setVisible(const == "Segmented")

        # Branch controls visibility based on tee type
        show_opp = (tee_type in ["Y-Branch", "Cross Tee", "Circular Wye"])
        self.w4_label.setVisible(show_opp)
        self.w4_input.setVisible(show_opp)
        self.d4_label.setVisible(show_opp and not is_circ)
        self.d4_input.setVisible(show_opp and not is_circ)

        show_w3_d3 = tee_type not in ["Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Rectangular Dovetail Wye"]
        self.w3_label.setVisible(show_w3_d3)
        self.w3_input.setVisible(show_w3_d3)
        self.d3_label.setVisible(show_w3_d3 and not is_circ)
        self.d3_input.setVisible(show_w3_d3 and not is_circ)

        show_wye_angle = tee_type in ["Rectangular Wye", "Converging Wye Round", "Conical Wye Round", "Converging Wye", "Rectangular Angled Branch", "Rectangular Dovetail Wye"]
        self.wye_angle_label.setVisible(show_wye_angle)
        self.wye_angle_combo.setVisible(show_wye_angle)
        
        # Main/Branch length visibility for Tee
        show_main_branch_len = (cat == "Tee")
        self.main_len_label.setVisible(show_main_branch_len)
        self.main_len_input.setVisible(show_main_branch_len)
        self.branch_len_label.setVisible(show_main_branch_len)
        self.branch_len_input.setVisible(show_main_branch_len)
        
        if tee_type == "Rectangular Wye":
            self.wye_angle_combo.blockSignals(True)
            current = self.wye_angle_combo.currentText()
            self.wye_angle_combo.clear()
            self.wye_angle_combo.addItems(["45", "30", "15"])
            self.wye_angle_combo.setCurrentText(current if current in ["45", "30", "15"] else "45")
            self.wye_angle_combo.blockSignals(False)
            
            self.on_wye_angle_changed()
        elif tee_type == "Converging Wye Round":
            self.wye_angle_combo.blockSignals(True)
            current = self.wye_angle_combo.currentText()
            self.wye_angle_combo.clear()
            self.wye_angle_combo.addItems(["45", "90"])
            self.wye_angle_combo.setCurrentText(current if current in ["45", "90"] else "45")
            self.wye_angle_combo.blockSignals(False)
        elif tee_type == "Conical Wye Round":
            self.wye_angle_combo.blockSignals(True)
            current = self.wye_angle_combo.currentText()
            self.wye_angle_combo.clear()
            self.wye_angle_combo.addItems(["45"])
            self.wye_angle_combo.setCurrentText(current if current in ["45"] else "45")
            self.wye_angle_combo.blockSignals(False)
        elif tee_type in ["Converging Wye", "Rectangular Angled Branch", "Rectangular Dovetail Wye"]:
            self.wye_angle_combo.blockSignals(True)
            current = self.wye_angle_combo.currentText()
            self.wye_angle_combo.clear()
            self.wye_angle_combo.addItems(["45"])
            self.wye_angle_combo.setCurrentText(current if current in ["45"] else "45")
            self.wye_angle_combo.blockSignals(False)

        if cat in ["Straight Duct", "Transitions"]: self.auto_calc_transition_length()
        elif cat == "Drop/Rise Elbow": self.auto_calc_drop()

    def update_preview(self, *args):
        class DummyDuct: pass
        dummy = DummyDuct()

        try:
            cat = self.category_combo.currentText()
            # Map UI categories to internal categories
            if cat == "Straight Duct":
                dummy.Category = "Straight"
            elif cat == "Transitions":
                dummy.Category = "Transitions"
            else:
                dummy.Category = cat
            
            tee_type = self.tee_type_combo.currentText()
            
            prof = self.shape_combo.currentText()
            if hasattr(self, 'has_selection') and self.has_selection and prof == "Match Selected Face":
                prof = getattr(self, 'detected_shape', "Rectangular")
            
            if tee_type == "Converging Wye Round":
                prof = "Circular"
            elif tee_type == "Circular Wye":
                prof = "Circular"
            elif tee_type == "Rectangular Wye":
                prof = "Rectangular"
            
            dummy.Profile = prof
            # For Straight: Profile2 = Profile (same)
            # For Transitions: allow different Profile2
            if dummy.Category == "Straight":
                dummy.Profile2 = dummy.Profile
            elif dummy.Category == "Transitions":
                dummy.Profile2 = self.shape2_combo.currentText()
            else:
                dummy.Profile2 = dummy.Profile
            
            dummy.Construction = self.const_combo.currentText()
            dummy.TeeType = self.tee_type_combo.currentText()
            # Alignment only for Transitions category
            dummy.Alignment = self.align_combo.currentText() if dummy.Category == "Transitions" else "Concentric"
            
            is_branch_circular = (dummy.TeeType in ["Rect Main Round Branch", "Converging Wye Round", "Conical Wye Round", "Circular Wye"])
            
            # --- CRITICAL FIX: Removed "self.has_selection" override. UI is the law. ---
            dummy.W1 = float(self.w_input.value())
            dummy.D1 = float(self.d_input.value()) if dummy.Profile != "Circular" else dummy.W1

            dummy.W2 = float(self.w2_input.value())
            dummy.D2 = float(self.d2_input.value()) if dummy.Profile2 != "Circular" else dummy.W2
            
            # For Straight Duct, force W2=W1, D2=D1 internally
            if dummy.Category == "Straight":
                dummy.W2 = dummy.W1
                dummy.D2 = dummy.D1
                
            dummy.W3 = float(self.w3_input.value())
            dummy.D3 = float(self.d3_input.value()) if not is_branch_circular else dummy.W3
            dummy.W4 = float(self.w4_input.value())
            dummy.D4 = float(self.d4_input.value()) if dummy.Profile != "Circular" else dummy.W4
            
            dummy.Thickness = float(self.t_input.value())
            dummy.CornerRadius = 0.0 
            dummy.RollAngle = float(self.roll_input.value())    
            
            dummy.StraightLength = float(self.straight_len_input.value())
            dummy.BendAngle = float(self.angle_input.value())
            dummy.BendRadius = float(self.b_input.value())
            dummy.Gores = int(self.gores_input.value())
            dummy.SplitterVanes = int(self.vanes_input.value()) 
            
            dummy.BranchAngle = 90.0
            dummy.BranchRadius = min(dummy.W1, dummy.W3) * 0.5
            
            # Set MainLength and BranchLength for ALL tees
            dummy.MainLength = float(self.main_len_input.value())
            dummy.BranchLength = float(self.branch_len_input.value())
            
            # Set WyeBranchAngle for angled tees
            wye_types = ["Rectangular Wye", "Converging Wye Round", "Conical Wye Round", "Converging Wye", "Rectangular Angled Branch"]
            if dummy.TeeType in wye_types:
                if cat == "Tee":
                    # Use Wye group angle if on Tee category
                    dummy.WyeBranchAngle = self.wye_branch_angle_combo.currentText()
                else:
                    dummy.WyeBranchAngle = self.wye_angle_combo.currentText()
                dummy.WyeBranchAngle = self.wye_angle_combo.currentText()
            
            # FIT TO BARE MINIMUM FOR TEES - TeeLength as fallback
            if dummy.TeeType == "Y-Branch":
                dummy.TeeLength = max(dummy.W3, dummy.W4) * 1.5
            elif dummy.TeeType in ["Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Conical Wye Round"]:
                dummy.TeeLength = dummy.W1 * 2
            else:
                dummy.TeeLength = max(dummy.W3, dummy.W4)
            
            dummy.DropH = float(self.drop_h_input.value())
            dummy.DropL = float(self.drop_l_input.value())
            dummy.OffsetDist = float(self.off_dist_input.value())
            dummy.OffsetLen = float(self.off_len_input.value())

            if hasattr(self, 'center'):
                dummy.BaseCenter = self.center
                dummy.BaseNormal = self.normal
                dummy.BaseX = self.local_X
                dummy.BaseY = self.local_Y
            else:
                
                dummy.BaseCenter = App.Vector(0,0,0)
                dummy.BaseNormal = App.Vector(0,1,0)
                dummy.BaseX = App.Vector(1,0,0)
                dummy.BaseY = App.Vector(0,0,1)
                
            dummy.PathEdges = getattr(self, 'path_links', [])
            dummy.IsRouted = False

            preview_shape = build_duct_shape(dummy)
            if preview_shape and not preview_shape.isNull():
                self.preview_obj.Shape = preview_shape
        except Exception as e:
            
            App.Console.PrintError(f"Preview Generation Error: {str(e)}\n")

    def get_or_create_group(self, doc, parent, folder_name):
        if not parent: return None
        for obj in parent.Group:
            if obj.Name == folder_name or obj.Label == folder_name:
                return obj
        sub_group = doc.addObject("App::DocumentObjectGroup", folder_name)
        parent.addObject(sub_group)
        return sub_group

    def accept(self):
        if not self.preview_obj.Shape or self.preview_obj.Shape.isNull():
            App.Console.PrintError("Cannot finalize: Geometry is invalid.\n")
            App.ActiveDocument.abortTransaction()
            Gui.Control.closeDialog()
            return
            
        try:
            doc = App.ActiveDocument
            cat_txt = self.category_combo.currentText()
            # Map UI categories to internal categories
            if cat_txt == "Straight Duct":
                param_cat = "Straight"
            elif cat_txt == "Transitions":
                param_cat = "Transitions"
            else:
                param_cat = cat_txt
            
            tee_style = self.tee_type_combo.currentText()
            
            prof = self.shape_combo.currentText()
            if hasattr(self, 'has_selection') and self.has_selection and prof == "Match Selected Face":
                prof = getattr(self, 'detected_shape', "Rectangular")
            
            if tee_style == "Converging Wye Round":
                prof = "Circular"

            if tee_style == "Circular Wye":
                prof = "Circular"

            const_txt = self.const_combo.currentText()
            
            main_group = doc.getObject("Duct_System")
            if not main_group:
                main_group = doc.addObject("App::DocumentObjectGroup", "Duct_System")
                
            # --- CRITICAL FIX: Removed "self.has_selection" override! ---
            W = float(self.w_input.value())
            D = float(self.d_input.value()) if prof != "Circular" else W
            T = float(self.t_input.value())
            
            if param_cat == "Route (Follow Edges)":
                # v1.6.2 FIX 1: Fetch branch dimensions explicitly so they are in memory!
                W3_val = float(self.w3_input.value()) if hasattr(self, 'w3_input') else W
                D3_val = float(self.d3_input.value()) if hasattr(self, 'd3_input') else D
                W4_val = float(self.w4_input.value()) if hasattr(self, 'w4_input') else W
                D4_val = float(self.d4_input.value()) if hasattr(self, 'd4_input') else D
                

                edges = []
                for item in self.path_links:
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
                        
                if edges:
                    raw_lines = []
                    for edge in edges:
                        if hasattr(edge, "Curve") and 'Line' in str(type(edge.Curve).__name__):
                            raw_lines.append((edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)))
                        elif hasattr(edge, "Vertexes") and len(edge.Vertexes) >= 2:
                            raw_lines.append((edge.Vertexes[0].Point, edge.Vertexes[-1].Point))

                    # v1.6.2 FIX 2: Deep Scan for the true Sketch Plane
                    route_up = App.Vector(0,0,1)
                    found_plane = False
                    for i in range(len(raw_lines)):
                        for j in range(i+1, len(raw_lines)):
                            v1 = (raw_lines[i][1] - raw_lines[i][0]).normalize()
                            v2 = (raw_lines[j][1] - raw_lines[j][0]).normalize()
                            cv = v1.cross(v2)
                            if cv.Length > 0.01:
                                route_up = cv.normalize()
                                found_plane = True
                                break
                        if found_plane: break
                    if route_up.z < 0 and abs(route_up.z) > 0.5: route_up = -route_up

                    adj = {}
                    edge_sizes = {}
                    orig_dirs = {}
                    for p1, p2 in raw_lines:
                        k1 = (round(p1.x, 2), round(p1.y, 2), round(p1.z, 2))
                        k2 = (round(p2.x, 2), round(p2.y, 2), round(p2.z, 2))
                        if k1 not in adj: adj[k1] = []
                        if k2 not in adj: adj[k2] = []
                        adj[k1].append(k2); adj[k2].append(k1)
                        edge_sizes[tuple(sorted([k1, k2]))] = (W, D)
                        orig_dirs[(k1, k2)] = (p2 - p1).normalize()
                        orig_dirs[(k2, k1)] = (p1 - p2).normalize()

                    vertices = {}
                    for p1, p2 in raw_lines:
                        k1 = (round(p1.x, 2), round(p1.y, 2), round(p1.z, 2))
                        k2 = (round(p2.x, 2), round(p2.y, 2), round(p2.z, 2))
                        if k1 not in vertices: vertices[k1] = []
                        if k2 not in vertices: vertices[k2] = []
                        vertices[k1].append((p2 - p1).normalize())
                        vertices[k2].append((p1 - p2).normalize())

                    true_nodes = {k: App.Vector(*k) for k in adj.keys()}
                    shifts = []
                    custom_ports = {}
                    pullbacks = {} # v1.12.0: Restored Pullbacks to stop Trunk overlaps!
                    fittings_map = {}

                    b_rad = float(self.b_input.value())
                    grp_straight = self.get_or_create_group(doc, main_group, "Straights")
                    grp_elbow = self.get_or_create_group(doc, main_group, "Elbows")
                    grp_tee = self.get_or_create_group(doc, main_group, "Tees")

                    # PASS 1: GENERATE TEES & POPULATE PULLBACKS
                    for pt_key, vectors in vertices.items():
                        degree = len(vectors)
                        pt = true_nodes[pt_key]
                        
                        if degree in [3, 4]:
                            v_col1 = None; v_col2 = None; v_perp = None
                            for i in range(degree):
                                for j in range(i+1, degree):
                                    if abs(vectors[i].getAngle(vectors[j]) - math.pi) < 0.1:
                                        v_col1 = vectors[i]; v_col2 = vectors[j]
                                        branches = [v for k, v in enumerate(vectors) if k not in (i,j)]
                                        v_perp = branches[0] if branches else None
                                        break
                                if v_col1: break
                                
                            bullhead_types = ["Y-Branch", "Rectangular Dovetail Wye", "Rectangular Wye", "Circular Wye"]
                            
                            if v_col1 and v_perp:
                                if any(b in tee_style for b in bullhead_types):
                                    v_m2 = v_perp; v_b1 = v_col1 
                                else:
                                    v_m2 = v_col2; v_b1 = v_perp 
                            else:
                                min_ang = 999; b1 = 0; b2 = 1
                                for i in range(degree):
                                    for j in range(i+1, degree):
                                        ang = vectors[i].getAngle(vectors[j])
                                        if ang < min_ang: min_ang = ang; b1 = i; b2 = j
                                trunk_idx = [k for k in range(3) if k not in (b1, b2)][0]
                                v_m2 = vectors[trunk_idx]; v_b1 = vectors[b1]

                            base_normal = -v_m2
                            base_x = route_up.cross(base_normal).normalize()
                            if base_x.Length < 0.001: base_x = App.Vector(1,0,0)
                            
                            br_ang = 90.0 if not v_b1 else math.degrees(base_normal.getAngle(v_b1))
                            br_rad = min(W, W3_val) * 0.5
                            
                            # v2.7.1 FIX: Directly harvest and apply the UI's Zero-Lengths!
                            main_len_val = float(self.main_len_input.value())
                            branch_len_val = float(self.branch_len_input.value())
                            
                            t_len = main_len_val if main_len_val > 0.001 else 0.1
                            b_len = branch_len_val if branch_len_val > 0.001 else 0.1
                        
                            
                            # // STEP: Set correct center for fittings so branches align with sketch lines
                            if "Dovetail" in tee_style:
                                t_center = pt - base_normal * W
                            else:
                                # Y-Branch and standard tees anchor perfectly to the Vertex
                                t_center = pt

                            new_obj = doc.addObject("Part::FeaturePython", "Parametric_Tee")
                            ParametricDuct(new_obj)
                            new_obj.Category = "Tee"; new_obj.IsRouted = True
                            new_obj.RouteVertex = pt; new_obj.BaseCenter = t_center
                            new_obj.BaseNormal = base_normal; new_obj.BaseY = route_up; new_obj.BaseX = base_x
                            new_obj.Construction = const_txt; new_obj.Profile = prof
                            new_obj.TeeType = tee_style if degree == 3 else "Cross Tee"
                            new_obj.W1 = W; new_obj.D1 = D; new_obj.W2 = W; new_obj.D2 = D
                            new_obj.W3 = W3_val; new_obj.D3 = D3_val; new_obj.W4 = W4_val; new_obj.D4 = D4_val
                            new_obj.Thickness = T; new_obj.CornerRadius = 0.0
                            new_obj.BranchAngle = br_ang; new_obj.BranchRadius = br_rad; 
                            
                            # Bake lengths into the Parametric Object
                            new_obj.TeeLength = t_len
                            new_obj.MainLength = main_len_val
                            new_obj.BranchLength = branch_len_val

                            # CRITICAL FIX 1: Bake the Wye Angle so it doesn't default to 15 degrees!
                            wye_types = ["Rectangular Wye", "Converging Wye Round", "Conical Wye Round", "Converging Wye", "Rectangular Angled Branch"]
                            if new_obj.TeeType in wye_types:
                                new_obj.WyeBranchAngle = self.wye_angle_combo.currentText()

                            if any(b in tee_style for b in bullhead_types):
                                # CRITICAL FIX 2: Restore the '0.0' Y-Branch trunk logic to match the Preview!
                                trunk_len = 0.0 if "Y-Branch" in tee_style else (t_len if "Dovetail" in tee_style else max(t_len / 2.0, 10.0))
                                
                                for v in vectors:
                                    if abs(v.dot(base_normal)) > 0.9: 
                                        for nbr in adj[pt_key]:
                                            if orig_dirs[(pt_key, nbr)].getAngle(v) < 0.01:
                                                # // STEP: Trunk pullback
                                                pb_tee = (W + trunk_len) if "Dovetail" in tee_style else trunk_len
                                                pullbacks[(pt_key, nbr)] = pb_tee
                                                break
                                        continue 
                                        
                                    for nbr in adj[pt_key]:
                                        if orig_dirs[(pt_key, nbr)].getAngle(v) < 0.01:
                                            is_right = v.dot(base_x) > 0
                                            edge_sizes[tuple(sorted([pt_key, nbr]))] = (W4_val, D4_val) if is_right else (W3_val, D3_val)
                                            
                                            # // STEP: Branch pullbacks for bullheads
                                            if "Dovetail" in tee_style:
                                                w_b = W4_val if is_right else W3_val
                                                pb_branch = 1.5 * W - (w_b / 2.0) + b_len
                                            else:
                                                pb_branch = trunk_len + b_len
                                            pullbacks[(pt_key, nbr)] = pb_branch
                                            break
                            else:
                                for v in vectors:
                                    for nbr in adj[pt_key]:
                                        if orig_dirs[(pt_key, nbr)].getAngle(v) < 0.01:
                                            if abs(v.dot(base_normal)) > 0.9: 
                                                pb_tee = t_len / 2.0
                                                pullbacks[(pt_key, nbr)] = pb_tee
                                            else:
                                                is_right = v.dot(base_x) > 0
                                                edge_sizes[tuple(sorted([pt_key, nbr]))] = (W4_val, D4_val) if is_right else (W3_val, D3_val)
                                                
                                                if "Angled Branch" in tee_style:
                                                    hyp = (W / 2.0) / math.sin(math.radians(br_ang)) if br_ang > 0.1 else 0
                                                    pb_branch = hyp + ((W4_val if is_right else W3_val) / 2.0) + b_len
                                                    pullbacks[(pt_key, nbr)] = pb_branch
                                                else:
                                                    pb_branch = (W / 2.0) + b_len
                                                    pullbacks[(pt_key, nbr)] = pb_branch
                                            break

                            if new_obj.ViewObject: new_obj.ViewObject.Proxy = 0; new_obj.ViewObject.ShapeColor = (0.6, 0.6, 0.6)
                            new_obj.Proxy.execute(new_obj); grp_tee.addObject(new_obj)
                            fittings_map[pt_key] = new_obj

                    # PASS 2: PROPAGATE SHIFTS
                    tee_groups = {}
                    for t_key, b_key, s_vec in shifts:
                        if t_key not in tee_groups: tee_groups[t_key] = []
                        tee_groups[t_key].append((b_key, s_vec))
                        
                    for t_key, branch_shifts in tee_groups.items():
                        visited = {t_key} 
                        for b_key, s_vec in branch_shifts:
                            queue = [b_key]
                            while queue:
                                curr = queue.pop(0)
                                if curr not in visited:
                                    visited.add(curr)
                                    true_nodes[curr] = true_nodes[curr] + s_vec
                                    for nbr in adj[curr]:
                                        if nbr not in visited: queue.append(nbr)

                    # PASS 3: GENERATE ELBOWS & POPULATE PULLBACKS
                    for pt_key, vectors in vertices.items():
                        degree = len(vectors)
                        pt = true_nodes[pt_key] 
                        
                        if degree == 2:
                            v_in = -vectors[0]; v_out = vectors[1]
                            angle = math.degrees(v_in.getAngle(v_out))
                            if angle < 0.1 or abs(angle - 180) < 0.1: continue
                            
                            cross = v_in.cross(v_out)
                            elbow_up = cross.normalize() if cross.Length > 0.01 else route_up
                            
                            nbr1 = None; nbr2 = None
                            for n in adj[pt_key]:
                                if orig_dirs[(pt_key, n)].getAngle(vectors[0]) < 0.01: nbr1 = n
                                elif orig_dirs[(pt_key, n)].getAngle(vectors[1]) < 0.01: nbr2 = n
                                
                            w_e1, d_e1 = edge_sizes[tuple(sorted([pt_key, nbr1]))] if nbr1 else (W, D)
                            w_e2, d_e2 = edge_sizes[tuple(sorted([pt_key, nbr2]))] if nbr2 else (W, D)
                            w_max = max(w_e1, w_e2)
                            
                            if const_txt == "Smooth":
                                r = w_max * 1.0
                            elif const_txt == "Segmented":
                                r = max(b_rad, (w_max / 2.0) + 0.1)
                            else:
                                r = max(b_rad, w_max / 2.0)
                                
                            pb = r * math.tan(math.radians(angle) / 2.0)
                            
                            if nbr1: pullbacks[(pt_key, nbr1)] = pb
                            if nbr2: pullbacks[(pt_key, nbr2)] = pb

                            new_obj = doc.addObject("Part::FeaturePython", "Parametric_Elbow")
                            ParametricDuct(new_obj)
                            new_obj.Category = "Elbow"; new_obj.IsRouted = True
                            new_obj.RouteVertex = pt

                            # CRITICAL FIX 3: Actually assign the Construction and Profile so it stops defaulting!
                            new_obj.Construction = const_txt
                            new_obj.Profile = prof
                            new_obj.RouteVertex = pt

                            # UNIFIED ARCHITECTURE: All elbows anchor to Pullback
                            new_obj.BaseCenter = pt - v_in * pb
                                
                            new_obj.BaseNormal = v_in; new_obj.BaseY = elbow_up
                            new_obj.BaseX = elbow_up.cross(v_in).normalize()
                            
                            # Assign the individual properties to support Reducing Elbows!
                            new_obj.W1 = w_e1; new_obj.D1 = d_e1; new_obj.W2 = w_e2; new_obj.D2 = d_e2
                            
                            new_obj.Thickness = T; new_obj.CornerRadius = 0.0
                            new_obj.BendAngle = angle; new_obj.BendRadius = r
                            new_obj.SplitterVanes = int(self.vanes_input.value()); new_obj.Gores = int(self.gores_input.value())
                            
                            if new_obj.ViewObject: new_obj.ViewObject.Proxy = 0; new_obj.ViewObject.ShapeColor = (0.6, 0.6, 0.6)
                            new_obj.Proxy.execute(new_obj); grp_elbow.addObject(new_obj)
                            fittings_map[pt_key] = new_obj

                    # PASS 4: GENERATE STRAIGHT DUCTS
                    processed_edges = set()
                    for p1, p2 in raw_lines:
                        k1 = (round(p1.x, 2), round(p1.y, 2), round(p1.z, 2))
                        k2 = (round(p2.x, 2), round(p2.y, 2), round(p2.z, 2))
                        edge_id = tuple(sorted([k1, k2]))
                        if edge_id in processed_edges: continue
                        processed_edges.add(edge_id)
                        
                        v_dir_orig = orig_dirs[(k1, k2)]
                        
                        # v2.7.0 FIX: Apply the pullbacks here so they are baked into RouteP1!
                        if (k1, k2) in custom_ports:
                            p_start, v_dir_eff = custom_ports[(k1, k2)]
                        else:
                            p_start = true_nodes[k1] + v_dir_orig * pullbacks.get((k1, k2), 0.0)
                            v_dir_eff = v_dir_orig
                            
                        if (k2, k1) in custom_ports:
                            p_end, _ = custom_ports[(k2, k1)]
                        else:
                            p_end = true_nodes[k2] - v_dir_eff * pullbacks.get((k2, k1), 0.0)
                            
                        length = (p_end - p_start).dot(v_dir_eff)
                        if length < 0.1: length = (p_end - p_start).Length 

                        w_edge, d_edge = edge_sizes.get(edge_id, (W, D))
                        straight_up = route_up - route_up.dot(v_dir_eff) * v_dir_eff
                        if straight_up.Length < 0.001: straight_up = App.Vector(0,0,1)
                        else: straight_up.normalize()
                        
                        new_straight = doc.addObject("Part::FeaturePython", "Parametric_Straight")
                        ParametricDuct(new_straight)
                        new_straight.Category = "Straight"; new_straight.Profile = prof
                        new_straight.IsRouted = True
                        new_straight.RouteP1 = p_start; new_straight.RouteP2 = p_end
                        new_straight.BaseNormal = v_dir_eff; new_straight.BaseY = straight_up
                        new_straight.BaseX = straight_up.cross(v_dir_eff).normalize()
                        new_straight.W1 = w_edge; new_straight.D1 = d_edge; new_straight.W2 = w_edge; new_straight.D2 = d_edge
                        new_straight.Thickness = T; new_straight.CornerRadius = 0.0
                        
                        # v2.7.0 FIX: Formally establish the Topological Graph!
                        if k1 in fittings_map: new_straight.StartFitting = fittings_map[k1]
                        if k2 in fittings_map: new_straight.EndFitting = fittings_map[k2]
                        
                        if new_straight.ViewObject: new_straight.ViewObject.Proxy = 0; new_straight.ViewObject.ShapeColor = (0.6, 0.6, 0.6)
                        new_straight.Proxy.execute(new_straight); grp_straight.addObject(new_straight)

                    for item in self.path_links:
                        obj = item[0] if isinstance(item, tuple) else item
                        if obj and hasattr(obj, "ViewObject") and obj.ViewObject: obj.ViewObject.hide()

            else:
                folder_map = {
                    "Straight": "Straights",
                    "Elbow": "Elbows",
                    "Tee": "Tees",
                    "Offset": "Offsets",
                    "Drop/Rise Elbow": "Drop_Elbows"
                }
                grp = self.get_or_create_group(doc, main_group, folder_map.get(param_cat, "Fittings"))
                
                new_obj = doc.addObject("Part::FeaturePython", f"Parametric_{param_cat.replace('/', '_').replace(' ', '_')}")
                ParametricDuct(new_obj)
                
                # --- MIRROR PREVIEW LOGIC: Use same calculation order as update_preview ---
                
                # 1. Set category (triggers update_visibility)
                new_obj.Category = param_cat

                # 2. Determine profile (same logic as preview)
                final_prof = prof  # prof already calculated above with tee_type overrides
                
                # 3. Determine Profile2 (same logic as preview)
                if param_cat == "Straight":
                    profile2 = final_prof
                elif param_cat == "Transitions":
                    profile2 = self.shape2_combo.currentText()
                else:
                    profile2 = final_prof
                
                # 4. Set automation flags FIRST (before dimensions that trigger calculations)
                if param_cat == "Transitions":
                    new_obj.AutoTransitionLength = self.auto_len_cb.isChecked()
                    new_obj.Alignment = self.align_combo.currentText()
                    new_obj.TransitionAngle = float(self.p_input.value())
                elif param_cat == "Drop/Rise Elbow":
                    new_obj.AutoDropSize = self.auto_drop_cb.isChecked()
                
                # 5. Set Profile and Profile2
                new_obj.Profile = final_prof
                new_obj.Profile2 = profile2
                new_obj.Construction = const_txt
                new_obj.TeeType = tee_style
                
                # 6. Calculate all dimensions (same as preview)
                W_val = float(self.w_input.value())
                D_val = float(self.d_input.value()) if final_prof != "Circular" else W_val
                
                W2_val = float(self.w2_input.value())
                D2_val = float(self.d2_input.value()) if profile2 != "Circular" else W2_val
                
                # For Straight Duct, force W2=W1, D2=D1
                if param_cat == "Straight":
                    W2_val = W_val
                    D2_val = D_val
                
                is_branch_circular = (tee_style in ["Rect Main Round Branch", "Converging Wye Round", "Conical Wye Round", "Circular Wye"])
                
                W3_val = float(self.w3_input.value())
                D3_val = float(self.d3_input.value()) if not is_branch_circular else W3_val
                W4_val = float(self.w4_input.value())
                D4_val = float(self.d4_input.value()) if final_prof != "Circular" else W4_val
                
                T_val = float(self.t_input.value())
                
                # 7. Set all dimensions
                new_obj.W1 = W_val
                new_obj.D1 = D_val
                new_obj.W2 = W2_val
                new_obj.D2 = D2_val
                new_obj.W3 = W3_val
                new_obj.D3 = D3_val
                new_obj.W4 = W4_val
                new_obj.D4 = D4_val
                
                new_obj.Thickness = T_val
                new_obj.CornerRadius = 0.0
                new_obj.RollAngle = float(self.roll_input.value())
                
                # 8. Set fitting-specific parameters
                new_obj.BendAngle = float(self.angle_input.value())
                new_obj.BendRadius = float(self.b_input.value())
                new_obj.Gores = int(self.gores_input.value())
                new_obj.SplitterVanes = int(self.vanes_input.value())
                
                new_obj.BranchAngle = 90.0
                new_obj.BranchRadius = min(W_val, W3_val) * 0.5
                
                # 9. Set MainLength and BranchLength (critical for tees)
                # Use same logic as preview - no artificial limits
                main_len_val = float(self.main_len_input.value())
                branch_len_val = float(self.branch_len_input.value())
                new_obj.MainLength = main_len_val
                new_obj.BranchLength = branch_len_val
                
                # 10. Set WyeBranchAngle for angled tees (same as preview)
                angled_tees = ["Rectangular Wye", "Converging Wye Round", "Conical Wye Round", "Converging Wye", "Rectangular Angled Branch", "Rectangular Dovetail Wye"]
                if tee_style in angled_tees:
                    if cat_txt == "Tee" and hasattr(self, 'wye_branch_angle_combo'):
                        new_obj.WyeBranchAngle = self.wye_branch_angle_combo.currentText()
                    else:
                        new_obj.WyeBranchAngle = self.wye_angle_combo.currentText()
                
                # 11. Set TeeLength (fallback calculation same as preview)
                if tee_style == "Y-Branch":
                    new_obj.TeeLength = max(W3_val, W4_val) * 1.5
                elif tee_style in ["Converging Wye Round", "Rect Main Round Branch", "Rect Main Rect Branch", "Conical Wye Round"]:
                    new_obj.TeeLength = W_val * 2
                else:
                    new_obj.TeeLength = max(W3_val, W4_val)
                
                # 12. Set offset/drop parameters
                new_obj.OffsetDist = float(self.off_dist_input.value())
                new_obj.OffsetLen = float(self.off_len_input.value())
                new_obj.DropH = float(self.drop_h_input.value())
                new_obj.DropL = float(self.drop_l_input.value())

                # 13. Set placement vectors
                if hasattr(self, 'center'):
                    new_obj.BaseCenter = self.center
                    new_obj.BaseNormal = self.normal
                    new_obj.BaseX = self.local_X
                    new_obj.BaseY = self.local_Y
                else:
                    new_obj.BaseCenter = App.Vector(0,0,0)
                    new_obj.BaseNormal = App.Vector(0,1,0)
                    new_obj.BaseX = App.Vector(1,0,0)
                    new_obj.BaseY = App.Vector(0,0,1)

                # 14. Assign StraightLength LAST to override any auto-calc
                new_obj.StraightLength = float(self.straight_len_input.value())

                # 15. Set visual properties
                if new_obj.ViewObject: 
                    new_obj.ViewObject.Proxy = 0
                    if hasattr(self, 'has_selection') and self.has_selection and self.obj and self.obj.ViewObject:
                        new_obj.ViewObject.ShapeColor = self.obj.ViewObject.ShapeColor
                    else:
                        new_obj.ViewObject.ShapeColor = (0.6, 0.6, 0.6) 
                
                # 16. Execute to generate geometry
                new_obj.Proxy.execute(new_obj)
                
                if grp:
                    grp.addObject(new_obj)
            
            if self.preview_obj:
                doc.removeObject(self.preview_obj.Name)

            doc.recompute()
            doc.commitTransaction()
            
        except Exception as e:
            App.ActiveDocument.abortTransaction()
            App.Console.PrintError(f"Failed to finalize fitting: {str(e)}\n")
            
        Gui.Control.closeDialog()

    # --- CRITICAL FIX: Removed manual deletion to stop the ReferenceError! ---
    def reject(self):
        App.ActiveDocument.abortTransaction()
        Gui.Control.closeDialog()
import ComfacUtils
class CommandDuctLibrary:
    def GetResources(self):
        return {
            'Pixmap' : ComfacUtils.get_icon_path("DuctLibrary.svg"),
            'MenuText': 'Duct Library',
            'ToolTip': 'Open Parametric Duct Fitting Library'
        }
    def Activated(self):
        panel = DuctLibraryTaskPanel()
        Gui.Control.showDialog(panel)

#Gui.addCommand('DuctLibrary', CommandDuctLibrary())