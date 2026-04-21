import os
import json
import FreeCAD
import FreeCADGui
import Part
import math
from compat import QtWidgets, QtCore, QtGui

# External ComfacTools modules
import ComfacUtils
import Pipes.CreateNetworkPipeFittings as PFittings


# =========================================================
# 1. UNIFIED ROUTER & GENERATOR TASK PANEL
# =========================================================
class PipeRouterTaskPanel:
    def __init__(self, router):
        self.router = router
        self.form = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QVBoxLayout(self.form)
        
        # --- 1. PIPE SPECIFICATIONS (From Generator) ---
        self.settings_group = QtWidgets.QGroupBox("Pipe Specifications")
        self.form_layout = QtWidgets.QFormLayout(self.settings_group)
        
        # Load external data
        self.pipe_data = {}
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "PipeData.json")
        try:
            if os.path.exists(data_path):
                with open(data_path, 'r') as f:
                    self.pipe_data = json.load(f)
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to load pipe data: {e}\n")

          # Load colors from external file
        self.colors = {}
        color_path = os.path.join(os.path.dirname(__file__), "..", "data", "PipeColors.json")
        try:
            with open(color_path, 'r') as f:
                self.colors = json.load(f)
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to load pipe colors: {e}\n")

        self.default_colors = self.colors.get("default_colors", {})
        self.default_colors["PVC"] = None  # Uses dropdown
        self.pvc_colors = self.colors.get("pvc_colors", {})

        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.addItems(list(self.pipe_data.keys()) if self.pipe_data else ["Custom"])

        self.size_cb = QtWidgets.QComboBox()
        self.color_cb = QtWidgets.QComboBox()
        
        self.outer_input = QtWidgets.QDoubleSpinBox()
        self.outer_input.setRange(0.1, 2000.0)
        self.outer_input.setDecimals(2)
        self.outer_input.setSuffix(" mm")
        self.outer_input.setValue(40.0) # Default
        
        self.thick_input = QtWidgets.QDoubleSpinBox()
        self.thick_input.setRange(0.1, 500.0)
        self.thick_input.setDecimals(2)
        self.thick_input.setSuffix(" mm")
        self.thick_input.setValue(2.0) # Default
        
        self.form_layout.addRow("Pipe Type:", self.type_cb)
        self.form_layout.addRow("Pipe Size:", self.size_cb)
        self.form_layout.addRow("Color:", self.color_cb)
        self.form_layout.addRow("Outer Diameter:", self.outer_input)
        self.form_layout.addRow("Wall Thickness:", self.thick_input)

        self.type_cb.currentTextChanged.connect(self.update_sizes_dropdown)
        self.type_cb.currentTextChanged.connect(self.update_color_options)
        self.size_cb.currentIndexChanged.connect(self.update_ui)
        self.outer_input.valueChanged.connect(self.update_router_radius)

        if self.pipe_data:
            self.update_sizes_dropdown(self.type_cb.currentText())
            self.update_ui()
        else:
            self.update_router_radius()

        self.main_layout.addWidget(self.settings_group)

        # --- 2. ROUTER CONTROLS (Cheat Sheet) ---
        self.info_group = QtWidgets.QGroupBox("Routing Controls")
        self.info_layout = QtWidgets.QVBoxLayout(self.info_group)
        
        desc = QtWidgets.QLabel("Draw 3D pipes with exact dimensions and magnetic T-branching.")
        desc.setWordWrap(True)
        
        controls_html = """
        <table width="100%" style="font-size: 11px;">
          <tr><td width="35%"><b>Left-Click</b></td><td>Place Node / Snap</td></tr>
          <tr><td><b>Right-Click</b></td><td>Finish & Build Pipe</td></tr>
          <tr><td><b>` (Backtick)</b></td><td>Cycle Axis Lock</td></tr>
          <tr><td><b>P</b></td><td>Cycle Working Plane</td></tr>
          <tr><td><b>Enter</b></td><td>Type Dimensions</td></tr>
          <tr><td><b>Tab</b></td><td>Toggle Length/Angle</td></tr>
          <tr><td><b>U</b></td><td>Undo Last Point</td></tr>
          <tr><td><b>B</b></td><td>Lift Pen (Branching)</td></tr>
          <tr><td><b>ESC</b></td><td>Cancel Route</td></tr>
        </table>
        """
        controls_lbl = QtWidgets.QLabel(controls_html)
        controls_lbl.setTextFormat(QtCore.Qt.RichText)
        
        self.info_layout.addWidget(desc)
        self.info_layout.addWidget(controls_lbl)
        self.main_layout.addWidget(self.info_group)
        self.main_layout.addStretch(1) 

    def update_sizes_dropdown(self, val_type):
        self.size_cb.blockSignals(True)
        self.size_cb.clear()
        if val_type in self.pipe_data:
            self.size_cb.addItems(list(self.pipe_data[val_type].keys()))
        self.size_cb.addItem("Custom")
        self.size_cb.blockSignals(False)
        self.update_color_options(val_type)
        self.update_ui()

    def update_color_options(self, val_type):
        self.color_cb.blockSignals(True)
        self.color_cb.clear()
        is_pvc = "PVC" in val_type
        if is_pvc:
            self.color_cb.addItems(list(self.pvc_colors.keys()))
            self.color_cb.setEnabled(True)
        else:
            self.color_cb.setEnabled(False)
        self.color_cb.blockSignals(False)

    def update_ui(self):
        val_type = self.type_cb.currentText()
        val_size = self.size_cb.currentText()
        if val_type in self.pipe_data and val_size in self.pipe_data[val_type]:
            od, wt = self.pipe_data[val_type][val_size]
            self.outer_input.setValue(od)
            self.thick_input.setValue(wt)
            self.outer_input.setEnabled(False)
            self.thick_input.setEnabled(False)
        else:
            self.outer_input.setEnabled(True)
            self.thick_input.setEnabled(True)
        self.update_router_radius()

    def update_router_radius(self):
        # Update live preview cylinder radius based on UI selection
        radius = self.outer_input.value() / 2.0
        self.router.visual_radius = radius
        
        # Dynamically update the size of already drawn pipes in the viewport
        if hasattr(self.router, 'temp_ghosts') and hasattr(self.router, 'temp_lines'):
            for i, ghost in enumerate(self.router.temp_ghosts):
                if i < len(self.router.temp_lines):
                    seg = self.router.temp_lines[i]
                    if ghost and seg and hasattr(ghost, 'Shape') and hasattr(seg, 'Shape'):
                        try:
                            # Re-calculate the vector and draw a new cylinder with the updated radius
                            p_prev = seg.Shape.Vertexes[0].Point
                            p_final = seg.Shape.Vertexes[-1].Point
                            vec = p_final - p_prev
                            
                            ghost.Shape = Part.makeCylinder(radius, vec.Length, p_prev, vec)
                        except Exception:
                            pass
            FreeCAD.ActiveDocument.recompute()

    def get_selected_color(self):
        val_type = self.type_cb.currentText()
        if "PVC" in val_type:
            color_name = self.color_cb.currentText()
            return self.pvc_colors.get(color_name, (0.5, 0.5, 0.5))
        for key, color in self.default_colors.items():
            if key in val_type: return color
        return (0.5, 0.5, 0.5)

    def get_pipe_type(self):
        return self.type_cb.currentText()

    def accept(self):
        # Triggered when "OK" is clicked or Enter is pressed on the panel.
        self.router.finish_route()
        return True

    def reject(self):
        self.router.cancel_route()
        return True
        
    def getStandardButtons(self):
        ok_flag = QtWidgets.QDialogButtonBox.Ok
        cancel_flag = QtWidgets.QDialogButtonBox.Cancel
        ok_val = ok_flag.value if hasattr(ok_flag, 'value') else int(ok_flag)
        cancel_val = cancel_flag.value if hasattr(cancel_flag, 'value') else int(cancel_flag)
        return ok_val | cancel_val


