import FreeCAD as App
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui
import Ducts.DuctGeometryUtils as DuctGeometryUtils

try:
    import ComfacUtils
except ImportError:
    pass

class DuctInsulationTaskPanel:
    def __init__(self, target_obj):
        self.target_obj = target_obj
        self.ducts = []

        # Find all valid ducts in the selection
        if hasattr(target_obj, "SourceNetworks"):
            for src in target_obj.SourceNetworks:
                if hasattr(src, "DuctWidth") or hasattr(src, "SolidWidth"):
                    self.ducts.append(src)
        elif hasattr(target_obj, "DuctWidth") or hasattr(target_obj, "SolidWidth"):
            self.ducts.append(target_obj)

        self.form = QtWidgets.QWidget()
        self.layout = QtWidgets.QFormLayout(self.form)

        # Protect against empty selections
        first_props = self.get_duct_props(self.ducts[0]) if self.ducts else None
        self.base_w = first_props["w"] if first_props else 100.0
        self.base_h = first_props["h"] if first_props else 100.0

        self.detected_w = QtWidgets.QLabel(f"~ {self.base_w:.2f} mm")
        self.detected_h = QtWidgets.QLabel(f"~ {self.base_h:.2f} mm")

        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(5.0, 500.0)
        self.thick_input.setValue(25.0)
        self.thick_input.setDecimals(2)
        self.thick_input.setSuffix(" mm")

        self.layout.addRow("Detected Base Width:", self.detected_w)
        self.layout.addRow("Detected Base Height:", self.detected_h)
        self.layout.addRow("Insulation Thickness:", self.thick_input)

        self.preview = ComfacUtils.PreviewManager(App.ActiveDocument, "DuctInsulation_Preview") if 'ComfacUtils' in globals() else None
        
        self.thick_input.valueChanged.connect(self.trigger_preview)
        self.trigger_preview()

    def get_duct_props(self, obj):
        """Helper to unify property names between Hollow Ducts and Solid CFD Domains."""
        if hasattr(obj, "DuctWidth"):
            return {
                "w": float(obj.DuctWidth),
                "h": float(getattr(obj, 'DuctHeight', getattr(obj, 'DuctDepth', obj.DuctWidth))),
                "r": float(getattr(obj, 'DuctRadius', 0.0)),
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
                "profile": getattr(obj, "SolidProfileType", "Rectangular"),
                "corner": getattr(obj, "SolidCornerType", "Rounded"),
                "align": getattr(obj, "SolidAlignment", "Center"),
                "sketch_name": getattr(obj, "LinkedSolidSketchName", "")
            }
        return None

    def trigger_preview(self):
        if not self.preview: return
        try:
            ins_thick = self.thick_input.value()
            ghost_shape = self.build_insulation_geometry(ins_thick, is_preview=True)
            if ghost_shape:
                self.preview.update(ghost_shape, color=(0.75, 0.75, 0.75)) 
        except: pass

    def accept(self):
        ins_thick = self.thick_input.value()
        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()
        
        progress = QtWidgets.QProgressDialog("Generating Duct Insulation...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Computing Geometry")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            first_props = self.get_duct_props(self.ducts[0]) if self.ducts else None
            out_w = first_props["w"] + (2 * ins_thick) if first_props else 100.0
            out_h = first_props["h"] + (2 * ins_thick) if first_props else 100.0

            final_shape = self.build_insulation_geometry(ins_thick, is_preview=False)
            if final_shape:
                self.commit_insulation(final_shape, out_w, out_h)
        finally:
            progress.close()

    def commit_insulation(self, final_shape, out_w, out_h):
        """TREE COMMIT: Attaches the built insulation and saves exact dimensions."""
        doc = App.ActiveDocument
        doc.openTransaction("Generate Duct Insulation")
        try:
            parent_container = None
            is_body = False
            for parent in self.target_obj.InList:
                if parent.isDerivedFrom("PartDesign::Body"):
                    parent_container = parent
                    is_body = True
                    break
                elif parent.isDerivedFrom("App::Part") or parent.isDerivedFrom("App::DocumentObjectGroup"):
                    parent_container = parent

            if is_body:
                raw_ins = doc.addObject("Part::Feature", "Raw_Duct_Insulation")
                raw_ins.Shape = final_shape
                raw_ins.ViewObject.Visibility = False 
                obj = parent_container.newObject("PartDesign::FeatureBase", "Duct_Insulation")
                obj.BaseFeature = raw_ins
            else:
                obj = doc.addObject("Part::Feature", "Duct_Insulation")
                obj.Shape = final_shape
                if parent_container: 
                    parent_container.addObject(obj)
                else:
                    if self.target_obj.isDerivedFrom("App::DocumentObjectGroup"):
                        self.target_obj.addObject(obj)

            try:
                obj.addProperty("App::PropertyLength", "InsulatedWidth", "Insulation Data", "Exact Width").InsulatedWidth = out_w
                obj.addProperty("App::PropertyLength", "InsulatedHeight", "Insulation Data", "Exact Height").InsulatedHeight = out_h
            except: pass

            obj.ViewObject.ShapeColor = (0.75, 0.75, 0.75)
            obj.ViewObject.Transparency = 60
            
            if hasattr(obj, "Refine"): obj.Refine = True

            doc.recompute()
            doc.commitTransaction()
            
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Generation Error", f"Failed to generate insulation.\n\nError: {e}")

    def reject(self):
        if self.preview: self.preview.clear()
        FreeCADGui.Control.closeDialog()

    def build_insulation_geometry(self, ins_thick, is_preview=False):
        doc = App.ActiveDocument
        all_outer_shells = []
        all_inner_shells = []
        bump_outer_shapes = []
        
        try:
            for duct_obj in self.ducts:
                props = self.get_duct_props(duct_obj)
                if not props: continue

                sketch = doc.getObject(props["sketch_name"])
                if not sketch: continue
                
                profile_type = props["profile"]
                corner_type = props["corner"]
                alignment = props["align"]
                
                base_w = props["w"]
                base_h = props["h"]
                base_r = props["r"]

                in_w = base_w
                in_h = base_h
                in_r = base_r
                
                out_w = in_w + (2 * ins_thick)
                out_h = in_h + (2 * ins_thick)
                out_r = in_r + ins_thick

                sketch_normal = sketch.Placement.Rotation.multVec(App.Vector(0, 0, 1))
                calc_inner_rad = base_h * 0.5
                
                offset_val = 0.0
                if alignment == "Inner": offset_val = -(base_w / 2.0)
                elif alignment == "Outer": offset_val = (base_w / 2.0)

                edges = [e for e in sketch.Shape.Edges if e.Length > 0.001]
                junctions = DuctGeometryUtils.get_junction_points(edges)
                simple_paths = DuctGeometryUtils.build_simple_paths(edges, junctions)

                valid_edges = []

                for path_edges in simple_paths:
                    if corner_type == "Rounded":
                        process_edges = DuctGeometryUtils.fillet_wire_path(path_edges, sketch_normal, base_w, offset_val, calc_inner_rad)
                    else: 
                        process_edges = path_edges

                    if not process_edges: continue
                    
                    for edge in process_edges:
                        if edge.Length > 0.001:
                            e_tangent = edge.tangentAt(edge.FirstParameter).normalize()
                            cur_x_dir = sketch_normal.cross(e_tangent).normalize()
                            valid_edges.append((edge, cur_x_dir))

                    over_len = out_w + 15.0
                    try:
                        if len(process_edges) == 1:
                            e = process_edges[0]
                            p1 = e.valueAt(e.FirstParameter)
                            p2 = e.valueAt(e.LastParameter)
                            v_dir = (p2 - p1).normalize()
                            new_p1 = p1 - v_dir * over_len if any(p1.isEqual(jp, 0.001) for jp in junctions) else p1
                            new_p2 = p2 + v_dir * over_len if any(p2.isEqual(jp, 0.001) for jp in junctions) else p2
                            process_edges[0] = Part.makeLine(new_p1, new_p2)
                        else:
                            e_first = process_edges[0]
                            p1 = e_first.valueAt(e_first.FirstParameter)
                            p2 = e_first.valueAt(e_first.LastParameter)
                            v_next = [v.Point for v in process_edges[1].Vertexes]
                            
                            is_p1_shared = p1.isEqual(v_next[0], 0.001) or (len(v_next) > 1 and p1.isEqual(v_next[1], 0.001))
                            shared_pt = p1 if is_p1_shared else p2
                            free_pt = p2 if is_p1_shared else p1

                            if any(free_pt.isEqual(jp, 0.001) for jp in junctions):
                                v_out = (free_pt - shared_pt).normalize()
                                if is_p1_shared: process_edges[0] = Part.makeLine(p1, p2 + v_out * over_len)
                                else: process_edges[0] = Part.makeLine(p1 + v_out * over_len, p2)

                            e_last = process_edges[-1]
                            p1 = e_last.valueAt(e_last.FirstParameter)
                            p2 = e_last.valueAt(e_last.LastParameter)
                            v_prev = [v.Point for v in process_edges[-2].Vertexes]
                            
                            is_p1_shared = p1.isEqual(v_prev[0], 0.001) or (len(v_prev) > 1 and p1.isEqual(v_prev[1], 0.001))
                            shared_pt = p1 if is_p1_shared else p2
                            free_pt = p2 if is_p1_shared else p1

                            if any(free_pt.isEqual(jp, 0.001) for jp in junctions):
                                v_out = (free_pt - shared_pt).normalize()
                                if is_p1_shared: process_edges[-1] = Part.makeLine(p1, p2 + v_out * over_len)
                                else: process_edges[-1] = Part.makeLine(p1 + v_out * over_len, p2)
                    except: pass
                    
                    process_wire = Part.Wire(process_edges)
                    has_arcs = any(hasattr(e.Curve, 'TypeId') and 'GeomCircle' in e.Curve.TypeId for e in process_edges)
                    t_mode = 2 if has_arcs else 1
                    
                    first_edge = process_wire.OrderedEdges[0]
                    start_pt = first_edge.valueAt(first_edge.FirstParameter)
                    tangent = first_edge.tangentAt(first_edge.FirstParameter).normalize()
                    
                    X_dir = sketch_normal.cross(tangent).normalize()
                    shifted_start_pt = start_pt + (X_dir * offset_val)

                    prof_out = DuctGeometryUtils.create_profile(out_w, out_h, out_r, shifted_start_pt, tangent, sketch_normal, profile_type)
                    prof_in = DuctGeometryUtils.create_profile(in_w, in_h, in_r, shifted_start_pt, tangent, sketch_normal, profile_type)
                    
                    try:
                        sweep_out = process_wire.makePipeShell([prof_out], True, True, t_mode)
                        sweep_in = process_wire.makePipeShell([prof_in], True, True, t_mode)
                        if not sweep_out.isNull(): all_outer_shells.append(sweep_out)
                        if not sweep_in.isNull(): all_inner_shells.append(sweep_in)
                    except: pass

                # =======================================================
                # GENERATE THE OUTER AESTHETIC BUMP
                # =======================================================
                if valid_edges:
                    bump_allow = 10.0 
                    bump_out_w = out_w + bump_allow
                    bump_out_h = out_h + bump_allow
                    bump_out_r = out_r + (bump_allow / 2.0)
                    
                    sock_len = 55.0

                    def is_straight_edge(e):
                        try: return hasattr(e.Curve, 'TypeId') and 'GeomLine' in e.Curve.TypeId
                        except: return False

                    all_endpoints = []
                    for e, xd in valid_edges:
                        all_endpoints.append(e.valueAt(e.FirstParameter))
                        all_endpoints.append(e.valueAt(e.LastParameter))

                    intersection_points = []
                    for pt in all_endpoints:
                        deg = 0
                        for e, xd in valid_edges:
                            if e.distToShape(Part.Vertex(pt))[0] < 0.001:
                                is_start = e.valueAt(e.FirstParameter).isEqual(pt, 0.001)
                                is_end = e.valueAt(e.LastParameter).isEqual(pt, 0.001)
                                deg += 1 if (is_start or is_end) else 2
                        if deg > 1 and not any(pt.isEqual(ipt, 0.001) for ipt in intersection_points):
                            intersection_points.append(pt)

                    for pt in intersection_points:
                        has_arc = False
                        for e, xd in valid_edges:
                            if e.distToShape(Part.Vertex(pt))[0] < 0.001 and not is_straight_edge(e):
                                has_arc = True
                                break

                        if not has_arc:
                            raw_dirs = []
                            unique_offsets = []
                            for e, true_x_dir in valid_edges:
                                if is_straight_edge(e) and e.distToShape(Part.Vertex(pt))[0] < 0.01:
                                    p_s = e.valueAt(e.FirstParameter)
                                    p_e = e.valueAt(e.LastParameter)
                                    dist_s = (p_s - pt).Length
                                    dist_e = (p_e - pt).Length

                                    v_off = true_x_dir * offset_val
                                    if not any((uo - v_off).Length < 1.0 for uo in unique_offsets):
                                        unique_offsets.append(v_off)

                                    if dist_s < 1.0:
                                        swp_dir = (p_e - p_s).normalize()
                                        raw_dirs.append((swp_dir, true_x_dir))
                                    elif dist_e < 1.0:
                                        swp_dir = (p_s - p_e).normalize()
                                        raw_dirs.append((swp_dir, true_x_dir))
                                    else:
                                        vec1 = (p_e - pt).normalize()
                                        vec2 = (p_s - pt).normalize()
                                        raw_dirs.append((vec1, true_x_dir))
                                        raw_dirs.append((vec2, true_x_dir))

                            v_combined = App.Vector(0,0,0)
                            for vo in unique_offsets: v_combined += vo
                            shifted_pt = pt + v_combined

                            unique_dirs = []
                            for swp_dir, x_dir in raw_dirs:
                                if not any((ud[0] - swp_dir).Length < 0.01 for ud in unique_dirs):
                                    unique_dirs.append((swp_dir, x_dir))

                            for swp_dir, true_x_dir in unique_dirs:
                                p0_out = shifted_pt - swp_dir * (max(bump_out_w, bump_out_h) / 2.0)
                                p1_out = shifted_pt + swp_dir * sock_len
                                edge_out = Part.makeLine(p0_out, p1_out)
                                
                                prof_out = DuctGeometryUtils.create_profile(bump_out_w, bump_out_h, bump_out_r, p0_out, swp_dir, sketch_normal, profile_type)
                                try: bump_outer_shapes.append(Part.Wire([edge_out]).makePipeShell([prof_out], True, False, 2))
                                except: pass

                    for e, cur_x_dir in valid_edges:
                        if not is_straight_edge(e):
                            p_s = e.valueAt(e.FirstParameter)
                            p_e = e.valueAt(e.LastParameter)
                            tangent_s = e.tangentAt(e.FirstParameter).normalize()
                            tangent_e = e.tangentAt(e.LastParameter).normalize()

                            X_dir_s = sketch_normal.cross(tangent_s).normalize()
                            shifted_p_s = p_s + (X_dir_s * offset_val)
                            
                            prof_out = DuctGeometryUtils.create_profile(bump_out_w, bump_out_h, bump_out_r, shifted_p_s, tangent_s, sketch_normal, profile_type)
                            try: bump_outer_shapes.append(Part.Wire([e]).makePipeShell([prof_out], True, True, 2))
                            except: pass

                            shifted_p_s_in = (p_s - tangent_s * 10.0) + (X_dir_s * offset_val)
                            shifted_p_s_end = (p_s + tangent_s * sock_len) + (X_dir_s * offset_val)
                            edge_in_s = Part.makeLine(shifted_p_s_in, shifted_p_s_end)
                            
                            prof_in_s_out = DuctGeometryUtils.create_profile(bump_out_w, bump_out_h, bump_out_r, shifted_p_s_in, tangent_s, sketch_normal, profile_type)
                            try: bump_outer_shapes.append(Part.Wire([edge_in_s]).makePipeShell([prof_in_s_out], True, False, 2))
                            except: pass

                            X_dir_e = sketch_normal.cross(tangent_e).normalize()
                            shifted_p_e_start = (p_e - tangent_e * sock_len) + (X_dir_e * offset_val)
                            shifted_p_e_end = (p_e + tangent_e * 10.0) + (X_dir_e * offset_val)
                            edge_in_e = Part.makeLine(shifted_p_e_start, shifted_p_e_end)
                            
                            prof_in_e_out = DuctGeometryUtils.create_profile(bump_out_w, bump_out_h, bump_out_r, shifted_p_e_start, tangent_e, sketch_normal, profile_type)
                            try: bump_outer_shapes.append(Part.Wire([edge_in_e]).makePipeShell([prof_in_e_out], True, False, 2))
                            except: pass

            if not all_outer_shells: return None

            # Fuse the straight outer segments and the bumps
            master_outer = DuctGeometryUtils.fuse_shapes(all_outer_shells)
            if bump_outer_shapes:
                master_bump_outer = DuctGeometryUtils.fuse_shapes(bump_outer_shapes)
                master_outer = master_outer.fuse(master_bump_outer)

            # =======================================================
            # PERFECT INNER VOID: Automatically use actual duct and 
            # fitting shapes from the folder as the cutting tool!
            # =======================================================
            master_inner_core = DuctGeometryUtils.fuse_shapes(all_inner_shells)
            
            fitting_shapes = []
            parent_group = None
            if self.target_obj.isDerivedFrom("App::DocumentObjectGroup"):
                parent_group = self.target_obj
            elif hasattr(self.target_obj, "InList"):
                for p in self.target_obj.InList:
                    if p.isDerivedFrom("App::DocumentObjectGroup"):
                        parent_group = p
                        break
            
            if parent_group and hasattr(parent_group, "Group"):
                for child in parent_group.Group:
                    if "Fittings" in child.Name or (hasattr(child, "Label") and "Fittings" in child.Label):
                        if hasattr(child, "Shape") and not child.Shape.isNull():
                            fitting_shapes.append(child.Shape)
            
            master_inner = master_inner_core
            if fitting_shapes:
                fittings_fused = DuctGeometryUtils.fuse_shapes(fitting_shapes)
                master_inner = master_inner.fuse(fittings_fused)
            # =======================================================

            return master_outer.cut(master_inner).removeSplitter()
            
        except Exception as e:
            if not is_preview: QtWidgets.QMessageBox.critical(None, "Dimension Error", str(e))
            return None

class CreateNetworkDuctInsulation:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('Duct_Insulation.svg') if 'ComfacUtils' in globals() else "", 
            'MenuText': "Add Duct Insulation",
            'ToolTip': "Select a Smart Duct, Solid Duct, or Merged Network to wrap it in insulation"
        }

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        if not sel:
            QtWidgets.QMessageBox.warning(None, "Selection Error", "Please select a generated Smart Duct Folder, CFD Domain Folder, or Merged Network!")
            return
            
        obj = sel[0]
        is_valid = hasattr(obj, "DuctWidth") or hasattr(obj, "SolidWidth") or hasattr(obj, "SourceNetworks")
        
        if not is_valid:
            QtWidgets.QMessageBox.warning(None, "Selection Error", "The selected object is not a valid parametric duct, CFD domain, or merged network.")
            return

        progress = QtWidgets.QProgressDialog("Launching Insulation Tool...\nPlease wait.", None, 0, 0)
        progress.setWindowTitle("Loading")
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            panel = DuctInsulationTaskPanel(obj)
            FreeCADGui.Control.showDialog(panel)
        finally:
            progress.close()

try:
    FreeCADGui.addCommand('CreateNetworkDuctInsulation', CreateNetworkDuctInsulation())
except Exception:
    pass