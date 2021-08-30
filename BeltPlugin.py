# Copyright (c) 2017 fieldOfView
# This plugin is released under the terms of the LGPLv3 or higher.

from UM.Extension import Extension
from UM.Application import Application
from UM.PluginRegistry import PluginRegistry
from UM.Settings.ContainerRegistry import ContainerRegistry
from UM.Settings.SettingFunction import SettingFunction
from UM.Logger import Logger
from UM.Version import Version

from cura.Settings.CuraContainerStack import _ContainerIndexes as ContainerIndexes
from UM.i18n import i18nCatalog
#from UM.FlameProfiler import pyqtSlot

from PyQt5.QtCore import QObject, QUrl, pyqtProperty, pyqtSignal, pyqtSlot



from . import BeltDecorator

from . import CuraApplicationPatches
from . import PatchedCuraActions
from . import BuildVolumePatches
from . import CuraEngineBackendPatches
from . import FlavorParserPatches

from UM.Backend.Backend import BackendState

from PyQt5.QtQml import qmlRegisterSingletonType

import math
import os.path
import re
import json

from UM.Resources import Resources
Resources.addSearchPath(
    os.path.join(os.path.abspath(
        os.path.dirname(__file__))))  # Plugin translation file import

i18n_catalog = i18nCatalog("belt_printer_slicing")

