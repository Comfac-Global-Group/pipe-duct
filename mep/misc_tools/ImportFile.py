import FreeCAD as App
import FreeCADGui as Gui
import os
import re

from compat import QtWidgets, QtCore, QtGui
QFileDialog = QtWidgets.QFileDialog

# --- Helper Functions ---
# Kept outside the class to act as standard utilities

def extract_mtext_properties(text_input):
    props = {}
    if not isinstance(text_input, str): return props
        
    font_match = re.search(r'\\f([^|;]+)', text_input)
    if font_match: props['font'] = font_match.group(1)
    
    bold_match = re.search(r'\|b([01])', text_input)
    if bold_match: props['bold'] = (bold_match.group(1) == '1')
        
    italic_match = re.search(r'\|i([01])', text_input)
    if italic_match: props['italic'] = (italic_match.group(1) == '1')
        
    height_match = re.search(r'\\H([0-9.]+)(x?)[^;]*;', text_input)
    if height_match: 
        try:
            val = float(height_match.group(1))
            is_multiplier = (height_match.group(2) == 'x')
            if is_multiplier: props['height_multiplier'] = val
            else: props['height'] = val
        except ValueError:
            pass

    align_match = re.search(r'\\[pP]?[xX]?[qQ]([lrcLRC])', text_input)
    if align_match:
        align_char = align_match.group(1).lower()
        if align_char == 'c': props['justification'] = 'Center'
        elif align_char == 'r': props['justification'] = 'Right'
        elif align_char == 'l': props['justification'] = 'Left'
            
    return props

def clean_mtext_formatting(text_input):
    if not isinstance(text_input, str): return text_input
    cleaned = re.sub(r'\\+[^;]+;', '', text_input)
    cleaned = cleaned.replace('{', '').replace('}', '')
    return cleaned.strip()


# --- The FreeCAD Command Class ---

