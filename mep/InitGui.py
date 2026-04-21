import FreeCADGui

class ComfacToolsWorkbench(FreeCADGui.Workbench):
    import ComfacUtils as utils

    MenuText = "Comfac MEP Tools"
    ToolTip = "Custom tools for Pipe and Duct Generation"
    Icon = utils.get_icon_path('Workbench_ComfacMEP.svg')

    def Initialize(self):
        import misc_tools.CreateNewSketch, misc_tools.CreateNewPartBody, misc_tools.BillOfMaterials
        import Pipes.CreateNetworkPipe, Pipes.CreateSolidPipeNetwork, Pipes.CreateNetworkPipeInsulation, Pipes.CreateNetworkPipeFittings, Pipes.PipeRouter,Pipes.CreateDetailedFMC,Pipes.CreateDetailedLFMC,Pipes.CreatePipeLibraries
        import Ducts.CreateNetworkDuct, Ducts.CreateSolidDuct, Ducts.CreateNetworkDuctInsulation, Ducts.CreateDuctFittings,Ducts.CreateDuctHangers,Ducts.CreateDuctScrews, Ducts.CreateDuctFastener, Ducts.DuctLibrary
        import misc_tools.CreateTransitionReducer, misc_tools.MergeHollowNetworks,misc_tools.StepImporter, misc_tools.ImportFile
        import Sheets.CreatePerforatedSheet, Sheets.CreateCorrugatedSheet
        import Cables.CreateWireGutter, Cables.CreateCableLadderFittings,Cables.CreateFiberTray,Cables.CreateDetailedCableTray
        import Pipes.CreatePipeSaddle, Pipes.CreatePipeHanger, Pipes.CreateFlexConduit, Pipes.CreatePipeLocknut

        self.list_drafts = ["Custom_NewSketch", "Custom_NewPartBody","PipeRouter"]
        self.list_pipes = ["CreateNetworkPipe", "Create_Solid_Pipe", "CreateNetworkPipeInsulation", "CreateNetworkPipeFittings","CreateFlexConduit","CreateDetailedFMC","CreateDetailedLFMC","CreatePipeHanger", "CreatePipeSaddle","CreatePipeLibraries"]
        self.list_ducts = ["CreateNetworkDuct", "Create_Solid_Duct", "CreateNetworkDuctInsulation", "CreateDuctFittings","CreateDuctHangers","CreateDuctFastener","CreateDuctScrews", "DuctLibrary"]
        self.list_extra = ["Create_Transition", "Merge_Networks"]
        self.list_sheets = ["CreatePerforatedSheet", "CreateCorrugatedSheet"]
        self.list_cables = ["CreateWireGutter","CreateCableLadderFittings","CreateDetailedCableTray","CreateFiberTray"]
        self.list_utilities = ["StepImporter", "ImportFile"]

        self.appendToolbar("Draft Tool", self.list_drafts)
        self.appendToolbar("Pipe Tools", self.list_pipes)
        self.appendToolbar("Duct Tools", self.list_ducts)
        self.appendToolbar("Extra Tools", self.list_extra)
        self.appendToolbar("Sheets", self.list_sheets)
        self.appendToolbar("Cable Tools", self.list_cables)
        self.appendToolbar("Acessory Tools", self.list_utilities)

    def GetClassName(self):
        return "Gui::PythonWorkbench"

FreeCADGui.addWorkbench(ComfacToolsWorkbench())