class BeltPlugin(QObject,Extension):
    def __init__(self):
        super().__init__()
        plugin_path = os.path.dirname(os.path.abspath(__file__))

        self._application = Application.getInstance()
        self._preferences = self._application.getPreferences()

        self._build_volume_patches = None
        self._cura_engine_backend_patches = None
        self._material_manager_patches = None

        self._global_container_stack = None

        #Belt Plugin environment variable#############################
        self._preferences.addPreference("BeltPlugin/on_plugin", False) #Belt Plugin ON:True,OFF:False

        self._preferences.addPreference("BeltPlugin/gantry_angle", 45) 

        self._preferences.addPreference("BeltPlugin/support_gantry_angle_bias", 45) 
        self._preferences.addPreference("BeltPlugin/support_minimum_island_area", 3.0) 

        self._preferences.addPreference("BeltPlugin/repetitions", 1) 
        self._preferences.addPreference("BeltPlugin/repetitions_distance", 300) 

        #TODO Allow user to be set
        self._preferences.addPreference("BeltPlugin/repetitions_gcode", "\nG92 E0   ; Set Extruder to zero\nG1 E-4 F3900  ; Retract 4mm at 65mm/s\nG92 Z0   ; Set Belt to zero\nG1 Z{belt_repetitions_distance}   ; Advance belt between repetitions\nG92 Z0   ; Set Belt to zero again\n\n;˄˄˄˄˄˄˄˄˄˄˄˄˄˄˄˄ - repetition - ˄˄˄˄˄˄˄˄˄˄˄˄˄˄˄˄\n\nM107    ; Start with the fan off\nG0 X170 ; Move X to the center\nG1 Y1   ; Move y to the belt\nG1 E0   ; Move extruder back to 0\nG92 E-5 ; Add 5mm restart distance\n\n")

        #TODO Raft setting Default Cura
        self._preferences.addPreference("BeltPlugin/raft", False)
        self._preferences.addPreference("BeltPlugin/raft_margin", 0.0)
        self._preferences.addPreference("BeltPlugin/raft_thickness", 0.8)
        self._preferences.addPreference("BeltPlugin/raft_gap", 0.5)
        self._preferences.addPreference("BeltPlugin/raft_speed", 18.0)
        self._preferences.addPreference("BeltPlugin/raft_flow", 1.0)


        self._preferences.addPreference("BeltPlugin/belt_wall_enabled", False)
        self._preferences.addPreference("BeltPlugin/belt_wall_speed", 600.0)
        self._preferences.addPreference("BeltPlugin/belt_wall_flow", 1.0)
        
        self._preferences.addPreference("BeltPlugin/z_offset_gap", 0.25)

        self._preferences.addPreference("BeltPlugin/secondary_fans_enabled", False)
        self._preferences.addPreference("BeltPlugin/secondary_fans_speed", 0)

        #Not setting user
        self._preferences.addPreference("BeltPlugin/z_offset", 0.2)
        self._preferences.addPreference("BeltPlugin/view_depth", 160)

        ###########################################
        self.setMenuName("Belt Extension")
        self.addMenuItem("Setting", self.showSettings)

        self._scene_root = self._application.getController().getScene().getRoot()
        self._scene_root.addDecorator(BeltDecorator.BeltDecorator())

        self._application.getOutputDeviceManager().writeStarted.connect(self._filterGcode)

        self._application.pluginsLoaded.connect(self._onPluginsLoaded)

        # disable update checker plugin (because it checks the wrong version)
        plugin_registry = PluginRegistry.getInstance()
        if "UpdateChecker" not in plugin_registry._disabled_plugins:
            Logger.log("d", "Disabling Update Checker plugin")
            plugin_registry._disabled_plugins.append("UpdateChecker")

    def _onPluginsLoaded(self):
        # make sure the we connect to engineCreatedSignal later than PrepareStage does, so we can substitute our own sidebar
        self._application.engineCreatedSignal.connect(self._onEngineCreated)

        # Hide nozzle in simulation view
        self._application.getController().activeViewChanged.connect(self._onActiveViewChanged)

        # Disable USB printing output device
        self._application.getOutputDeviceManager().outputDevicesChanged.connect(self._onOutputDevicesChanged)

    def _onEngineCreated(self):

        # Apply patches
        Logger.log("d", "Apply Patches")
        self._cura_application_patches = CuraApplicationPatches.CuraApplicationPatches(self._application)
        Logger.log("d", "Apply Build Volume")
        self._build_volume_patches = BuildVolumePatches.BuildVolumePatches(self._application.getBuildVolume())
        self._cura_engine_backend_patches = CuraEngineBackendPatches.CuraEngineBackendPatches(self._application.getBackend())
        self._output_device_patches = {}

        self._application._cura_actions = PatchedCuraActions.PatchedCuraActions()
        self._application._qml_engine.rootContext().setContextProperty("CuraActions", self._application._cura_actions)


        self._application.getBackend().slicingStarted.connect(self._onSlicingStarted)

        gcode_reader_plugin = PluginRegistry.getInstance().getPluginObject("GCodeReader")
        self._flavor_parser_patches = {}
        if gcode_reader_plugin:
            for (parser_name, parser_object) in gcode_reader_plugin._flavor_readers_dict.items():
                self._flavor_parser_patches[parser_name] = FlavorParserPatches.FlavorParserPatches(parser_object)

    def _onSlicingStarted(self):
        self._scene_root.callDecoration("calculateTransformData")

    def _onActiveViewChanged(self):
        self._adjustLayerViewNozzle()

    def _adjustLayerViewNozzle(self):
        global_stack = self._application.getGlobalContainerStack()
        if not global_stack:
            return

        view = self._application.getController().getActiveView()
        if view and view.getPluginId() == "SimulationView":
            gantry_angle = self._preferences.getValue("BeltPlugin/gantry_angle")
            if gantry_angle and float(gantry_angle) > 0:
                view.getNozzleNode().setParent(None)
            else:
                view.getNozzleNode().setParent(self._application.getController().getScene().getRoot())


    def _filterGcode(self, output_device):
        global_stack = self._application.getGlobalContainerStack()

        if not self._preferences.getValue("BeltPlugin/on_plugin"):
            return


        scene = self._application.getController().getScene()
        gcode_dict = getattr(scene, "gcode_dict", {})
        if not gcode_dict: # this also checks for an empty dict
            Logger.log("w", "Scene has no gcode to process")
            return
        dict_changed = False

        enable_secondary_fans = self._preferences.getValue("BeltPlugin/secondary_fans_enabled")
        if enable_secondary_fans:
            secondary_fans_speed = self._preferences.getValue("BeltPlugin/secondary_fans_speed")

        enable_belt_wall = self._preferences.getValue("BeltPlugin/belt_wall_enabled")
        if enable_belt_wall:
            belt_wall_flow = self._preferences.getValue("BeltPlugin/belt_wall_flow")
            belt_wall_speed = self._preferences.getValue("BeltPlugin/belt_wall_speed")
            minimum_y = global_stack.extruders["0"].getProperty("wall_line_width_0", "value") * 0.6 #  0.5 would be non-tolerant

        repetitions = self._preferences.getValue("BeltPlugin/repetitions") or 1
        if repetitions > 1:
            repetitions_distance = self._preferences.getValue("BeltPlugin/repetitions_distance")
            repetitions_gcode = self._preferences.getValue("BeltPlugin/repetitions_gcode")

        for plate_id in gcode_dict:
            gcode_list = gcode_dict[plate_id]
            if not gcode_list:
                continue

            if ";BELTPROCESSED" in gcode_list[0]:
                Logger.log("e", "Already post processed")
                continue
            
            # put a print settings summary at the top
            # note: this simplified view is only valid for single extrusion printers
            setting_values = {}
            setting_summary = ";Setting summary:\n"
            for stack in [global_stack.extruders["0"], global_stack]:
                for index, container in enumerate(stack.getContainers()):
                    if index == ContainerIndexes.Definition:
                        continue
                    for key in container.getAllKeys():
                        if key not in setting_values:
                            value = container.getProperty(key, "value")
                            if not global_stack.getProperty(key, "settable_per_extruder"):
                                value = global_stack.getProperty(key, "value")
                            if isinstance(value, SettingFunction):
                                value = value(stack)
                            definition = container.getInstance(key).definition
                            if definition.type == "str":
                                value = value.replace("\n", "\\n")
                                if len(value) > 40:
                                    value = "[not shown for brevity]"
                            setting_values[key] = value

            for definition in global_stack.getBottom().findDefinitions():
                if definition.type == "category":
                    setting_summary += ";  CATEGORY: %s\n" % definition.label
                elif definition.key in setting_values:
                    setting_summary += ";    %s: %s\n" % (definition.label, setting_values[definition.key])
            gcode_list[0] += setting_summary

            # secondary fans should similar things as print cooling fans
            if enable_secondary_fans:
                search_regex = re.compile(r"M106 S(\d*\.?\d*)")

                for layer_number, layer in enumerate(gcode_list):
                    gcode_list[layer_number] = re.sub(search_regex, lambda m: "M106 P1 S%d\nM106 S%s" % (int(min(255, float(m.group(1)) * secondary_fans_speed)), m.group(1)), layer) #Replace all.
            
            # z_offset change
            _wall_line_width_0 = global_stack.extruders["0"].getProperty("wall_line_width_0", "value")
            _xy_offset = global_stack.extruders["0"].getProperty("xy_offset", "value")

            Logger.log("d", "wall_line_width_0: " + str(_wall_line_width_0) + " xy_offset: " + str(_xy_offset))
            _belt_z_offset_gap = self._preferences.getValue("BeltPlugin/z_offset_gap")
            _gantry_angle = float(self._preferences.getValue("BeltPlugin/gantry_angle"))

            _belt_z_offset = round( ( _wall_line_width_0 / 2.0) - (_belt_z_offset_gap / math.sin(math.radians(_gantry_angle))) - _xy_offset, 4) 
            Logger.log("d", "belt_z_offset" + str(_belt_z_offset))
            gcode_list[1] = gcode_list[1].replace("{belt_z_offset}", str(_belt_z_offset))
            gcode_list[-1] = gcode_list[-1].replace("{belt_z_offset}", str(_belt_z_offset))

            # adjust walls that touch the belt
            if enable_belt_wall:
                #wall_line_width_0
                y = None
                last_y = None
                e = None
                last_e = None
                f = None

                speed_regex = re.compile(r" F\d*\.?\d*")
                extrude_regex = re.compile(r" E-?\d*\.?\d*")
                move_parameters_regex = re.compile(r"([YEF]-?\d*\.?\d+)")

                for layer_number, layer in enumerate(gcode_list):
                    if layer_number < 2 or layer_number > len(gcode_list) - 1:
                        # gcode_list[0]: curaengine header
                        # gcode_list[1]: start gcode
                        # gcode_list[2] - gcode_list[n-1]: layers
                        # gcode_list[n]: end gcode
                        continue

                    lines = layer.splitlines()
                    for line_number, line in enumerate(lines):
                        line_has_e = False
                        line_has_axis = False

                        gcode_command = line.split(' ', 1)[0]
                        if gcode_command not in ["G0", "G1", "G92"]:
                            continue

                        result = re.findall(move_parameters_regex, line)
                        if not result:
                            continue

                        for match in result:
                            parameter = match[:1]
                            value = float(match[1:])
                            if parameter == "Y":
                                y = value
                                line_has_axis = True
                            elif parameter == "E":
                                e = value
                                line_has_e = True
                            elif parameter == "F":
                                f = value
                            elif parameter in "XZ":
                                line_has_axis = True

                        if gcode_command != "G92" and line_has_axis and line_has_e and f is not None and y is not None and y <= minimum_y and last_y is not None and last_y <= minimum_y:
                            if f > belt_wall_speed:
                                # Remove pre-existing move speed and add our own
                                line = re.sub(speed_regex, r"", line)

                            if belt_wall_flow != 1.0 and last_y is not None:
                                new_e = last_e + (e - last_e) * belt_wall_flow
                                line = re.sub(extrude_regex, " E%f" % new_e, line)
                                line += " ; Adjusted E for belt wall\nG92 E%f ; Reset E to pre-compensated value" % e

                            if f > belt_wall_speed:
                                g_type = int(line[1:2])
                                line = "G%d F%d ; Belt wall speed\n%s\nG%d F%d ; Restored speed" % (g_type, belt_wall_speed, line, g_type, f)

                            lines[line_number] = line

                        last_y = y
                        last_e = e

                    edited_layer = "\n".join(lines) + "\n"
                    gcode_list[layer_number] = edited_layer

            # HOTFIX: remove finalize bits before end gcode
            end_gcode = gcode_list[len(gcode_list)-1]
            end_gcode = end_gcode.replace("M140 S0\nM203 Z5\nM107", "") # TODO: regex magic
            gcode_list[len(gcode_list)-1] = end_gcode

            # make repetitions
            if repetitions > 1 and len(gcode_list) > 2:
                # gcode_list[0]: curaengine header
                # gcode_list[1]: start gcode
                # gcode_list[2] - gcode_list[n-1]: layers
                # gcode_list[n]: end gcode
                layers = gcode_list[2:-1]
                layers.append(repetitions_gcode.replace("{belt_repetitions_distance}", str(repetitions_distance)))
                gcode_list[2:-1] = (layers * int(repetitions))[0:-1]

            gcode_list[0] += ";BELTPROCESSED\n"
            gcode_dict[plate_id] = gcode_list
            dict_changed = True

        if dict_changed:
            setattr(scene, "gcode_dict", gcode_dict)

    def showSettings(self) -> None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"qml","BeltSettings.qml")
        self._settings_dialog = self._application.createQmlComponent(path, {"manager":self})
        self._settings_dialog.show()
    
    @pyqtSlot()
    def resetSlice(self):
        _background = self._application.getBackend()
        _background.backendStateChange.emit(BackendState.NotStarted)