class ImportCADWithTextCommand:
    """
    This class defines the FreeCAD command for importing CAD files
    and preserving text formatting.
    """
    
    def GetResources(self):
        """
        Sets the icon, menu text, and tooltip for the workbench UI.
        """
        return {
            'Pixmap': 'Std_Import', # You can replace this with a path to a custom .svg icon
            'MenuText': 'Import CAD with Text',
            'ToolTip': 'Imports DXF/DWG/SKP files and cleans up AutoCAD MTEXT formatting.'
        }

    def Activated(self):
        """
        This method executes when the user clicks the toolbar button.
        It contains your main execution logic.
        """
        main_window = Gui.getMainWindow()
        filepath, _ = QFileDialog.getOpenFileName(
            main_window, "Select CAD File", "", "CAD Files (*.dxf *.dwg *.skp)"
        )

        if not filepath:
            App.Console.PrintMessage("Import cancelled.\n")
            return

        App.Console.PrintMessage(f"Starting import for: {filepath}...\n")
        Gui.updateGui()

        doc = App.ActiveDocument
        if doc is None: doc = App.newDocument("Imported_Layout")

        file_ext = os.path.splitext(filepath)[1].lower()

        # ==========================================
        # ONLY Override Preferences for DXF/DWG files
        # ==========================================
        if file_ext in ['.dxf', '.dwg']:
            prefs_import = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Import")
            prefs_draft = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Draft")
            
            for prefs in [prefs_import, prefs_draft]:
                prefs.SetBool("dxftext", True)
                prefs.SetBool("ImportTextsAndDimensions", True) 
                prefs.SetBool("dxfscreentext", False) 
                prefs.SetBool("dxfCreatePart", False) 
                prefs.SetBool("dxfpoints", False)
                prefs.SetBool("ImportPoints", False)
                prefs.SetBool("importPoints", False)
                prefs.SetBool("Points", False)

        # ==========================================
        # IMPORT ROUTING LOGIC
        # ==========================================
        try:
            if file_ext == ".dwg":
                import importDWG
                importDWG.insert(filepath, doc.Name)
            elif file_ext == ".dxf":
                import importDXF
                importDXF.insert(filepath, doc.Name)
            elif file_ext == ".skp":
                try:
                    import importSKP
                    importSKP.insert(filepath, doc.Name)
                except ImportError:
                    App.Console.PrintError("SketchUp Importer not found! Please open the Add-on Manager (Tools > Add-on manager), install the 'SketchUp' plugin, and restart FreeCAD.\n")
                    return
        except Exception as e:
            App.Console.PrintWarning(f"Importer hit a minor error: {e}\n")
            App.Console.PrintWarning("Proceeding to post-processing...\n")

        Gui.updateGui()
        if doc.Objects:
            doc.recompute()

        # ==========================================
        # BYPASS CLEANUP FOR SKETCHUP FILES
        # ==========================================
        if file_ext == ".skp":
            App.Console.PrintMessage("SketchUp file imported successfully. Skipping AutoCAD text cleanup.\n")
            if Gui.ActiveDocument: 
                Gui.SendMsgToActiveView("ViewFit")
            return

        # ==========================================
        # DXF/DWG TEXT CLEANUP LOOP
        # ==========================================
        cleaned_count = 0
        properties_to_check = ["String", "Text", "LabelText", "DisplayText"]
        
        text_objects = [obj for obj in doc.Objects if hasattr(obj, "Proxy") or obj.TypeId.startswith("App::Annotation") or "Draft" in obj.TypeId]
        
        total_objects = len(text_objects)
        if total_objects == 0:
            App.Console.PrintMessage("No text objects found to clean.\n")
            return

        App.Console.PrintMessage(f"Found {total_objects} text objects. Starting cleanup...\n")
        
        doc.openTransaction("Clean MTEXT")
        progress = App.Base.ProgressIndicator()
        progress.start("Cleaning AutoCAD Text...", total_objects)
        
        try:
            for i, obj in enumerate(text_objects):
                progress.next() 
                if i % 100 == 0: Gui.updateGui()

                for prop in properties_to_check:
                    if hasattr(obj, prop):
                        prop_val = getattr(obj, prop)
                        
                        raw_text = ""
                        if isinstance(prop_val, (list, tuple)) and len(prop_val) > 0: raw_text = prop_val[0]
                        elif isinstance(prop_val, str): raw_text = prop_val
                            
                        extracted = extract_mtext_properties(raw_text)
                        
                        if extracted:
                            if 'font' in extracted and hasattr(obj, 'FontName'):
                                base_font = extracted['font']
                                if extracted.get('bold') and extracted.get('italic'): base_font += " Bold Italic"
                                elif extracted.get('bold'): base_font += " Bold"
                                elif extracted.get('italic'): base_font += " Italic"
                                obj.FontName = base_font
                                
                            if hasattr(obj, 'TextSize'):
                                current_size = getattr(obj.TextSize, 'Value', obj.TextSize) if hasattr(obj.TextSize, 'Value') else 10.0
                                if 'height' in extracted: obj.TextSize = extracted['height']
                                elif 'height_multiplier' in extracted: obj.TextSize = current_size * extracted['height_multiplier']
                            
                            if 'justification' in extracted and hasattr(obj, 'Justification'):
                                obj.Justification = extracted['justification']

                        if isinstance(prop_val, (list, tuple)):
                            new_strings = [clean_mtext_formatting(line) for line in prop_val]
                            if list(prop_val) != new_strings: 
                                setattr(obj, prop, new_strings)
                                cleaned_count += 1
                                break 
                        elif isinstance(prop_val, str):
                            new_string = clean_mtext_formatting(prop_val)
                            if prop_val != new_string:
                                setattr(obj, prop, new_string)
                                cleaned_count += 1
                                break
        finally:
            progress.stop()
            doc.commitTransaction()
            App.Console.PrintMessage(f"Successfully cleaned and styled {cleaned_count} text objects.\n")
            doc.recompute()
            if Gui.ActiveDocument: 
                Gui.SendMsgToActiveView("ViewFit")

    def IsActive(self):
        """
        Determines if the button is clickable in the UI. 
        True means it's always available.
        """
        return True

# Register the command to FreeCAD's internal command dictionary
Gui.addCommand('ImportFile', ImportCADWithTextCommand())