import FreeCAD
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui
import ComfacUtils

# Try to import DuctGeometryUtils for advanced duct handling
try:
    import Ducts.DuctGeometryUtils as DuctGeometryUtils
    HAS_DUCT_UTILS = True
except ImportError:
    HAS_DUCT_UTILS = False

class MergeHollowNetworks:
    def GetResources(self):
        return {
            'Pixmap': ComfacUtils.get_icon_path('Hollow_Merge.svg'), 
            'MenuText': "Merge Hollow Networks",
            'ToolTip': "Merges pipes, ducts using subtractive cubes. Creates solid outer shell and subtracts inner void."
        }

    def create_rect_profile(self, w, h, radius, start_pt, tangent, sketch_normal):
        """Create a rectangular profile with optional corner radius."""
        if radius <= 0.001:
            p1 = FreeCAD.Vector(-w/2, -h/2, 0)
            p2 = FreeCAD.Vector(w/2, -h/2, 0)
            p3 = FreeCAD.Vector(w/2, h/2, 0)
            p4 = FreeCAD.Vector(-w/2, h/2, 0)
            wire = Part.Wire(Part.makePolygon([p1, p2, p3, p4, p1]))
        else:
            r = min(radius, (w/2.0) - 0.001, (h/2.0) - 0.001)
            c1 = FreeCAD.Vector(-w/2+r, -h/2+r, 0)
            c2 = FreeCAD.Vector(w/2-r, -h/2+r, 0)
            c3 = FreeCAD.Vector(w/2-r, h/2-r, 0)
            c4 = FreeCAD.Vector(-w/2+r, h/2-r, 0)
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
        
        # Transform profile to correct orientation
        Z_new = tangent.normalize()
        Y_new = sketch_normal.normalize()
        X_new = Y_new.cross(Z_new).normalize()
        if X_new.Length < 0.0001:
            Y_new = FreeCAD.Vector(1, 0, 0) if abs(Z_new.x) < 0.9 else FreeCAD.Vector(0, 1, 0)
            X_new = Y_new.cross(Z_new).normalize()
            
        mat = FreeCAD.Matrix(
            X_new.x, Y_new.x, Z_new.x, start_pt.x,
            X_new.y, Y_new.y, Z_new.y, start_pt.y,
            X_new.z, Y_new.z, Z_new.z, start_pt.z,
            0, 0, 0, 1
        )
        wire.Placement = FreeCAD.Placement(mat)
        return wire

    def create_inner_box(self, w, h, length, start_pt, end_pt, sketch_normal, corner_radius=0):
        """
        Create a box aligned with the duct segment for subtraction.
        The box origin is at its bottom-left-back vertex (0,0,0 local).
        The box extends in +X (width), +Y (height), +Z (length).
        The box is aligned to match the inner duct's bottom-left origin.
        If corner_radius > 0, applies fillets to match the rounded rectangular profile.
        """
        # Create box at origin - extends from (0,0,0) to (w, h, length)
        box = Part.makeBox(w, h, length)
        
        # Apply fillets to corners if corner_radius is specified
        if corner_radius > 0.001:
            # The box has 4 vertical edges (corners) that need filleting
            # These are the edges parallel to Z axis at the 4 corners
            edges_to_fillet = []
            for edge in box.Edges:
                # Find vertical edges (parallel to Z axis in local space)
                edge_dir = edge.tangentAt(edge.FirstParameter).normalize()
                if abs(edge_dir.z) > 0.99:  # Vertical edge
                    edges_to_fillet.append(edge)
            
            if len(edges_to_fillet) == 4:
                try:
                    # Apply fillet to all 4 corners with the inner corner radius
                    box = box.makeFillet(corner_radius, edges_to_fillet)
                except Exception as e:
                    FreeCAD.Console.PrintWarning(f"Fillet application failed: {e}\n")
        
        # Calculate direction from start to end
        direction = (end_pt - start_pt).normalize()
        
        # Create coordinate system matching the duct profile orientation
        # Z_axis points along the duct direction (length axis of box)
        Z_axis = direction
        Y_axis = sketch_normal.normalize()
        X_axis = Y_axis.cross(Z_axis).normalize()
        if X_axis.Length < 0.0001:
            Y_temp = FreeCAD.Vector(1, 0, 0) if abs(Z_axis.x) < 0.9 else FreeCAD.Vector(0, 1, 0)
            X_axis = Y_temp.cross(Z_axis).normalize()
            Y_axis = Z_axis.cross(X_axis).normalize()
        
        # Build rotation matrix
        # The box local axes: X=width, Y=height, Z=length
        # We want box Z to align with duct direction
        # Box X and Y align with the profile plane (matching the duct profile)
        rot_mat = FreeCAD.Matrix(
            X_axis.x, Y_axis.x, Z_axis.x, 0,
            X_axis.y, Y_axis.y, Z_axis.y, 0,
            X_axis.z, Y_axis.z, Z_axis.z, 0,
            0, 0, 0, 1
        )
        
        # Position the box to align with the inner duct's bottom-left corner
        # The inner duct profile in local coordinates spans:
        #   X: [-w/2, +w/2], Y: [-h/2, +h/2]
        # The bottom-left corner of the inner duct is at (-w/2, -h/2) in local space
        # Since the box origin (0,0) should align with this corner:
        local_offset = FreeCAD.Vector(-w/2, -h/2, 0)
        
        # Transform local offset to world space
        world_offset = FreeCAD.Vector(
            X_axis.x * local_offset.x + Y_axis.x * local_offset.y,
            X_axis.y * local_offset.x + Y_axis.y * local_offset.y,
            X_axis.z * local_offset.x + Y_axis.z * local_offset.y
        )
        
        position = start_pt + world_offset
        
        # Apply placement
        placement = FreeCAD.Placement(position, FreeCAD.Rotation(rot_mat))
        box.Placement = placement
        
        return box

    def create_inner_cylinder(self, diameter, length, start_pt, end_pt):
        """
        Create a cylinder aligned with the pipe segment for subtraction.
        Cylinder origin is at its base circle center.
        """
        direction = (end_pt - start_pt).normalize()
        radius = diameter / 2.0
        
        # Create cylinder (aligned with Z axis by default, base at origin)
        cylinder = Part.makeCylinder(radius, length)
        
        # Calculate rotation to align with direction
        Z_axis = FreeCAD.Vector(0, 0, 1)
        
        if abs(direction.dot(Z_axis)) > 0.999:
            # Already aligned with Z
            if direction.z < 0:
                # Opposite direction, rotate 180 around X
                cylinder.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1, 0, 0), 180)
            placement = FreeCAD.Placement(start_pt, FreeCAD.Rotation())
        else:
            # Calculate rotation axis and angle
            rot_axis = Z_axis.cross(direction)
            rot_angle = math.degrees(Z_axis.getAngle(direction))
            
            placement = FreeCAD.Placement(start_pt, FreeCAD.Rotation(rot_axis, rot_angle))
        
        cylinder.Placement = placement
        return cylinder

    def get_property_value(self, obj, prop_names):
        """Get property value trying multiple possible names."""
        for name in prop_names:
            if hasattr(obj, name):
                val = getattr(obj, name)
                # Handle FreeCAD Quantity objects
                if hasattr(val, 'Value'):
                    return float(val.Value)
                return float(val)
        return None

    def rebuild_duct_network(self, obj, doc):
        """Rebuild a duct network using subtractive boxes aligned with the duct object."""
        obj_outers = []
        obj_inners = []
        
        # Get sketch name - now stored directly on the duct object
        sketch_name = getattr(obj, "SketchName", None)
        if not sketch_name:
            sketch_name = getattr(obj, "LinkedDuctSketchName", None)
        
        sketch = doc.getObject(sketch_name) if sketch_name else None
        
        if not sketch:
            QtWidgets.QMessageBox.critical(None, "Error", 
                f"Could not find the source sketch for {obj.Name}.\n"
                f"Make sure the sketch hasn't been deleted.")
            return None, None
        
        # Get duct properties - now directly from the duct object
        out_w = self.get_property_value(obj, ["DuctWidth", "Width"])
        out_h = self.get_property_value(obj, ["DuctHeight", "DuctDepth", "Height", "Depth"])
        thick = self.get_property_value(obj, ["DuctThickness", "Thickness"])
        out_r = self.get_property_value(obj, ["DuctRadius", "Radius"])
        
        # Use defaults if properties not found
        if out_w is None: out_w = 100.0
        if out_h is None: out_h = out_w
        if thick is None: thick = 2.0
        if out_r is None: out_r = 0.0
        
        # Calculate inner dimensions
        in_w = max(0.1, out_w - (2 * thick))
        in_h = max(0.1, out_h - (2 * thick))
        
        # Get profile type if available
        profile_type = "Rectangular"
        if hasattr(obj, "DuctProfileType"):
            profile_type = obj.DuctProfileType
        elif hasattr(obj, "ProfileType"):
            profile_type = obj.ProfileType
        
        # Calculate sketch normal
        sketch_normal = sketch.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        
        # Get valid edges from sketch
        valid_edges = [edge for edge in sketch.Shape.Edges if edge.Length > 0.001]
        if not valid_edges:
            return None, None
        
        # Get the duct object's placement for alignment
        duct_placement = obj.Placement if hasattr(obj, "Placement") else FreeCAD.Placement()
        
        # Process each edge
        for edge in valid_edges:
            start_pt = edge.valueAt(edge.FirstParameter)
            end_pt = edge.valueAt(edge.LastParameter)
            tangent = edge.tangentAt(edge.FirstParameter)
            length = edge.Length
            
            # Create outer solid sweep
            if profile_type == "Circular":
                # For round ducts, use circular profile
                circ = Part.Circle(start_pt, tangent, out_w / 2.0)
                prof_out = Part.Wire([circ.toShape()])
            else:
                # Rectangular or Rounded Rectangular
                prof_out = self.create_rect_profile(out_w, out_h, out_r, start_pt, tangent, sketch_normal)
            
            try:
                sweep_out = Part.Wire([edge]).makePipeShell([prof_out], True, False)
                if not sweep_out.isNull():
                    obj_outers.append(sweep_out)
            except:
                pass
            
            # Create inner subtractive shape (for hollow effect)
            # The shape is aligned with the duct object's coordinate system
            if profile_type == "Circular":
                # Circular duct: use cylinder subtraction
                inner_shape = self.create_inner_cylinder(in_w, length, start_pt, end_pt)
            elif profile_type == "Rounded Rectangular":
                # Rounded Rectangular: use box with filleted corners
                # The inner corner radius = outer corner radius - thickness
                inner_corner_r = max(0.0, out_r - thick)
                inner_shape = self.create_inner_box(in_w, in_h, length, start_pt, end_pt, sketch_normal, inner_corner_r)
            else:
                # Rectangular: use full box subtraction (no corner radius)
                inner_shape = self.create_inner_box(in_w, in_h, length, start_pt, end_pt, sketch_normal, 0)
            
            if inner_shape and not inner_shape.isNull():
                obj_inners.append(inner_shape)
        
        # Add junction solids for smooth intersections
        endpoints = []
        for edge in valid_edges:
            endpoints.append(edge.Vertexes[0].Point)
            endpoints.append(edge.Vertexes[-1].Point)
        
        intersection_points = []
        for pt in endpoints:
            count = sum(1 for p in endpoints if pt.isEqual(p, 0.001))
            if count > 1 and not any(pt.isEqual(ipt, 0.001) for ipt in intersection_points):
                intersection_points.append(pt)
        
        for pt in intersection_points:
            if profile_type == "Circular":
                # For round ducts, use spheres at junctions
                obj_outers.append(Part.makeSphere(out_w / 2.0, pt))
                obj_inners.append(Part.makeSphere(in_w / 2.0, pt))
            else:
                # For rectangular ducts, use intersection boxes aligned with sketch plane
                box_size = max(out_w, out_h) + 20.0  # Extra size to ensure overlap
                
                # Create outer box
                junction_box_outer = Part.makeBox(box_size, box_size, box_size)
                
                # Create inner box (with fillets for rounded rectangular)
                junction_box_inner = Part.makeBox(in_w, in_h, box_size + 2.0)
                
                # Apply fillets to inner junction box for rounded rectangular
                if profile_type == "Rounded Rectangular":
                    inner_corner_r = max(0.0, out_r - thick)
                    if inner_corner_r > 0.001:
                        edges_to_fillet = []
                        for edge in junction_box_inner.Edges:
                            edge_dir = edge.tangentAt(edge.FirstParameter).normalize()
                            if abs(edge_dir.z) > 0.99:  # Vertical edge
                                edges_to_fillet.append(edge)
                        if len(edges_to_fillet) == 4:
                            try:
                                junction_box_inner = junction_box_inner.makeFillet(inner_corner_r, edges_to_fillet)
                            except:
                                pass
                
                # Align with sketch plane
                Z_axis = sketch_normal.normalize()
                Y_temp = FreeCAD.Vector(1, 0, 0) if abs(Z_axis.x) < 0.9 else FreeCAD.Vector(0, 1, 0)
                X_axis = Y_temp.cross(Z_axis).normalize()
                Y_axis = Z_axis.cross(X_axis).normalize()
                
                rot_mat = FreeCAD.Matrix(
                    X_axis.x, Y_axis.x, Z_axis.x, 0,
                    X_axis.y, Y_axis.y, Z_axis.y, 0,
                    X_axis.z, Y_axis.z, Z_axis.z, 0,
                    0, 0, 0, 1
                )
                
                # Align outer box to inner duct's bottom-left corner (centered on junction point)
                outer_offset = FreeCAD.Vector(-box_size/2, -box_size/2, -box_size/2)
                world_outer_offset = FreeCAD.Vector(
                    X_axis.x * outer_offset.x + Y_axis.x * outer_offset.y + Z_axis.x * outer_offset.z,
                    X_axis.y * outer_offset.x + Y_axis.y * outer_offset.y + Z_axis.y * outer_offset.z,
                    X_axis.z * outer_offset.x + Y_axis.z * outer_offset.y + Z_axis.z * outer_offset.z
                )
                
                # Align inner box to inner duct's bottom-left corner
                inner_offset = FreeCAD.Vector(-in_w/2, -in_h/2, -(box_size + 2.0)/2)
                world_inner_offset = FreeCAD.Vector(
                    X_axis.x * inner_offset.x + Y_axis.x * inner_offset.y + Z_axis.x * inner_offset.z,
                    X_axis.y * inner_offset.x + Y_axis.y * inner_offset.y + Z_axis.y * inner_offset.z,
                    X_axis.z * inner_offset.x + Y_axis.z * inner_offset.y + Z_axis.z * inner_offset.z
                )
                
                junction_box_outer.Placement = FreeCAD.Placement(pt + world_outer_offset, FreeCAD.Rotation(rot_mat))
                junction_box_inner.Placement = FreeCAD.Placement(pt + world_inner_offset, FreeCAD.Rotation(rot_mat))
                
                obj_outers.append(junction_box_outer)
                obj_inners.append(junction_box_inner)
        
        return obj_outers, obj_inners

    def rebuild_pipe_network(self, obj, doc):
        """Rebuild a pipe network using subtractive cylinders."""
        obj_outers = []
        obj_inners = []
        
        # Get sketch name - now stored directly on the pipe object
        sketch_name = getattr(obj, "SketchName", None)
        if not sketch_name:
            return None, None
        
        sketch = doc.getObject(sketch_name)
        if not sketch:
            QtWidgets.QMessageBox.critical(None, "Error", 
                f"Could not find the source sketch for {obj.Name}.")
            return None, None
        
        # Get pipe properties from the object itself
        od = self.get_property_value(obj, ["PipeOuter", "OuterDiameter"])
        id_val = self.get_property_value(obj, ["PipeInner", "InnerDiameter"])
        
        if od is None:
            QtWidgets.QMessageBox.critical(None, "Data Error", 
                f"{obj.Name} is missing pipe diameter data.")
            return None, None
        
        if id_val is None:
            id_val = od * 0.8  # Default to 80% if inner not found
        
        valid_edges = [edge for edge in sketch.Shape.Edges if edge.Length > 0.001]
        
        for edge in valid_edges:
            start_pt = edge.valueAt(edge.FirstParameter)
            end_pt = edge.valueAt(edge.LastParameter)
            tangent = edge.tangentAt(edge.FirstParameter)
            length = edge.Length
            
            # Create outer solid sweep (circular pipe)
            circ = Part.Circle(start_pt, tangent, od / 2.0)
            prof_out = Part.Wire([circ.toShape()])
            
            try:
                sweep_out = Part.Wire([edge]).makePipeShell([prof_out], True, True)
                if not sweep_out.isNull():
                    obj_outers.append(sweep_out)
            except:
                pass
            
            # Create inner subtractive cylinder
            inner_cyl = self.create_inner_cylinder(id_val, length, start_pt, end_pt)
            if inner_cyl and not inner_cyl.isNull():
                obj_inners.append(inner_cyl)
        
        # Add spheres at intersections for smooth outer shell
        endpoints = []
        for edge in valid_edges:
            endpoints.append(edge.Vertexes[0].Point)
            endpoints.append(edge.Vertexes[-1].Point)
        
        intersection_points = []
        for pt in endpoints:
            count = sum(1 for p in endpoints if pt.isEqual(p, 0.001))
            if count > 1 and not any(pt.isEqual(ipt, 0.001) for ipt in intersection_points):
                intersection_points.append(pt)
        
        for pt in intersection_points:
            obj_outers.append(Part.makeSphere(od / 2.0, pt))
            obj_inners.append(Part.makeSphere(id_val / 2.0, pt))
        
        return obj_outers, obj_inners

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        if len(sel) < 2:
            QtWidgets.QMessageBox.warning(None, "Selection Error", 
                "Please hold CTRL and select at least TWO objects to merge.")
            return

        inherited_color = None
        for obj in sel:
            if hasattr(obj, "ViewObject") and obj.ViewObject is not None and hasattr(obj.ViewObject, "ShapeColor"):
                inherited_color = obj.ViewObject.ShapeColor
                break

        outer_solids = []
        inner_solids = []
        fitting_solids = []
        doc = FreeCAD.ActiveDocument

        for obj in sel:
            # Get object placement matrix for transformation
            obj_matrix = obj.Placement.toMatrix() if hasattr(obj, "Placement") else FreeCAD.Matrix()

            obj_outers = []
            obj_inners = []
            
            # --- DETECT AND REBUILD DUCTS ---
            is_duct = False
            duct_indicators = ["DuctWidth", "DuctHeight", "DuctThickness", "Width", "Height", "Thickness"]
            for indicator in duct_indicators:
                if hasattr(obj, indicator):
                    # Make sure it's not a pipe (has PipeOuter)
                    if not hasattr(obj, "PipeOuter"):
                        is_duct = True
                        break
            
            if is_duct:
                obj_outers, obj_inners = self.rebuild_duct_network(obj, doc)
                if obj_outers is None:
                    return  # Error already shown
                    
            # --- DETECT AND REBUILD PIPES ---
            elif hasattr(obj, "PipeOuter") or hasattr(obj, "PipeInner"):
                obj_outers, obj_inners = self.rebuild_pipe_network(obj, doc)
                if obj_outers is None:
                    return  # Error already shown
                    
            # --- GENERIC SOLID FALLBACK ---
            else:
                try:
                    shape_copy = obj.Shape.copy()
                    shape_copy.transformShape(obj_matrix)
                    fitting_solids.append(shape_copy)
                except:
                    pass
                continue

            if not obj_outers:
                continue

            # Apply placement transform and add to master lists
            for s in obj_outers:
                s.transformShape(obj_matrix)
                outer_solids.append(s)
            for s in obj_inners:
                s.transformShape(obj_matrix)
                inner_solids.append(s)

        if not outer_solids and not fitting_solids:
            QtWidgets.QMessageBox.warning(None, "Nothing to Merge", 
                "No valid hollow networks found in selection.")
            return

        try:
            # Fuse all outer solids together
            if outer_solids:
                master_outer = outer_solids[0]
                for shape in outer_solids[1:]:
                    master_outer = master_outer.fuse(shape)
                master_outer = master_outer.removeSplitter()

            # Fuse all inner solids together
            if inner_solids:
                master_inner = inner_solids[0]
                for shape in inner_solids[1:]:
                    master_inner = master_inner.fuse(shape)
                master_inner = master_inner.removeSplitter()

            # Final cut to create hollow result
            if outer_solids and inner_solids:
                final_shape = master_outer.cut(master_inner)
                final_shape = final_shape.removeSplitter()
            elif outer_solids:
                final_shape = master_outer
            elif fitting_solids:
                final_shape = fitting_solids[0]
                fitting_solids = fitting_solids[1:]
            else:
                raise Exception("No geometry to merge")
            
            # Fuse any additional fitting solids
            for fit_shape in fitting_solids:
                final_shape = final_shape.fuse(fit_shape)
            
            if final_shape.isNull():
                raise Exception("Boolean sequence returned a Null geometry.")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Boolean Error", 
                f"Failed to merge geometries.\n\nError: {str(e)}")
            return

        # Create the merged object
        doc.openTransaction("Merge Hollow Networks")
        try:
            parent_container = None
            is_body = False
            for parent in sel[0].InList:
                if parent.isDerivedFrom("PartDesign::Body"):
                    parent_container = parent
                    is_body = True
                    break
                elif parent.isDerivedFrom("App::Part") or parent.isDerivedFrom("App::DocumentObjectGroup"):
                    parent_container = parent

            if is_body:
                raw_merge = doc.addObject("Part::Feature", "Raw_Merged_Data")
                raw_merge.Shape = final_shape
                raw_merge.ViewObject.Visibility = False
                
                merged_obj = parent_container.newObject("PartDesign::FeatureBase", "Merged_Network")
                merged_obj.BaseFeature = raw_merge
                
                if inherited_color and hasattr(raw_merge, "ViewObject") and raw_merge.ViewObject:
                    raw_merge.ViewObject.ShapeColor = inherited_color
            else:
                merged_obj = doc.addObject("Part::Feature", "Merged_Network")
                merged_obj.Shape = final_shape
                if parent_container:
                    parent_container.addObject(merged_obj)

            if inherited_color and hasattr(merged_obj, "ViewObject") and merged_obj.ViewObject:
                merged_obj.ViewObject.ShapeColor = inherited_color

            # Store reference to source networks
            try:
                if not hasattr(merged_obj, "SourceNetworks"):
                    merged_obj.addProperty("App::PropertyLinkList", "SourceNetworks", "MergeData", 
                                          "Original networks merged into this object")
                merged_obj.SourceNetworks = sel
            except:
                pass
            
            if hasattr(merged_obj, "Refine"):
                merged_obj.Refine = True
                
            # Hide original objects
            for obj in sel:
                if hasattr(obj, "ViewObject") and obj.ViewObject:
                    obj.ViewObject.hide()

            doc.recompute()
            doc.commitTransaction()
            
        except Exception as e:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(None, "Error", 
                f"Failed to place merged geometry.\n\n{e}")


FreeCADGui.addCommand('Merge_Networks', MergeHollowNetworks())
