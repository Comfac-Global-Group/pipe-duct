import FreeCAD
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils

class PipeFittingTaskPanel:
    def __init__(self, pipe_obj, selected_points=None):
        try:
            self.pipe_obj = pipe_obj
            self.selected_points = selected_points if selected_points else []
            
            # Safely grab the primary sketch linked by the main generator
            self.sketch = None
            if hasattr(self.pipe_obj, "SketchName"):
                self.sketch = FreeCAD.ActiveDocument.getObject(self.pipe_obj.SketchName)
            
            if not self.sketch:
                FreeCAD.Console.PrintWarning("Warning: Linked Sketch not found. Fittings may not generate properly.\n")
            
            self.form = QtWidgets.QWidget()
            self.layout = QtWidgets.QFormLayout(self.form)
            
            # Safe property fetching with fallbacks to prevent NoneType errors
            self.pipe_od = getattr(self.pipe_obj, 'PipeOuter', 10.0)
            self.pipe_id = getattr(self.pipe_obj, 'PipeInner', 8.0)
            self.pipe_thick = (self.pipe_od - self.pipe_id) / 2.0
            if self.pipe_thick <= 0: self.pipe_thick = 1.0 # Prevent zero-thickness crashes
            
            self.detected_od = QtWidgets.QLabel(f"{self.pipe_od} mm")
            
            self.thick_input = QtWidgets.QDoubleSpinBox()
            self.thick_input.setRange(0.1, 100.0) # Safe minimum
            self.thick_input.setValue(self.pipe_thick * 1.5) 
            self.thick_input.setDecimals(2)
            self.thick_input.setSuffix(" mm")
            
            self.length_input = QtWidgets.QDoubleSpinBox()
            self.length_input.setRange(0.1, 1000.0) # Safe minimum
            self.length_input.setValue(self.pipe_od * 1.0) 
            self.length_input.setDecimals(2)
            self.length_input.setSuffix(" mm")
            
            # Prevent Division by zero
            self.wye_depth = 20.0 * (self.pipe_od / 13.7) if self.pipe_od > 0 else 20.0
            
            self.layout.addRow("Detected Pipe OD:", self.detected_od)
            self.layout.addRow("Fitting Wall Thickness:", self.thick_input)
            self.layout.addRow("User Socket Depth (Tee/90):", self.length_input)
            self.layout.addRow("Wye Socket Depth (45 deg):", QtWidgets.QLabel(f"Auto-Scaled to {self.wye_depth:.2f} mm"))

            self.preview = ComfacUtils.PreviewManager(FreeCAD.ActiveDocument, "Fittings_Preview")

            self.thick_input.valueChanged.connect(self.trigger_preview)
            self.length_input.valueChanged.connect(self.trigger_preview)
            self.trigger_preview()

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Initialization Error", f"Failed to open panel:\n{str(e)}")

    def trigger_preview(self):
        try:
            fit_thick = self.thick_input.value()
            sock_len = self.length_input.value()
            fit_id = self.pipe_od
            fit_od = self.pipe_od + (2 * fit_thick)
            ghost_shape = self.build_geometry(fit_od, fit_id, sock_len, fit_thick)
            if ghost_shape:
                self.preview.update(ghost_shape)
        except:
            pass

    def build_geometry(self, fit_od, fit_id, user_sock_len, fit_thick=None):
        try:
            if fit_thick is None:
                fit_thick = (fit_od - fit_id) / 2.0

            outer_shapes = []
            inner_shapes = []

            MATCH_TOLERANCE = 0.5
            END_TOLERANCE = 2.0

            def is_straight_edge(e):
                try: return hasattr(e.Curve, 'TypeId') and e.Curve.TypeId == 'Part::GeomLine'
                except: return False

            def safe_normalize(vec):
                if vec.Length < 0.0001: return FreeCAD.Vector(0,0,1)
                return vec.normalize()

            doc = FreeCAD.ActiveDocument
            all_sketches_in_doc = [obj for obj in doc.Objects if obj.isDerivedFrom("Sketcher::SketchObject")]
            connected_sketches = {self.sketch} if self.sketch else set()

            valid_edges = []
            network_points = []

            if self.sketch and hasattr(self.sketch, "Shape") and self.sketch.Shape:
                for e in self.sketch.Shape.Edges:
                    if e.Length > 0.001:
                        valid_edges.append(e)
                        try: network_points.extend([e.Vertexes[0].Point, e.Vertexes[-1].Point])
                        except: network_points.extend([e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)])

            added_new = True
            while added_new:
                added_new = False
                for sk in all_sketches_in_doc:
                    if sk in connected_sketches: continue
                    if not hasattr(sk, "Shape") or not sk.Shape: continue

                    sk_edges = [e for e in sk.Shape.Edges if e.Length > 0.001]
                    sk_points = []
                    for e in sk_edges:
                        try: sk_points.extend([e.Vertexes[0].Point, e.Vertexes[-1].Point])
                        except: sk_points.extend([e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)])

                    touches = False
                    for p_new in sk_points:
                        for existing_edge in valid_edges:
                            if existing_edge.distToShape(Part.Vertex(p_new))[0] < MATCH_TOLERANCE:
                                touches = True
                                break
                        if touches: break

                    if not touches:
                        for p_exist in network_points:
                            for new_edge in sk_edges:
                                if new_edge.distToShape(Part.Vertex(p_exist))[0] < MATCH_TOLERANCE:
                                    touches = True
                                    break
                            if touches: break

                    if touches:
                        connected_sketches.add(sk)
                        valid_edges.extend(sk_edges)
                        network_points.extend(sk_points)
                        added_new = True

            if not valid_edges:
                return None

            all_endpoints = network_points
            intersection_points = []
            end_points = []

            for pt in all_endpoints:
                if any((pt - ipt).Length < MATCH_TOLERANCE for ipt in intersection_points) or \
                   any((pt - ept).Length < MATCH_TOLERANCE for ept in end_points):
                    continue

                touch_count = 0
                for edge in valid_edges:
                    if edge.distToShape(Part.Vertex(pt))[0] < MATCH_TOLERANCE:
                        touch_count += 1

                if touch_count > 1:
                    intersection_points.append(pt)
                elif touch_count == 1:
                    end_points.append(pt)

            is_cap_only_mode = len(self.selected_points) > 0

            for pt in end_points:
                is_selected = False
                for sel_pt in self.selected_points:
                    if (pt - sel_pt).Length < MATCH_TOLERANCE:
                        is_selected = True
                        break

                if not is_selected:
                    continue

                for edge in valid_edges:
                    if not is_straight_edge(edge): continue
                    if edge.distToShape(Part.Vertex(pt))[0] > MATCH_TOLERANCE: continue

                    try: p_s = edge.Vertexes[0].Point; p_e = edge.Vertexes[-1].Point
                    except: p_s = edge.valueAt(edge.FirstParameter); p_e = edge.valueAt(edge.LastParameter)

                    d_s = (p_s - pt).Length
                    d_e = (p_e - pt).Length

                    dir_inward = None
                    if d_s < END_TOLERANCE: dir_inward = safe_normalize(p_e - p_s)
                    elif d_e < END_TOLERANCE: dir_inward = safe_normalize(p_s - p_e)

                    if dir_inward:
                        dir_outward = dir_inward * -1.0
                        L = max(0.1, min(user_sock_len, edge.Length / 2.01))

                        start_pt = pt + (dir_outward * fit_thick)
                        total_L = L + fit_thick

                        outer_shapes.append(Part.makeCylinder(fit_od/2.0, total_L, start_pt, dir_inward))
                        inner_shapes.append(Part.makeCylinder(fit_id/2.0, L + 10.0, pt, dir_inward))

            if not is_cap_only_mode:
                for pt in intersection_points:
                    vecs_away = []
                    for edge in valid_edges:
                        if not is_straight_edge(edge): continue
                        if edge.distToShape(Part.Vertex(pt))[0] > MATCH_TOLERANCE: continue

                        try: p_s = edge.Vertexes[0].Point; p_e = edge.Vertexes[-1].Point
                        except: p_s = edge.valueAt(edge.FirstParameter); p_e = edge.valueAt(edge.LastParameter)

                        d_s = (p_s - pt).Length
                        d_e = (p_e - pt).Length

                        if d_s < END_TOLERANCE: vecs_away.append(safe_normalize(p_e - p_s))
                        elif d_e < END_TOLERANCE: vecs_away.append(safe_normalize(p_s - p_e))
                        else:
                            vecs_away.append(safe_normalize(p_e - p_s))
                            vecs_away.append(safe_normalize(p_s - p_e))

                    is_wye = False
                    for i in range(len(vecs_away)):
                        for j in range(i+1, len(vecs_away)):
                            try:
                                ang = math.degrees(vecs_away[i].getAngle(vecs_away[j]))
                                if 40.0 < ang < 50.0 or 130.0 < ang < 140.0:
                                    is_wye = True; break
                            except: pass

                    current_sock_len = self.wye_depth if is_wye else user_sock_len

                    outer_shapes.append(Part.makeSphere(fit_od/2.0, pt))
                    inner_shapes.append(Part.makeSphere(fit_id/2.0, pt))

                    for edge in valid_edges:
                        if not is_straight_edge(edge): continue
                        if edge.distToShape(Part.Vertex(pt))[0] > MATCH_TOLERANCE: continue

                        try: p_s = edge.Vertexes[0].Point; p_e = edge.Vertexes[-1].Point
                        except: p_s = edge.valueAt(edge.FirstParameter); p_e = edge.valueAt(edge.LastParameter)

                        d_s = (p_s - pt).Length
                        d_e = (p_e - pt).Length

                        if d_s < END_TOLERANCE:
                            dir_fwd = safe_normalize(p_e - p_s)
                            L = max(0.1, min(current_sock_len, edge.Length / 2.01))
                            outer_shapes.append(Part.makeCylinder(fit_od/2.0, L, pt, dir_fwd))
                            inner_shapes.append(Part.makeCylinder(fit_id/2.0, L + fit_od, pt, dir_fwd))
                        elif d_e < END_TOLERANCE:
                            dir_bwd = safe_normalize(p_s - p_e)
                            L = max(0.1, min(current_sock_len, edge.Length / 2.01))
                            outer_shapes.append(Part.makeCylinder(fit_od/2.0, L, pt, dir_bwd))
                            inner_shapes.append(Part.makeCylinder(fit_id/2.0, L + fit_od, pt, dir_bwd))
                        else:
                            dir_fwd = safe_normalize(p_e - p_s)
                            dir_bwd = safe_normalize(p_s - p_e)

                            L_fwd = max(0.1, min(current_sock_len, d_e / 1.05))
                            L_bwd = max(0.1, min(current_sock_len, d_s / 1.05))

                            outer_shapes.append(Part.makeCylinder(fit_od/2.0, L_fwd, pt, dir_fwd))
                            inner_shapes.append(Part.makeCylinder(fit_id/2.0, L_fwd + fit_od, pt, dir_fwd))
                            outer_shapes.append(Part.makeCylinder(fit_od/2.0, L_bwd, pt, dir_bwd))
                            inner_shapes.append(Part.makeCylinder(fit_id/2.0, L_bwd + fit_od, pt, dir_bwd))

                for edge in valid_edges:
                    if not is_straight_edge(edge):
                        try: p_s = edge.Vertexes[0].Point; p_e = edge.Vertexes[-1].Point
                        except: p_s = edge.valueAt(edge.FirstParameter); p_e = edge.valueAt(edge.LastParameter)

                        t_s = safe_normalize(edge.tangentAt(edge.FirstParameter))
                        t_e = safe_normalize(edge.tangentAt(edge.LastParameter))

                        try:
                            outer_shapes.append(Part.Wire([edge]).makePipeShell([Part.Wire([Part.Circle(p_s, t_s, fit_od/2.0).toShape()])], True, True, 2))
                            inner_shapes.append(Part.Wire([edge]).makePipeShell([Part.Wire([Part.Circle(p_s, t_s, fit_id/2.0).toShape()])], True, True, 2))
                        except Exception as sweep_e:
                            FreeCAD.Console.PrintWarning(f"Curved elbow sweep failed: {sweep_e}\n")

                        outer_shapes.append(Part.makeCylinder(fit_od/2.0, user_sock_len, p_s, t_s * -1))
                        inner_shapes.append(Part.makeCylinder(fit_id/2.0, user_sock_len + 10.0, p_s, t_s * -1))
                        outer_shapes.append(Part.makeCylinder(fit_od/2.0, user_sock_len, p_e, t_e))
                        inner_shapes.append(Part.makeCylinder(fit_id/2.0, user_sock_len + 10.0, p_e, t_e))

            if not outer_shapes:
                return None

            def robust_fuse(shape_list):
                if not shape_list: return None
                master = shape_list[0]
                for i in range(1, len(shape_list)):
                    try:
                        master = master.fuse(shape_list[i])
                    except Exception as fuse_err:
                        FreeCAD.Console.PrintWarning(f"Skipped a broken fitting piece: {fuse_err}\n")
                return master.removeSplitter()

            fused_outer = robust_fuse(outer_shapes)
            fused_inner = robust_fuse(inner_shapes)

            if not fused_outer or not fused_inner:
                return None

            return fused_outer.cut(fused_inner).removeSplitter()

        except Exception as e:
            FreeCAD.Console.PrintError(f"Preview build failed: {e}\n")
            return None

    def accept(self):
        try:
            fit_thick = self.thick_input.value()
            sock_len = self.length_input.value()
            fit_id = self.pipe_od
            fit_od = self.pipe_od + (2 * fit_thick)
            self.preview.clear()
            FreeCADGui.Control.closeDialog()
            self.generate_fittings(fit_od, fit_id, sock_len, fit_thick)
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Input Error", f"Failed to read inputs:\n{str(e)}")

    def reject(self):
        self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def generate_fittings(self, fit_od, fit_id, user_sock_len, fit_thick=None):
        try:
            if fit_thick is None:
                fit_thick = (fit_od - fit_id) / 2.0
                
            doc = FreeCAD.ActiveDocument
            outer_shapes = []
            inner_shapes = []
            
            MATCH_TOLERANCE = 0.5 
            # FIX: End tolerance prevents false T-Junctions from cutting holes in elbows!
            END_TOLERANCE = 2.0 

            def is_straight_edge(e):
                try: return hasattr(e.Curve, 'TypeId') and e.Curve.TypeId == 'Part::GeomLine'
                except: return False
                
            # Error Handling: Safe normalization prevents zero-division crashes
            def safe_normalize(vec):
                if vec.Length < 0.0001: return FreeCAD.Vector(0,0,1)
                return vec.normalize()

            # --- SMART NETWORK TRACER ---
            all_sketches_in_doc = [obj for obj in doc.Objects if obj.isDerivedFrom("Sketcher::SketchObject")]
            connected_sketches = {self.sketch} if self.sketch else set()
            
            valid_edges = []
            network_points = []
            
            if self.sketch and hasattr(self.sketch, "Shape") and self.sketch.Shape:
                for e in self.sketch.Shape.Edges:
                    if e.Length > 0.001:
                        valid_edges.append(e)
                        try: network_points.extend([e.Vertexes[0].Point, e.Vertexes[-1].Point])
                        except: network_points.extend([e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)])

            added_new = True
            while added_new:
                added_new = False
                for sk in all_sketches_in_doc:
                    if sk in connected_sketches: continue
                    if not hasattr(sk, "Shape") or not sk.Shape: continue
                    
                    sk_edges = [e for e in sk.Shape.Edges if e.Length > 0.001]
                    sk_points = []
                    for e in sk_edges:
                        try: sk_points.extend([e.Vertexes[0].Point, e.Vertexes[-1].Point])
                        except: sk_points.extend([e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)])
                            
                    touches = False
                    for p_new in sk_points:
                        for existing_edge in valid_edges:
                            if existing_edge.distToShape(Part.Vertex(p_new))[0] < MATCH_TOLERANCE:
                                touches = True
                                break
                        if touches: break
                        
                    if not touches:
                        for p_exist in network_points:
                            for new_edge in sk_edges:
                                if new_edge.distToShape(Part.Vertex(p_exist))[0] < MATCH_TOLERANCE:
                                    touches = True
                                    break
                            if touches: break
                        
                    if touches:
                        connected_sketches.add(sk)
                        valid_edges.extend(sk_edges)
                        network_points.extend(sk_points)
                        added_new = True

            if not valid_edges:
                QtWidgets.QMessageBox.warning(None, "Geometry Error", "No valid sketch lines found.")
                return

            # --- SEPARATE JOINTS FROM DEAD ENDS ---
            all_endpoints = network_points
            intersection_points = []
            end_points = []
            
            for pt in all_endpoints:
                if any((pt - ipt).Length < MATCH_TOLERANCE for ipt in intersection_points) or \
                   any((pt - ept).Length < MATCH_TOLERANCE for ept in end_points): 
                    continue
                    
                touch_count = 0
                for edge in valid_edges:
                    if edge.distToShape(Part.Vertex(pt))[0] < MATCH_TOLERANCE:
                        touch_count += 1
                        
                if touch_count > 1:
                    intersection_points.append(pt)
                elif touch_count == 1:
                    end_points.append(pt)

            is_cap_only_mode = len(self.selected_points) > 0

            # --- GENERATE END CAPS (MANUAL SELECTION ONLY) ---
            for pt in end_points:
                is_selected = False
                for sel_pt in self.selected_points:
                    if (pt - sel_pt).Length < MATCH_TOLERANCE:
                        is_selected = True
                        break
                        
                if not is_selected:
                    continue 

                for edge in valid_edges:
                    if not is_straight_edge(edge): continue
                    if edge.distToShape(Part.Vertex(pt))[0] > MATCH_TOLERANCE: continue

                    try: p_s = edge.Vertexes[0].Point; p_e = edge.Vertexes[-1].Point
                    except: p_s = edge.valueAt(edge.FirstParameter); p_e = edge.valueAt(edge.LastParameter)
                    
                    d_s = (p_s - pt).Length
                    d_e = (p_e - pt).Length
                    
                    dir_inward = None
                    # Use safe_normalize
                    if d_s < END_TOLERANCE: dir_inward = safe_normalize(p_e - p_s)
                    elif d_e < END_TOLERANCE: dir_inward = safe_normalize(p_s - p_e)
                    
                    if dir_inward:
                        dir_outward = dir_inward * -1.0
                        L = max(0.1, min(user_sock_len, edge.Length / 2.01))
                        
                        start_pt = pt + (dir_outward * fit_thick)
                        total_L = L + fit_thick
                        
                        outer_shapes.append(Part.makeCylinder(fit_od/2.0, total_L, start_pt, dir_inward))
                        inner_shapes.append(Part.makeCylinder(fit_id/2.0, L + 10.0, pt, dir_inward))

            # --- GENERATE FITTING JOINTS (Tees, Elbows, Wyes) ---
            if not is_cap_only_mode:
                for pt in intersection_points:
                    vecs_away = []
                    for edge in valid_edges:
                        if not is_straight_edge(edge): continue
                        if edge.distToShape(Part.Vertex(pt))[0] > MATCH_TOLERANCE: continue

                        try: p_s = edge.Vertexes[0].Point; p_e = edge.Vertexes[-1].Point
                        except: p_s = edge.valueAt(edge.FirstParameter); p_e = edge.valueAt(edge.LastParameter)
                        
                        d_s = (p_s - pt).Length
                        d_e = (p_e - pt).Length
                        
                        # Use END_TOLERANCE here so it doesn't accidentally think it's a T-Junction
                        if d_s < END_TOLERANCE: vecs_away.append(safe_normalize(p_e - p_s))
                        elif d_e < END_TOLERANCE: vecs_away.append(safe_normalize(p_s - p_e))
                        else:
                            vecs_away.append(safe_normalize(p_e - p_s))
                            vecs_away.append(safe_normalize(p_s - p_e))
                    
                    is_wye = False
                    for i in range(len(vecs_away)):
                        for j in range(i+1, len(vecs_away)):
                            try:
                                ang = math.degrees(vecs_away[i].getAngle(vecs_away[j]))
                                if 40.0 < ang < 50.0 or 130.0 < ang < 140.0:
                                    is_wye = True; break
                            except: pass # Ignore angle math errors on perfectly parallel vectors
                    
                    current_sock_len = self.wye_depth if is_wye else user_sock_len

                    outer_shapes.append(Part.makeSphere(fit_od/2.0, pt))
                    inner_shapes.append(Part.makeSphere(fit_id/2.0, pt))
                    
                    for edge in valid_edges:
                        if not is_straight_edge(edge): continue
                        if edge.distToShape(Part.Vertex(pt))[0] > MATCH_TOLERANCE: continue

                        try: p_s = edge.Vertexes[0].Point; p_e = edge.Vertexes[-1].Point
                        except: p_s = edge.valueAt(edge.FirstParameter); p_e = edge.valueAt(edge.LastParameter)
                        
                        d_s = (p_s - pt).Length
                        d_e = (p_e - pt).Length
                        
                        # Also use END_TOLERANCE here when building sleeves!
                        if d_s < END_TOLERANCE:
                            dir_fwd = safe_normalize(p_e - p_s)
                            L = max(0.1, min(current_sock_len, edge.Length / 2.01))
                            outer_shapes.append(Part.makeCylinder(fit_od/2.0, L, pt, dir_fwd))
                            inner_shapes.append(Part.makeCylinder(fit_id/2.0, L + fit_od, pt, dir_fwd))
                        elif d_e < END_TOLERANCE:
                            dir_bwd = safe_normalize(p_s - p_e)
                            L = max(0.1, min(current_sock_len, edge.Length / 2.01))
                            outer_shapes.append(Part.makeCylinder(fit_od/2.0, L, pt, dir_bwd))
                            inner_shapes.append(Part.makeCylinder(fit_id/2.0, L + fit_od, pt, dir_bwd))
                        else:
                            dir_fwd = safe_normalize(p_e - p_s)
                            dir_bwd = safe_normalize(p_s - p_e)
                            
                            L_fwd = max(0.1, min(current_sock_len, d_e / 1.05))
                            L_bwd = max(0.1, min(current_sock_len, d_s / 1.05))
                            
                            outer_shapes.append(Part.makeCylinder(fit_od/2.0, L_fwd, pt, dir_fwd))
                            inner_shapes.append(Part.makeCylinder(fit_id/2.0, L_fwd + fit_od, pt, dir_fwd))
                            outer_shapes.append(Part.makeCylinder(fit_od/2.0, L_bwd, pt, dir_bwd))
                            inner_shapes.append(Part.makeCylinder(fit_id/2.0, L_bwd + fit_od, pt, dir_bwd))

                for edge in valid_edges:
                    if not is_straight_edge(edge):
                        try: p_s = edge.Vertexes[0].Point; p_e = edge.Vertexes[-1].Point
                        except: p_s = edge.valueAt(edge.FirstParameter); p_e = edge.valueAt(edge.LastParameter)
                        
                        t_s = safe_normalize(edge.tangentAt(edge.FirstParameter))
                        t_e = safe_normalize(edge.tangentAt(edge.LastParameter))
                        
                        try:
                            outer_shapes.append(Part.Wire([edge]).makePipeShell([Part.Wire([Part.Circle(p_s, t_s, fit_od/2.0).toShape()])], True, True, 2))
                            inner_shapes.append(Part.Wire([edge]).makePipeShell([Part.Wire([Part.Circle(p_s, t_s, fit_id/2.0).toShape()])], True, True, 2))
                        except Exception as sweep_e:
                            FreeCAD.Console.PrintWarning(f"Curved elbow sweep failed: {sweep_e}\n")
                        
                        outer_shapes.append(Part.makeCylinder(fit_od/2.0, user_sock_len, p_s, t_s * -1))
                        inner_shapes.append(Part.makeCylinder(fit_id/2.0, user_sock_len + 10.0, p_s, t_s * -1))
                        outer_shapes.append(Part.makeCylinder(fit_od/2.0, user_sock_len, p_e, t_e))
                        inner_shapes.append(Part.makeCylinder(fit_id/2.0, user_sock_len + 10.0, p_e, t_e))

            # =========================================================
            # TOPOLOGICAL ERROR HANDLER (NO FITTINGS DETECTED)
            # =========================================================
            if not outer_shapes: 
                if is_cap_only_mode:
                    QtWidgets.QMessageBox.information(None, "Selection Notice", "No end caps generated. Make sure you selected the exact circular edge at the open end of the pipe.")
                else:
                    # ---> THIS IS THE ERROR HANDLER YOU REQUESTED <---
                    QtWidgets.QMessageBox.information(None, "No Fittings Identified", "No valid junctions, corners, or arcs were found in the sketch. Fittings cannot be generated for a single straight pipe.")
                return

            try:
                def robust_fuse(shape_list):
                    if not shape_list: return None
                    master = shape_list[0]
                    for i in range(1, len(shape_list)): 
                        try:
                            master = master.fuse(shape_list[i])
                        except Exception as fuse_err:
                            FreeCAD.Console.PrintWarning(f"Skipped a broken fitting piece: {fuse_err}\n")
                    return master.removeSplitter()

                fused_outer = robust_fuse(outer_shapes)
                fused_inner = robust_fuse(inner_shapes)
                
                if not fused_outer or not fused_inner:
                    raise Exception("Failed to fuse geometry into a solid block.")
                
                final_shape = fused_outer.cut(fused_inner).removeSplitter()
                
                doc.openTransaction("Add Pipe Fittings")
                
                obj_name = "Pipe_EndCaps" if is_cap_only_mode else "Pipe_Fittings"
                obj = doc.addObject("Part::Feature", obj_name)
                
                obj.Shape = final_shape
                obj.addProperty("App::PropertyString", "SketchName").SketchName = getattr(self.pipe_obj, "SketchName", "")
                obj.addProperty("App::PropertyFloat", "PipeOuter").PipeOuter = self.pipe_od
                obj.addProperty("App::PropertyFloat", "PipeInner").PipeInner = self.pipe_id
                
                for parent in self.pipe_obj.InList:
                    if parent.isDerivedFrom("App::Part") or parent.isDerivedFrom("App::DocumentObjectGroup"):
                        parent.addObject(obj); break
                        
                if hasattr(obj.ViewObject, "ShapeColor") and hasattr(self.pipe_obj.ViewObject, "ShapeColor"): 
                    try: obj.ViewObject.ShapeColor = self.pipe_obj.ViewObject.ShapeColor
                    except: obj.ViewObject.ShapeColor = (0.3, 0.3, 0.3)
                
                doc.recompute(); doc.commitTransaction()
                
            except Exception as e:
                if doc.hasPendingTransaction():
                    doc.abortTransaction()
                QtWidgets.QMessageBox.critical(None, "Boolean Math Error", f"FreeCAD failed to cut the fitting shapes properly:\n\n{str(e)}")

        except Exception as global_e:
            QtWidgets.QMessageBox.critical(None, "Fatal Script Error", f"The fittings script crashed:\n\n{str(global_e)}")