# =========================================================
# 2. INTERACTIVE HUD WIDGET
# =========================================================
class RouterHUDWidget(QtWidgets.QWidget):
    def __init__(self, router):
        super().__init__()
        self.router = router 
        
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.frame = QtWidgets.QFrame()
        self.frame.setStyleSheet("background-color: rgba(30, 30, 30, 220); border: 1px solid #888; border-radius: 4px;")
        layout = QtWidgets.QHBoxLayout(self.frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        
        self.mode_lbl = QtWidgets.QLabel("[FREE]")
        self.mode_lbl.setStyleSheet("color: white; font-weight: bold; border: none; background: transparent;")
        
        self.len_input = QtWidgets.QLineEdit(self.frame)
        self.len_input.setFixedWidth(55) 
        self.len_input.setStyleSheet("background-color: #222; color: white; border: 1px inset #555; padding: 2px;")
        self.len_input.returnPressed.connect(self.commit_typed_values)
        
        self.unit_lbl = QtWidgets.QLabel("mm")
        self.unit_lbl.setStyleSheet("color: white; border: none; background: transparent; padding-right: 5px;")
        
        self.ang_input = QtWidgets.QLineEdit(self.frame)
        self.ang_input.setFixedWidth(45) 
        self.ang_input.setStyleSheet("background-color: #222; color: white; border: 1px inset #555; padding: 2px;")
        self.ang_input.returnPressed.connect(self.commit_typed_values)
        
        self.deg_lbl = QtWidgets.QLabel("°")
        self.deg_lbl.setStyleSheet("color: white; font-weight: bold; border: none; background: transparent;")
        
        self.plane_lbl = QtWidgets.QLabel("[XY]")
        self.plane_lbl.setStyleSheet("color: #44FF44; font-weight: bold; border: none; background: transparent;")

        self.setTabOrder(self.len_input, self.ang_input)
        
        layout.addWidget(self.mode_lbl)
        layout.addWidget(self.len_input)
        layout.addWidget(self.unit_lbl)
        layout.addWidget(self.ang_input)
        layout.addWidget(self.deg_lbl)
        layout.addWidget(self.plane_lbl)
        main_layout.addWidget(self.frame)

    def commit_typed_values(self):
        if not self.router.input_mode: return
        try:
            val_len = float(self.len_input.text().strip())
            val_ang = float(self.ang_input.text().strip())
            rad = math.radians(val_ang)
            
            p_prev = self.router.routing_nodes[-1]
            m = self.router.lock_mode
            wp = self.router.working_plane
            
            if m == 0:
                xy_length = math.hypot(self.router.current_dir.x, self.router.current_dir.y)
                if xy_length > 1e-6:
                    new_dir = FreeCAD.Vector(xy_length * math.cos(rad), xy_length * math.sin(rad), self.router.current_dir.z).normalize()
                else:
                    new_dir = FreeCAD.Vector(math.cos(rad), math.sin(rad), 0)
            else:
                A = self.router.current_dir
                raw_d = getattr(self.router, "raw_dir", FreeCAD.Vector(1,0,0))
                
                if wp == 'XY':
                    if m == 1: P = FreeCAD.Vector(0, 1 if raw_d.y >= 0 else -1, 0)
                    elif m == 2: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                    elif m == 3: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                elif wp == 'XZ':
                    if m == 1: P = FreeCAD.Vector(0, 0, 1 if raw_d.z >= 0 else -1)
                    elif m == 2: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                    elif m == 3: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                elif wp == 'YZ':
                    if m == 1: P = FreeCAD.Vector(0, 1 if raw_d.y >= 0 else -1, 0)
                    elif m == 2: P = FreeCAD.Vector(0, 0, 1 if raw_d.z >= 0 else -1)
                    elif m == 3: P = FreeCAD.Vector(0, 1 if raw_d.y >= 0 else -1, 0)

                new_dir = A * math.cos(rad) + P * math.sin(rad)

            final_pt = p_prev + new_dir * val_len
            self.router.add_segment(final_pt)
            self.router.update_axis_indicator(final_pt)
        except ValueError:
            pass 
            
        self.len_input.setModified(False)
        self.ang_input.setModified(False)
        self.router.input_mode = False
        self.frame.setStyleSheet("background-color: rgba(30, 30, 30, 220); border: 1px solid #888; border-radius: 4px;")
        self.len_input.clearFocus()
        self.ang_input.clearFocus()
        QtCore.QTimer.singleShot(10, self.router.force_viewport_focus)


# =========================================================
# 3. KEYBOARD FILTER
# =========================================================
class RouterKeyFilter(QtCore.QObject):
    def __init__(self, router):
        super().__init__()
        self.router = router

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()

            if self.router.input_mode:
                if key == QtCore.Qt.Key_Escape:
                    self.router.input_mode = False
                    self.router.hud.frame.setStyleSheet("background-color: rgba(30, 30, 30, 220); border: 1px solid #888; border-radius: 4px;")
                    self.router.hud.len_input.clearFocus()
                    self.router.hud.ang_input.clearFocus()
                    self.router.force_viewport_focus()
                    return True
                return False 

            else:
                if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    if len(self.router.routing_nodes) > 0 and getattr(self.router, "current_dir", None):
                        self.router.input_mode = True
                        self.router.hud.len_input.setModified(False)
                        self.router.hud.ang_input.setModified(False)
                        self.router.hud.frame.setStyleSheet("background-color: rgba(10, 50, 90, 240); border: 1px solid #4488FF; border-radius: 4px;")
                        self.router.hud.raise_()
                        self.router.hud.activateWindow()
                        self.router.hud.len_input.setFocus()
                        self.router.hud.len_input.selectAll()
                    return True

                if key == QtCore.Qt.Key_QuoteLeft:
                    self.router.lock_mode = (self.router.lock_mode + 1) % 4
                    hex_color = self.router.get_dynamic_color(as_hex=True)
                    self.router.hud.mode_lbl.setStyleSheet(f"color: {hex_color}; font-weight: bold; border: none; background: transparent;")
                    
                    self.router.hud.ang_input.setEnabled(True)
                    self.router.hud.ang_input.setStyleSheet("background-color: #222; color: white; border: 1px inset #555; padding: 2px;")

                    if not self.router.routing_nodes:
                        self.router.hud.ang_input.setText("0.00")
                        if self.router.lock_mode == 0: self.router.hud.deg_lbl.setText("°")

                    if self.router.routing_nodes: 
                        self.router.update_axis_indicator(self.router.routing_nodes[-1])
                    return True
                
                if key == QtCore.Qt.Key_P:
                    planes = ['XY', 'XZ', 'YZ']
                    colors = ['#44FF44', '#FF4444', '#4444FF']
                    idx = (planes.index(self.router.working_plane) + 1) % 3
                    self.router.working_plane = planes[idx]
                    self.router.hud.plane_lbl.setText(f"[{planes[idx]}]")
                    self.router.hud.plane_lbl.setStyleSheet(f"color: {colors[idx]}; font-weight: bold; border: none; background: transparent;")
                    return True

                if key == QtCore.Qt.Key_U:
                    if len(self.router.routing_nodes) > 1:
                        self.router.routing_nodes.pop()
                        
                        if self.router.temp_lines:
                            last_line = self.router.temp_lines.pop()
                            try:
                                if getattr(last_line, "Name", None) and self.router.doc.getObject(last_line.Name): 
                                    self.router.doc.removeObject(last_line.Name)
                            except ReferenceError: pass
                            
                        if self.router.temp_ghosts:
                            last_ghost = self.router.temp_ghosts.pop()
                            try:
                                if getattr(last_ghost, "Name", None) and self.router.doc.getObject(last_ghost.Name): 
                                    self.router.doc.removeObject(last_ghost.Name)
                            except ReferenceError: pass
                            
                        if self.router.temp_labels:
                            last_lbl = self.router.temp_labels.pop()
                            try:
                                if getattr(last_lbl, "Name", None) and self.router.doc.getObject(last_lbl.Name): 
                                    self.router.doc.removeObject(last_lbl.Name)
                            except ReferenceError: pass
                            
                        if len(self.router.routing_nodes) < 2 and self.router.hud:
                            self.router.hud.hide()
                        self.router.doc.recompute()
                    return True
                    
                if key == QtCore.Qt.Key_B:
                    if self.router.routing_nodes:
                        self.router.routing_nodes = [] 
                        if getattr(self.router, "preview_line", None): self.router.preview_line.ViewObject.Visibility = False
                        FreeCAD.Console.PrintMessage("Pen Lifted. Click near a pipe to branch, or anywhere to start a new line.\n")
                    return True

                if key == QtCore.Qt.Key_Escape:
                    self.router.prompt_cancel()
                    return True

        return False


# =========================================================
# 4. MAIN WORKBENCH COMMAND (MERGED ROUTER & GENERATOR)
# =========================================================
class PipeRouterCommand:
    def GetResources(self):
        return {
            'Pixmap': 'Draft_Wire', 
            'MenuText': 'Smart Pipe Router',
            'ToolTip': 'Draw a 3D pipe route and automatically generate network pipes.'
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        self.doc = FreeCAD.ActiveDocument
        self.view = FreeCADGui.ActiveDocument.ActiveView
        if not self.doc or not self.view: return

        self.is_tool_active = True 
        self.routing_nodes = []
        self.temp_lines = []      
        self.temp_ghosts = []     
        self.temp_labels = [] 
        self.target_route = None 
        self.lock_mode = 0 
        self.input_mode = False 
        self.current_dir = None 
        self.raw_dir = None 
        self.working_plane = 'XY' 
        self.visual_radius = 20.0 

        self.hud = None
        self.key_filter = None
        self.mouse_id = None
        self.move_id = None
        self.preview_line = None
        self.axis_x = None
        self.axis_y = None
        self.axis_z = None
        self.task_panel = None

        self.setup_ui()
        
        self.mouse_id = self.view.addEventCallback("SoMouseButtonEvent", self.click_observer)
        self.move_id = self.view.addEventCallback("SoLocation2Event", self.move_observer)
        self.key_filter = RouterKeyFilter(self)
        QtWidgets.QApplication.instance().installEventFilter(self.key_filter)
        
        self.task_panel = PipeRouterTaskPanel(self)
        FreeCADGui.Control.showDialog(self.task_panel)

    def setup_ui(self):
        self.preview_line = self.doc.addObject("Part::Feature", "Live_Preview")
        self.preview_line.ViewObject.Transparency = 60 
        self.preview_line.ViewObject.Visibility = False 

        size = 10
        for ax_name, color in [("Axis_X", (1.0, 0.0, 0.0)), ("Axis_Y", (0.0, 1.0, 0.0)), ("Axis_Z", (0.0, 0.0, 1.0))]:
            ax = self.doc.addObject("Part::Feature", ax_name)
            
            if ax_name == "Axis_X": pA, pB = FreeCAD.Vector(-size, 0, 0), FreeCAD.Vector(size, 0, 0)
            elif ax_name == "Axis_Y": pA, pB = FreeCAD.Vector(0, -size, 0), FreeCAD.Vector(0, size, 0)
            else: pA, pB = FreeCAD.Vector(0, 0, -size), FreeCAD.Vector(0, 0, size)
                
            ax.Shape = Part.LineSegment(pA, pB).toShape()
            ax.ViewObject.LineColor = color
            ax.ViewObject.LineWidth = 3
            ax.ViewObject.Transparency = 50 
            
            if ax_name == "Axis_X": self.axis_x = ax
            elif ax_name == "Axis_Y": self.axis_y = ax
            else: self.axis_z = ax

        self.hud = RouterHUDWidget(self)

    def get_mode_name(self):
        return {0: "FREE", 1: "X-AXIS", 2: "Y-AXIS", 3: "Z-AXIS"}[self.lock_mode]

    def get_dynamic_color(self, vec=None, as_hex=False):
        m = self.lock_mode
        if m == 1: return "#FF4444" if as_hex else (1.0, 0.0, 0.0)
        if m == 2: return "#44FF44" if as_hex else (0.0, 1.0, 0.0)
        if m == 3: return "#4444FF" if as_hex else (0.0, 0.0, 1.0)
        
        if vec and vec.Length > 0.01:
            dx, dy, dz = abs(vec.x), abs(vec.y), abs(vec.z)
            if dx > dy * 10 and dx > dz * 10: return "#FF4444" if as_hex else (1.0, 0.0, 0.0) 
            if dy > dx * 10 and dy > dz * 10: return "#44FF44" if as_hex else (0.0, 1.0, 0.0) 
            if dz > dx * 10 and dz > dy * 10: return "#4444FF" if as_hex else (0.0, 0.0, 1.0) 
        
        return "#FFFFFF" if as_hex else (1.0, 1.0, 1.0) 

    def apply_constraints(self, prev, raw):
        m = self.lock_mode
        if m == 0: return raw
        if m == 1: return FreeCAD.Vector(raw.x, prev.y, prev.z)
        if m == 2: return FreeCAD.Vector(prev.x, raw.y, prev.z)
        if m == 3: return FreeCAD.Vector(prev.x, prev.y, raw.z)
        return raw

    def check_magnetic_snap(self, pos_tuple):
        O = self.view.getPoint(pos_tuple)
        if O is None: return None, None 

        D = self.view.getViewDirection()
        if D.Length > 1e-6: D.normalize()
        else: D = FreeCAD.Vector(0,0,1)

        objects_to_check = []
        for line in self.temp_lines: objects_to_check.append(line)
        for obj in self.doc.Objects:
            if obj.Name.startswith("Smart_Pipe_Route"): objects_to_check.append(obj)

        best_pt = O
        best_dist = 25.0 
        best_obj = None

        for obj in objects_to_check:
            try:
                if getattr(obj, "Shape", None) and obj.Shape:
                    for v in obj.Shape.Vertexes:
                        vec = v.Point - O
                        dist = vec.cross(D).Length 
                        if dist < best_dist and vec.dot(D) > 0: 
                            best_dist = dist
                            best_pt = v.Point
                            best_obj = obj
            except: pass

        if best_obj is None:
            for obj in objects_to_check:
                try:
                    if getattr(obj, "Shape", None) and obj.Shape:
                        for edge in obj.Shape.Edges:
                            pA = edge.valueAt(edge.FirstParameter)
                            pB = edge.valueAt(edge.LastParameter)
                            
                            AB = pB - pA
                            V = O - pA
                            ab_ab = AB.dot(AB)
                            if ab_ab < 1e-6: continue
                            
                            ab_d = AB.dot(D)
                            v_ab = V.dot(AB)
                            v_d = V.dot(D)
                            
                            denom = ab_ab - ab_d * ab_d
                            if denom < 1e-6: t2 = v_ab / ab_ab
                            else: t2 = (v_ab - v_d * ab_d) / denom
                                
                            t2 = max(0.0, min(1.0, t2))
                            closest_on_edge = pA + AB * t2
                            
                            dist = (closest_on_edge - O).cross(D).Length
                            if dist < best_dist:
                                best_dist = dist
                                best_pt = closest_on_edge
                                best_obj = obj
                except: pass
                
        return best_pt, best_obj

    def update_axis_indicator(self, pos):
        if pos is None: return
        placement = FreeCAD.Placement(pos, FreeCAD.Rotation())
        if self.axis_x: self.axis_x.Placement = placement
        if self.axis_y: self.axis_y.Placement = placement
        if self.axis_z: self.axis_z.Placement = placement
        
        if self.axis_x: self.axis_x.ViewObject.LineWidth = 6 if self.lock_mode == 1 else 2
        if self.axis_y: self.axis_y.ViewObject.LineWidth = 6 if self.lock_mode == 2 else 2
        if self.axis_z: self.axis_z.ViewObject.LineWidth = 6 if self.lock_mode == 3 else 2

    def add_segment(self, final_pt):
        if len(self.routing_nodes) > 0:
            p_prev = self.routing_nodes[-1]
            if (final_pt - p_prev).Length < 0.001:
                return 
                
        self.routing_nodes.append(final_pt)
        if len(self.routing_nodes) >= 2:
            p_prev = self.routing_nodes[-2]
            vec = final_pt - p_prev
            
            seg = self.doc.addObject("Part::Feature", f"RouteSeg_{len(self.routing_nodes)}")
            seg.Shape = Part.LineSegment(p_prev, final_pt).toShape()
            seg.ViewObject.Visibility = False 
            self.temp_lines.append(seg)
            
            ghost = self.doc.addObject("Part::Feature", f"RouteGhost_{len(self.routing_nodes)}")
            try:
                ghost.Shape = Part.makeCylinder(self.visual_radius, vec.Length, p_prev, vec)
                ghost.ViewObject.ShapeColor = self.get_dynamic_color(vec)
                ghost.ViewObject.LineColor = self.get_dynamic_color(vec)
                ghost.ViewObject.Transparency = 50 
            except: pass
            self.temp_ghosts.append(ghost)
            
            dim = self.doc.addObject("App::Annotation", f"SegDim_{len(self.routing_nodes)}")
            dim.Label = f"{vec.Length:.1f} mm"
            dim.Position = p_prev + vec * 0.5
            dim.ViewObject.FontSize = 14
            dim.ViewObject.TextColor = self.get_dynamic_color(vec)
            self.temp_labels.append(dim)
            
            self.doc.recompute()

    def move_observer(self, info):
        raw = self.view.getPoint(info["Position"])
        if raw is None: return 

        if not self.routing_nodes:
            snap_raw, _ = self.check_magnetic_snap(info["Position"])
            if snap_raw: raw = snap_raw
            self.update_axis_indicator(raw)
            if getattr(self, "preview_line", None): self.preview_line.ViewObject.Visibility = False
            
            if self.hud:
                hex_color = self.get_dynamic_color(as_hex=True)
                self.hud.mode_lbl.setStyleSheet(f"color: {hex_color}; font-weight: bold; border: none; background: transparent;")
                self.hud.mode_lbl.setText(f"[{self.get_mode_name()}]")
                
                self.hud.len_input.hide()
                self.hud.unit_lbl.hide()
                self.hud.ang_input.hide()
                self.hud.deg_lbl.setText("°")
                
                mouse_pos = QtGui.QCursor.pos()
                self.hud.move(mouse_pos.x() + 25, mouse_pos.y() + 25)
                self.hud.show()
            return
            
        if self.hud:
            self.hud.len_input.show()
            self.hud.unit_lbl.show()
            self.hud.ang_input.show()
            self.hud.deg_lbl.show()
            
        if self.lock_mode == 0:
            snap_raw, _ = self.check_magnetic_snap(info["Position"])
            if snap_raw: raw = snap_raw
            
        indicator_pos = self.apply_constraints(self.routing_nodes[-1], raw)
        self.update_axis_indicator(indicator_pos)

        prev = self.routing_nodes[-1]
        raw_vec = raw - prev
        if raw_vec.Length > 0.001:
            self.raw_dir = raw_vec.normalize()
            
        final = self.apply_constraints(prev, raw)

        try:
            vec = final - prev
            dist = vec.Length
            
            if dist > 0.001: 
                self.current_dir = vec.normalize() 
            
            if self.lock_mode == 0:
                if abs(vec.z) > abs(vec.x) and abs(vec.z) > abs(vec.y): angle = 90.0 if vec.z > 0 else -90.0
                else: angle = math.degrees(math.atan2(vec.y, vec.x))
            else:
                if getattr(self, "raw_dir", None) and getattr(self, "current_dir", None):
                    A = self.current_dir
                    raw_d = self.raw_dir
                    wp = self.working_plane
                    
                    if wp == 'XY':
                        if self.lock_mode == 1: P = FreeCAD.Vector(0, 1 if raw_d.y >= 0 else -1, 0)
                        elif self.lock_mode == 2: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                        elif self.lock_mode == 3: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                    elif wp == 'XZ':
                        if self.lock_mode == 1: P = FreeCAD.Vector(0, 0, 1 if raw_d.z >= 0 else -1)
                        elif self.lock_mode == 2: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                        elif self.lock_mode == 3: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                    elif wp == 'YZ':
                        if self.lock_mode == 1: P = FreeCAD.Vector(0, 1 if raw_d.y >= 0 else -1, 0)
                        elif self.lock_mode == 2: P = FreeCAD.Vector(0, 0, 1 if raw_d.z >= 0 else -1)
                        elif self.lock_mode == 3: P = FreeCAD.Vector(0, 1 if raw_d.y >= 0 else -1, 0)
                        
                    proj_A = raw_d.dot(A)
                    proj_P = raw_d.dot(P)
                    angle = math.degrees(math.atan2(abs(proj_P), abs(proj_A))) if abs(proj_A) > 1e-6 else 90.0
                else: angle = 0.0

            if self.input_mode:
                text_len = self.hud.len_input.text().strip()
                text_ang = self.hud.ang_input.text().strip()
                
                if text_len and self.hud.len_input.isModified():
                    try: dist = float(text_len)
                    except ValueError: pass
                else:
                    if not self.hud.len_input.hasFocus():
                        self.hud.len_input.setText(f"{dist:.2f}")

                if text_ang and self.hud.ang_input.isModified():
                    try: 
                        angle = float(text_ang)
                        rad = math.radians(angle)
                        
                        if self.lock_mode == 0:
                            if getattr(self, "current_dir", None):
                                xy_length = math.hypot(self.current_dir.x, self.current_dir.y)
                                if xy_length > 1e-6:
                                    new_dir = FreeCAD.Vector(xy_length * math.cos(rad), xy_length * math.sin(rad), self.current_dir.z).normalize()
                                else:
                                    new_dir = FreeCAD.Vector(math.cos(rad), math.sin(rad), 0)
                                self.current_dir = new_dir
                        else:
                            if getattr(self, "current_dir", None) and getattr(self, "raw_dir", None):
                                A = self.current_dir
                                raw_d = self.raw_dir
                                wp = self.working_plane
                                
                                if wp == 'XY':
                                    if self.lock_mode == 1: P = FreeCAD.Vector(0, 1 if raw_d.y >= 0 else -1, 0)
                                    elif self.lock_mode == 2: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                                    elif self.lock_mode == 3: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                                elif wp == 'XZ':
                                    if self.lock_mode == 1: P = FreeCAD.Vector(0, 0, 1 if raw_d.z >= 0 else -1)
                                    elif self.lock_mode == 2: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                                    elif self.lock_mode == 3: P = FreeCAD.Vector(1 if raw_d.x >= 0 else -1, 0, 0)
                                elif wp == 'YZ':
                                    if self.lock_mode == 1: P = FreeCAD.Vector(0, 1 if raw_d.y >= 0 else -1, 0)
                                    elif self.lock_mode == 2: P = FreeCAD.Vector(0, 0, 1 if raw_d.z >= 0 else -1)
                                    elif self.lock_mode == 3: P = FreeCAD.Vector(0, 1 if raw_d.y >= 0 else -1, 0)
                                
                                self.current_dir = A * math.cos(rad) + P * math.sin(rad)
                    except Exception: pass
                else:
                    if not self.hud.ang_input.hasFocus():
                        self.hud.ang_input.setText(f"{angle:.2f}")
                
                if getattr(self, "current_dir", None):
                    final = prev + self.current_dir * dist
                    vec = final - prev
                    
            else:
                if self.hud:
                    self.hud.len_input.setText(f"{dist:.2f}")
                    self.hud.ang_input.setText(f"{angle:.2f}")

            # --- Live 3D Cylinder Preview ---
            if dist > 0.001:
                if getattr(self, "preview_line", None):
                    try:
                        self.preview_line.Shape = Part.makeCylinder(self.visual_radius, dist, prev, vec)
                        self.preview_line.ViewObject.ShapeColor = self.get_dynamic_color(vec)
                        self.preview_line.ViewObject.LineColor = self.get_dynamic_color(vec)
                        self.preview_line.ViewObject.Visibility = True
                    except: pass
            else:
                if getattr(self, "preview_line", None):
                    self.preview_line.ViewObject.Visibility = False
            
            if self.hud:
                hex_color = self.get_dynamic_color(vec, as_hex=True)
                self.hud.mode_lbl.setStyleSheet(f"color: {hex_color}; font-weight: bold; border: none; background: transparent;")
                self.hud.mode_lbl.setText(f"[{self.get_mode_name()}]")
                self.hud.deg_lbl.setText("°")
                
                mouse_pos = QtGui.QCursor.pos()
                self.hud.move(mouse_pos.x() + 25, mouse_pos.y() + 25)
                if dist > 0: self.hud.show()
        except Exception: pass

    def finish_route(self):
        if not getattr(self, "is_tool_active", False): return
        self.is_tool_active = False 

        # Gather specifications from the Task Panel UI before closing it
        od = self.task_panel.outer_input.value()
        thick = self.task_panel.thick_input.value()
        pipe_color = self.task_panel.get_selected_color()
        pipe_type = self.task_panel.get_pipe_type()

        id_val = od - (2 * thick)
        
        # We collect the INVISIBLE centerlines
        temp_edges = [l.Shape for l in self.temp_lines] if self.temp_lines else []
        self.remove_scene_objects() # Nukes all the 3D ghosts!
        
        try: FreeCADGui.Control.closeDialog()
        except: pass

        if id_val <= 0:
            QtWidgets.QMessageBox.critical(None, "Error", "Wall thickness is too large for this pipe diameter.")
            return
        
        if temp_edges:
            # 1. Compile the centerlines into a compound
            if self.target_route and getattr(self.target_route, "Name", None) and self.doc.getObject(self.target_route.Name):
                existing_edges = self.target_route.Shape.Edges
                self.target_route.Shape = Part.Compound(existing_edges + temp_edges)
                route_obj = self.target_route
            else:
                route_obj = self.doc.addObject("Part::Feature", "Smart_Pipe_Route")
                route_obj.Shape = Part.Compound(temp_edges)
                
            self.doc.recompute()
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(self.doc.Name, route_obj.Name)

            # 2. Directly Generate the Pipe Network based on panel data
            self.generate_network(route_obj, od, id_val, pipe_color, pipe_type)

    def generate_network(self, route_obj, od, id_val, pipe_color, pipe_type):
        try:
            outer_shapes, inner_shapes = [], []
            valid_edges = [edge for edge in route_obj.Shape.Edges if edge.Length > ComfacUtils.TOLERANCE]

            if not valid_edges:
                return

            endpoints = []
            for edge in valid_edges:
                try:
                    endpoints.append(edge.Vertexes[0].Point)
                    endpoints.append(edge.Vertexes[-1].Point)
                except:
                    endpoints.append(edge.valueAt(edge.FirstParameter))
                    endpoints.append(edge.valueAt(edge.LastParameter))

            intersection_points = []
            MATCH_TOLERANCE = 0.5 
            
            for pt in endpoints:
                already_found = False
                for ipt in intersection_points:
                    if (pt - ipt).Length < MATCH_TOLERANCE:
                        already_found = True
                        break
                
                if not already_found:
                    count = sum(1 for p in endpoints if (pt - p).Length < MATCH_TOLERANCE)
                    if count > 1: intersection_points.append(pt)

            for edge in valid_edges:
                start_pt = edge.valueAt(edge.FirstParameter)
                tangent = edge.tangentAt(edge.FirstParameter)
                circ_out = Part.Circle(start_pt, tangent, od/2.0).toShape()
                outer_shapes.append(Part.Wire([edge]).makePipeShell([Part.Wire([circ_out])], True, True))
                circ_in = Part.Circle(start_pt, tangent, id_val/2.0).toShape()
                inner_shapes.append(Part.Wire([edge]).makePipeShell([Part.Wire([circ_in])], True, True))

            for pt in intersection_points:
                outer_shapes.append(Part.makeSphere(od/2.0, pt))
                inner_shapes.append(Part.makeSphere(id_val/2.0, pt))

            if not outer_shapes: 
                QtWidgets.QMessageBox.warning(None, "Error", "Failed to generate any 3D shapes.")
                return

            master_outer = ComfacUtils.fuse_shapes(outer_shapes)
            master_inner = ComfacUtils.fuse_shapes(inner_shapes)
            
            try:
                final_shape = master_outer.cut(master_inner).removeSplitter()
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Boolean Cut Error", f"FreeCAD failed to hollow out the pipes!\n\nDetails: {e}")
                return

            self.doc.openTransaction("Generate Pipe Network")
            try:
                container, is_body = ComfacUtils.get_container(self.doc, route_obj)
                obj = self.doc.addObject("Part::Feature", "Pipe_Network")
                obj.Shape = final_shape
                
                if container and not is_body: container.addObject(obj)

                ComfacUtils.add_common_properties(obj, route_obj, {"PipeOuter": od, "PipeInner": id_val, "PipeType": pipe_type})
                if hasattr(obj, "Refine"): obj.Refine = True
                
                # Ensure pipe_color is a tuple
                if isinstance(pipe_color, list):
                    pipe_color = tuple(pipe_color)
                
                obj.ViewObject.ShapeColor = pipe_color
                
                if "PVC" in pipe_type:
                    pvc_color_map = {
                        "Water (Blue)": (0.2, 0.4, 0.8),
                        "Electrical (Orange)": (0.9, 0.5, 0.1),
                        "Mechanical (Silver)": (0.7, 0.7, 0.7)
                    }
                    pvc_selection = self.task_panel.color_cb.currentText()
                    if pvc_selection in pvc_color_map:
                        obj.addProperty("App::PropertyColor", "PipeColor", "PipeData")
                        obj.PipeColor = pvc_color_map[pvc_selection]
                        
                route_obj.ViewObject.hide()

                self.doc.recompute()
                self.doc.commitTransaction()

                # --- AUTO-LAUNCH FITTINGS & CLEANUP ---
                def launch_silent_fittings():
                    try:
                        fittings_panel = PFittings.PipeFittingTaskPanel(obj)
                        
                        # Use safely calculated values, no UI references needed here!
                        fit_thick = (od - id_val) / 2.0
                        sock_len = fittings_panel.length_input.value()
                        fit_id = fittings_panel.pipe_od
                        fit_od = fittings_panel.pipe_od + (2 * fit_thick)
                        
                        # Generate actual fittings
                        fittings_panel.generate_fittings(fit_od, fit_id, sock_len)
                        
                        # Attempt native clearing
                        if hasattr(fittings_panel, 'preview'): 
                            fittings_panel.preview.clear()
                            
                        # Safely delete any leftover preview ghosts without deleting the fittings
                        for doc_obj in FreeCAD.ActiveDocument.Objects:
                            name_lower = doc_obj.Name.lower()
                            label_lower = doc_obj.Label.lower()
                            
                            if "preview" in name_lower or "preview" in label_lower:
                                if "network" not in name_lower and "network" not in label_lower:
                                    try: 
                                        FreeCAD.ActiveDocument.removeObject(doc_obj.Name)
                                    except Exception: 
                                        pass
                                        
                        FreeCAD.ActiveDocument.recompute()
                    except Exception as e:
                        FreeCAD.Console.PrintWarning(f"Silent auto-fittings failed: {e}\n")

                QtCore.QTimer.singleShot(50, launch_silent_fittings)

            except Exception as e:
                self.doc.abortTransaction()
                QtWidgets.QMessageBox.critical(None, "Feature Creation Error", f"Failed building the final object:\n{e}")

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Fatal Crash", f"The generation script crashed completely:\n{str(e)}")

    def cancel_route(self):
        if not getattr(self, "is_tool_active", False): return
        self.is_tool_active = False 
        
        self.remove_scene_objects()
        try: FreeCADGui.Control.closeDialog()
        except: pass

    def remove_scene_objects(self):
        try:
            if getattr(self, "mouse_id", None): self.view.removeEventCallback("SoMouseButtonEvent", self.mouse_id)
            if getattr(self, "move_id", None): self.view.removeEventCallback("SoLocation2Event", self.move_id)
            if getattr(self, "key_filter", None): QtWidgets.QApplication.instance().removeEventFilter(self.key_filter)
        except: pass

        if getattr(self, "hud", None):
            self.hud.close()
            self.hud.deleteLater()
            self.hud = None

        if getattr(self, "temp_lines", None):
            for line in self.temp_lines:
                try:
                    if getattr(line, "Name", None) and self.doc.getObject(line.Name): self.doc.removeObject(line.Name)
                except ReferenceError: pass
            self.temp_lines = [] 
            
        if getattr(self, "temp_ghosts", None):
            for ghost in self.temp_ghosts:
                try:
                    if getattr(ghost, "Name", None) and self.doc.getObject(ghost.Name): self.doc.removeObject(ghost.Name)
                except ReferenceError: pass
            self.temp_ghosts = [] 
            
        if hasattr(self, "temp_labels"):
            for lbl in self.temp_labels:
                try:
                    if getattr(lbl, "Name", None) and self.doc.getObject(lbl.Name): self.doc.removeObject(lbl.Name)
                except ReferenceError: pass
            self.temp_labels = []

        for obj_attr in ["preview_line", "axis_x", "axis_y", "axis_z"]:
            obj = getattr(self, obj_attr, None)
            try:
                if obj and getattr(obj, "Name", None) and self.doc.getObject(obj.Name): 
                    self.doc.removeObject(obj.Name)
            except ReferenceError: pass
            
        self.doc.recompute()

    def click_observer(self, info):
        if info["State"] != "DOWN" or self.input_mode: return
        btn = info["Button"]

        if btn == "BUTTON3": 
            self.finish_route()
            return

        if btn == "BUTTON1": 
            raw = self.view.getPoint(info["Position"])
            if raw is None: return
            
            snapped_obj = None
            if self.lock_mode == 0 or len(self.routing_nodes) == 0:
                snap_raw, snapped_obj = self.check_magnetic_snap(info["Position"]) 
                if snap_raw: raw = snap_raw
                
            prev = self.routing_nodes[-1] if self.routing_nodes else None
            final = self.apply_constraints(prev, raw) if prev else raw
            
            if len(self.routing_nodes) == 0 and snapped_obj:
                if snapped_obj.Name.startswith("Smart_Pipe_Route"):
                    self.target_route = snapped_obj
                    FreeCAD.Console.PrintMessage(f"Branching off existing route: {snapped_obj.Name}\n")
            
            self.add_segment(final)

    def force_viewport_focus(self):
        v = FreeCADGui.ActiveDocument.ActiveView
        if v and hasattr(v, "getGLWidget"): 
            gl_widget = v.getGLWidget()
            gl_widget.setFocus()
            gl_widget.activateWindow()
            
        mw = FreeCADGui.getMainWindow()
        if mw: mw.activateWindow()

    def prompt_cancel(self):
        reply = QtWidgets.QMessageBox.question(
            FreeCADGui.getMainWindow(), "Cancel Routing?",
            "Are you sure you want to cancel and discard the current route?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes: self.cancel_route()
        else: QtCore.QTimer.singleShot(10, self.force_viewport_focus)


# =========================================================
# REGISTER COMMAND IN FREECAD
# =========================================================
FreeCADGui.addCommand('PipeRouter', PipeRouterCommand())