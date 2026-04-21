import os
import FreeCAD
import Part
import FreeCADGui

# Constants
TOLERANCE = 0.001

def get_icon_path(filename):
    """Dynamically resolves icon paths relative to this module."""
    base_path = os.path.dirname(__file__)
    path = os.path.join(base_path, "Resources", "icons", filename)
    if os.path.exists(path):
        return path
    # Fallback for standard icons if file not found
    return filename

def calculate_orientation(tangent, normal):
    """
    Robustly calculates a local coordinate system (X, Y, Z) for a given tangent and normal.
    Prevents gimbal lock when vectors are parallel.
    """
    Z = tangent.normalize()
    # Try using the provided normal first
    Y = normal.normalize()
    
    # Check if tangent and normal are parallel
    if abs(Z.dot(Y)) > 0.99:
        # Fallback to an arbitrary axis
        if abs(Z.x) < 0.9:
            Y = FreeCAD.Vector(1, 0, 0)
        else:
            Y = FreeCAD.Vector(0, 1, 0)
            
    X = Y.cross(Z).normalize()
    Y = Z.cross(X).normalize() # Ensure exact orthogonality
    
    return X, Y, Z

def fuse_shapes(shapes):
    """Optimized fusion of multiple shapes using Compound + BOP."""
    if not shapes:
        return None
    if len(shapes) == 1:
        return shapes[0]
        
    try:
        # Part.makeCompound is O(n), then one fusion is much faster than looping fuse()
        compound = Part.makeCompound(shapes)
        return compound.fuse()
    except:
        # Fallback to iterative if complex BOP fails
        master = shapes[0]
        for s in shapes[1:]:
            master = master.fuse(s)
        return master

def get_container(doc, sketch):
    """Finds or creates the appropriate container (Body, Part, Group) for a new object."""
    body = None
    for parent in sketch.InList:
        if parent.isDerivedFrom("PartDesign::Body"):
            body = parent
            return body, True
            
    for parent in sketch.InList:
        if parent.isDerivedFrom("App::Part") or parent.isDerivedFrom("App::DocumentObjectGroup"):
            return parent, False
            
    return None, False

def add_common_properties(obj, sketch, data_dict):
    """Safely adds custom properties to an object."""
    try:
        if not hasattr(obj, "SketchName"):
            obj.addProperty("App::PropertyString", "SketchName", "ComfacData", "Source Sketch")
        obj.SketchName = sketch.Name
        
        for key, value in data_dict.items():
            prop_type = "App::PropertyFloat" if isinstance(value, float) else "App::PropertyString"
            if not hasattr(obj, key):
                obj.addProperty(prop_type, key, "ComfacData")
            setattr(obj, key, value)
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"Could not add properties: {e}")

class PreviewManager:
    """
    UNIVERSAL LIVE PREVIEW ENGINE
    Handles dynamic live-preview generation for UI Task Panels.
    Creates a semi-transparent ghost object that updates in real-time.
    """
    def __init__(self, doc, name="Live_Preview_Ghost"):
        self.doc = doc
        self.name = name
        self.preview_obj = None

    def update(self, shape, color=(0.8, 0.8, 0.2)):
        """Pushes a new geometric shape to the ghost object."""
        if not self.preview_obj:
            self.preview_obj = self.doc.addObject("Part::Feature", self.name)
        
        self.preview_obj.Shape = shape
        if self.preview_obj.ViewObject:
            # Set to a yellow/gold ghost color with 50% transparency
            self.preview_obj.ViewObject.ShapeColor = color
            self.preview_obj.ViewObject.Transparency = 50 
        self.doc.recompute()

    def clear(self):
        """Wipes the ghost object from the tree when the dialog closes."""
        if self.preview_obj:
            try:
                self.doc.removeObject(self.preview_obj.Name)
            except:
                pass
            self.preview_obj = None
            self.doc.recompute()

def sweep_sketch_wires(sketch, profile_callback, make_solid=False, transition_mode=1):
    """
    UNIVERSAL SWEEP ENGINE
    Sweeps a custom 2D profile along all continuous wires in a sketch.
    
    :param sketch: The FreeCAD SketchObject
    :param profile_callback: A function that takes (start_pt, tangent, sketch_normal) and returns a Part.Wire
    :param make_solid: True for solid CFD/Pipes, False for hollow walls/shells
    :param transition_mode: 1 for Sharp/Mitered corners, 2 for Rounded corners
    """
    import Part
    import FreeCAD
    
    shapes = []
    
    # Calculate the 3D plane the sketch is drawn on
    sketch_normal = sketch.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))

    # Safely extract wires (continuous lines) from the sketch
    wires = sketch.Shape.Wires
    if not wires:
        wires = [Part.Wire([e]) for e in sketch.Shape.Edges]

    for wire in wires:
        if wire.Length < TOLERANCE: continue
        
        ordered_edges = wire.OrderedEdges
        if not ordered_edges: continue
        
        # Get the starting coordinates and direction
        first_edge = ordered_edges[0]
        start_pt = first_edge.valueAt(first_edge.FirstParameter)
        tangent = first_edge.tangentAt(first_edge.FirstParameter).normalize()
        
        # --- THE MAGIC CALLBACK ---
        # We ask the specific tool (Wall, Pipe, Duct) to draw its specific profile here!
        prof = profile_callback(start_pt, tangent, sketch_normal)
        
        if not prof: continue
        
        try:
            # Sweep the profile along the wire using the requested physics mode
            sweep = wire.makePipeShell([prof], make_solid, False, transition_mode)
            if not sweep.isNull():
                shapes.append(sweep)
        except Exception as e:
            FreeCAD.Console.PrintError(f"Universal Sweep failed: {e}\n")

    if not shapes: 
        return None
        
    return fuse_shapes(shapes)