class CreateNetworkPipeFittings:
    def GetResources(self):
        return {'Pixmap': ComfacUtils.get_icon_path('Pipe_Fittings.svg'), 'MenuText': "Add Pipe Fittings"}
        
    def Activated(self):
        try:
            sel_ex = FreeCADGui.Selection.getSelectionEx()
            pipe_obj = None
            selected_points = []
            
            for sel_obj in sel_ex:
                obj = sel_obj.Object
                if hasattr(obj, "PipeOuter"):
                    pipe_obj = obj
                    for sub in sel_obj.SubObjects:
                        try:
                            if "Circle" in sub.Curve.TypeId:
                                selected_points.append(sub.Curve.Location)
                        except: pass
                elif obj.isDerivedFrom("Sketcher::SketchObject"):
                    for sub in sel_obj.SubObjects:
                        try:
                            if str(sub.ShapeType) == "Vertex":
                                selected_points.append(sub.Point)
                        except: pass
                        
            if not pipe_obj:
                sel = FreeCADGui.Selection.getSelection()
                if sel and hasattr(sel[0], "PipeOuter"):
                    pipe_obj = sel[0]
                    
            if not pipe_obj: 
                QtWidgets.QMessageBox.warning(None, "Selection Error", "Please select a generated Pipe Network solid in the Tree View!")
                return
                
            panel = PipeFittingTaskPanel(pipe_obj, selected_points)
            FreeCADGui.Control.showDialog(panel)
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Launch Error", f"Could not launch the tool:\n{str(e)}")

FreeCADGui.addCommand('CreateNetworkPipeFittings', CreateNetworkPipeFittings())