#****************************************************************************
#*                                                                          *
#*   Comfac MEP Workbench:                                                  *
#*       Procedural MEP tools for FreeCAD                                   *
#*       Forked from Dodo / Flamingo tools (Riccardo Treu, LGPL)            *
#*   Copyright (c) 2024 Comfac Global Group                                 *
#*                                                                          *
#*   This program is free software; you can redistribute it and/or modify   *
#*   it under the terms of the GNU Lesser General Public License (LGPL)     *
#*   as published by the Free Software Foundation; either version 2 of      *
#*   the License, or (at your option) any later version.                    *
#*   for detail see the LICENCE text file.                                  *
#*                                                                          *
#*   This program is distributed in the hope that it will be useful,        *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of         *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          *
#*   GNU Library General Public License for more details.                   *
#*                                                                          *
#*   You should have received a copy of the GNU Library General Public      *
#*   License along with this program; if not, write to the Free Software    *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307   *
#*   USA                                                                    *
#*                                                                          *
#****************************************************************************

import os, sys

# Add mep/ subpackage to path so Comfac internal imports resolve
_mep_path = os.path.join(os.path.dirname(__file__), 'mep')
if _mep_path not in sys.path:
    sys.path.insert(0, _mep_path)

class dodo ( Workbench ):
  try:
      import DraftSnap
  except Exception:
      import draftguitools.gui_snapper as DraftSnap
      print('flag') # patch
  if not hasattr(FreeCADGui, "Snapper"):
      FreeCADGui.Snapper = DraftSnap.Snapper()
      print('flag2') # patch

  import sys, FreeCAD
  v=sys.version_info[0]
  if v<3: FreeCAD.Console.PrintWarning('Dodo is written for Py3 and Qt5\n You may experience mis-behaviuors\n')
  Icon = '''
/* XPM */
static char * dodo1_xpm[] = {
"98 98 2 1",
" 	c None",
".	c #000000",
"                                                                                                  ",
"                                                                                                  ",
"                                                                                                  ",
"                                                                                                  ",
"                                                                                                  ",
"                                                                                                  ",
"                                                                                                  ",
"                                                                  ....                            ",
"                                                               ........                           ",
"                                                             ...........                          ",
"                                                           .............                          ",
"                                                          ...............                         ",
"                                                         .................                        ",
"                                                        .....................                     ",
"                                                       .........................                  ",
"                                                       .............................              ",
"                                                      ................................            ",
"                                                      ................................            ",
"                                                      .................................           ",
"                                                      ..................................          ",
"                                                      ..................................          ",
"                                                      ..................................          ",
"                                                      ..................................          ",
"                                                      ..................................          ",
"                                                       .................................          ",
"                                                       ..........         ..............          ",
"                 ......                                 .........           ........              ",
"            ............                                ..........           ......               ",
"          ................                              ..........                                ",
"         .................                               ..........                               ",
"         .................          .......               ..........                              ",
"        ..................     .................          ...........                             ",
"        ..................   .....................         ...........                            ",
"        ...........................................        ............                           ",
"        .............................................       .............                         ",
"        ..............................................       .............                        ",
"       ................................................      ..............                       ",
"       .................................................     ...............                      ",
"      .................................................... .................                      ",
"      .......................................................................                     ",
"       ......................................................................                     ",
"          ....................................................................                    ",
"              ................................................................                    ",
"               ...............................................................                    ",
"               ................................................................                   ",
"               ................................................................                   ",
"              ................................................................                    ",
"              ................................................................                    ",
"             .................................................................                    ",
"            ..................................................................                    ",
"            .................................................................                     ",
"           ..................................................................                     ",
"           ..................................................................                     ",
"          ..................................................................                      ",
"         ...................................................................                      ",
"         ...................................................................                      ",
"         ...................................................................                      ",
"           ................................................................                       ",
"            ...............................................................                       ",
"            ..............................................................                        ",
"             .............................................................                        ",
"              ............................................................                        ",
"               ..........................................................                         ",
"                .........................................................                         ",
"                 .......................................................                          ",
"                 ......................................................                           ",
"                   ...................................................                            ",
"                    ..................................................                            ",
"                     ...............................................                              ",
"                      .............................................                               ",
"                        ..........................................                                ",
"                         ........................................                                 ",
"                           ....................................                                   ",
"                            ................................                                      ",
"                             ............................                                         ",
"                             .........................                                            ",
"                              ....................                                                ",
"                              ....   ............                                                 ",
"                              ...            ...      ..                                          ",
"                              ...            ...    ....                                          ",
"                              ...            ................                                     ",
"                              ...       .... .................                                    ",
"                              ...        ..................                                       ",
"                              ...      ..   ........                                              ",
"                              ...    ....      .....                                              ",
"                        ....  ..........         .......                                          ",
"                          ...................        ....                                         ",
"                           ..................           .                                         ",
"                               .... .......                                                       ",
"                                ......                                                            ",
"                                 ......                                                           ",
"                                    .....                                                         ",
"                                       ..                                                         ",
"                                                                                                  ",
"                                                                                                  ",
"                                                                                                  ",
"                                                                                                  ",
"                                                                                                  ",
"                                                                                                  "};
'''
  MenuText = "Comfac MEP Workbench"
  ToolTip = "Procedural MEP tools for FreeCAD: pipes, ducts, cables, frames"
  def Initialize(self):
    import CUtils
    self.utilsList=["selectSolids","queryModel","moveWorkPlane","offsetWorkPlane","rotateWorkPlane","hackedL","moveHandle","dpCalc"]
    self.appendToolbar("Utils",self.utilsList)
    Log ('Loading Utils: done\n')
    import CFrame
    self.frameList=["frameIt","FrameBranchManager","insertSection","spinSect","reverseBeam","shiftBeam","pivotBeam","levelBeam","alignEdge","rotJoin","alignFlange","stretchBeam","extend","adjustFrameAngle","insertPath"]
    self.appendToolbar("frameTools",self.frameList)
    Log ('Loading Frame tools: done\n')
    import CPipe
    self.pypeList=["insertPipe","insertElbow","insertReduct","insertCap","insertValve","insertFlange","insertUbolt","insertPypeLine","insertBranch","insertTank","insertRoute","breakPipe","mateEdges","flat","extend2intersection","extend1intersection","makeHeader","laydown","raiseup","attach2tube","point2point","insertAnyz"]
    from dodoPM import toolList
    self.qm=toolList
    self.appendToolbar("pipeTools",self.pypeList)
    Log ('Loading Pipe tools: done\n')

    # --- Comfac MEP Tools (lazy import registers commands) ---
    try:
      import misc_tools.CreateNewSketch, misc_tools.CreateNewPartBody, misc_tools.BillOfMaterials
      import Pipes.CreateNetworkPipe, Pipes.CreateSolidPipeNetwork, Pipes.CreateNetworkPipeInsulation
      import Pipes.CreateNetworkPipeFittings, Pipes.PipeRouter, Pipes.CreateDetailedFMC
      import Pipes.CreateDetailedLFMC, Pipes.CreatePipeLibraries, Pipes.CreatePipeSaddle
      import Pipes.CreatePipeHanger, Pipes.CreateFlexConduit, Pipes.CreatePipeLocknut
      import Ducts.CreateNetworkDuct, Ducts.CreateSolidDuct, Ducts.CreateNetworkDuctInsulation
      import Ducts.CreateDuctFittings, Ducts.CreateDuctHangers, Ducts.CreateDuctFastener
      import Ducts.CreateDuctScrews, Ducts.DuctLibrary
      import Sheets.CreatePerforatedSheet, Sheets.CreateCorrugatedSheet
      import Cables.CreateWireGutter, Cables.CreateCableLadderFittings
      import Cables.CreateFiberTray, Cables.CreateDetailedCableTray
      import misc_tools.CreateTransitionReducer, misc_tools.MergeHollowNetworks
      import misc_tools.StepImporter, misc_tools.ImportFile
      Log ('Loading Comfac MEP tools: done\n')
    except Exception as e:
      FreeCAD.Console.PrintWarning('Failed to load Comfac MEP tools: '+str(e)+'\n')

    self.list_drafts = ["Custom_NewSketch", "Custom_NewPartBody", "PipeRouter"]
    self.list_pipes_mep = ["CreateNetworkPipe", "Create_Solid_Pipe", "CreateNetworkPipeInsulation", "CreateNetworkPipeFittings", "CreateFlexConduit", "CreateDetailedFMC", "CreateDetailedLFMC", "CreatePipeHanger", "CreatePipeSaddle", "CreatePipeLibraries"]
    self.list_ducts = ["CreateNetworkDuct", "Create_Solid_Duct", "CreateNetworkDuctInsulation", "CreateDuctFittings", "CreateDuctHangers", "CreateDuctFastener", "CreateDuctScrews", "DuctLibrary"]
    self.list_extra = ["Create_Transition", "Merge_Networks"]
    self.list_sheets = ["CreatePerforatedSheet", "CreateCorrugatedSheet"]
    self.list_cables = ["CreateWireGutter", "CreateCableLadderFittings", "CreateDetailedCableTray", "CreateFiberTray"]
    self.list_mep_utils = ["StepImporter", "ImportFile", "BillOfMaterials"]

    self.appendToolbar("MEP Draft", self.list_drafts)
    self.appendToolbar("MEP Pipes", self.list_pipes_mep)
    self.appendToolbar("MEP Ducts", self.list_ducts)
    self.appendToolbar("MEP Extra", self.list_extra)
    self.appendToolbar("MEP Sheets", self.list_sheets)
    self.appendToolbar("MEP Cables", self.list_cables)
    self.appendToolbar("MEP Utils", self.list_mep_utils)

    self.appendMenu(["Frame tools"],self.frameList)
    self.appendMenu(["Pype tools"],self.pypeList)
    self.appendMenu(["Utils"],self.utilsList)
    self.appendMenu(["QkMenus"], self.qm)
    self.appendMenu(["MEP Draft"], self.list_drafts)
    self.appendMenu(["MEP Pipes"], self.list_pipes_mep)
    self.appendMenu(["MEP Ducts"], self.list_ducts)
    self.appendMenu(["MEP Sheets"], self.list_sheets)
    self.appendMenu(["MEP Cables"], self.list_cables)
    self.appendMenu(["MEP Utils"], self.list_mep_utils)

  def ContextMenu(self, recipient):
    self.appendContextMenu('Frames', self.frameList)
    self.appendContextMenu('Pypes', self.pypeList)
    self.appendContextMenu('Utils', self.utilsList)
    self.appendContextMenu('MEP Pipes', self.list_pipes_mep)
    self.appendContextMenu('MEP Ducts', self.list_ducts)

  def Activated(self):
    FreeCAD.__activePypeLine__=None
    FreeCAD.__activeFrameLine__=None
    Msg("Created variables in FreeCAD module:\n")
    Msg("__activePypeLine__\n")
    Msg("__activeFrameLine__\n")
    try:
      import dodoPM
      Msg("__dodoPMact__ \n")
      FreeCAD.Console.PrintMessage(FreeCAD.__dodoPMact__.objectName()+' \'s shortcut = '+FreeCAD.__dodoPMact__.shortcuts()[0].toString()+'\n\t****\n')
    except:
      FreeCAD.Console.PrintError('dodoPM not loaded \n')

  def Deactivated(self):
    del FreeCAD.__activePypeLine__
    Msg("__activePypeLine__ variable deleted\n")
    del FreeCAD.__activeFrameLine__
    Msg("__activeFrameLine__ variable deleted\n")

Gui.addWorkbench(dodo)
