import QtQuick 2.1
import QtQuick.Controls 1.4
import QtQuick.Dialogs 1.2
import QtQuick.Window 2.1

import UM 1.3 as UM
import Cura 1.0 as Cura



UM.Dialog
{
    id: base

    title: catalog.i18nc("@title:window", "BirthT Settings")

    minimumWidth: 400 * screenScaleFactor
    minimumHeight: contents.implicitHeight + 5 * UM.Theme.getSize("default_margin").height
    width: minimumWidth
    height: minimumHeight

    property variant catalog: UM.I18nCatalog { name: "belt_printer_slicing" }

    function boolCheck(value) //Hack to ensure a good match between python and qml.
    {
        if(value == "True")
        {
            return true
        }else if(value == "False" || value == undefined)
        {
            return false
        }
        else
        {
            return value
        }
    }

    Column
    {
        id: contents
        anchors.fill: parent
        spacing: UM.Theme.getSize("default_lining").height

        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""

            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:enable","BeltPlugin") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                CheckBox
                {
                    id: onBeltPlugin
                    checked: boolCheck(UM.Preferences.getValue("BeltPlugin/on_plugin"))
                }
            }
        }

        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:gantry_angle","Gantry angle[deg]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:gantryAngleInput
                    text: UM.Preferences.getValue("BeltPlugin/gantry_angle")
                    validator: RegExpValidator { regExp : /[0-9]+\.[0-9]+/ }
                }
            }
        }

        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:copies","Copies") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:repetitionsInput
                    text: UM.Preferences.getValue("BeltPlugin/repetitions")
                    validator: RegExpValidator { regExp : /[1-9]|[1-9][0-9]/ }
                }
            }
        }

        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked && (parseInt(repetitionsInput.text) > 1)
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:repetitions_distance","Repetitions distance[mm]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:repetitionsDistanceInput
                    text: UM.Preferences.getValue("BeltPlugin/repetitions_distance")
                    validator: RegExpValidator { regExp : /[0-9]+\.[0-9]+/ }
                }
            }
        }


        //Raft Settings
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:print_raft","Print Raft") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                CheckBox
                {
                    id: onPrintRaft
                    checked: boolCheck(UM.Preferences.getValue("BeltPlugin/raft"))
                }
            }
        }
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked && onPrintRaft.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:raft_margin","Raft margin[mm]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:raftMarginInput
                    text: UM.Preferences.getValue("BeltPlugin/raft_margin")
                    validator: RegExpValidator { regExp : /[0-9]+\.[0-9]+/ }
                }
            }
        }
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked && onPrintRaft.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:raft_thickness", "Raft thickness[mm]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:raftThicknessInput
                    text: UM.Preferences.getValue("BeltPlugin/raft_thickness")
                    validator: RegExpValidator { regExp : /[0-9]+\.[0-9]+/ }
                }
            }
        }
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked && onPrintRaft.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:raft_gap","Raft gap[mm]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:raftGapInput
                    text: UM.Preferences.getValue("BeltPlugin/raft_gap")
                    validator: RegExpValidator { regExp : /[0-9]+\.[0-9]+/ }
                }
            }
        }
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked && onPrintRaft.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:raft_speed","Raft speed[mm/s]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:raftSpeedInput
                    text: UM.Preferences.getValue("BeltPlugin/raft_speed")
                    validator: RegExpValidator { regExp : /[0-9]+\.[0-9]+/ }
                }
            }
        }
        /*
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked && onPrintRaft.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:raft_flow", "Raft flow[%]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:raftFlowInput
                    text: UM.Preferences.getValue("BeltPlugin/raft_flow")
                    validator: RegExpValidator { regExp : /[0-9]+\.[0-9]+/ }
                }
            }
        }
        */

        //Adjust Belt Wall
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:adjust_belt_wall","Adjust Belt Wall") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                CheckBox
                {
                    id: onAdjustBeltWall
                    checked: boolCheck(UM.Preferences.getValue("BeltPlugin/belt_wall_enabled"))
                }
            }
        }
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked && onAdjustBeltWall.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:belt_wall_speed", "Belt wall speed[mm/s]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:beltWallSpeedInput
                    text: UM.Preferences.getValue("BeltPlugin/belt_wall_speed") / 60.0
                    validator: RegExpValidator { regExp : /[0-9]+\.[0-9]+/ }
                }
            }
        }
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked && onAdjustBeltWall.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:belt_wall_flow","Belt wall flow[%]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:beltWallFlowInput
                    text: UM.Preferences.getValue("BeltPlugin/belt_wall_flow") * 100.0
                    validator: RegExpValidator { regExp : /[0-9]+\.[0-9]+/ }
                }
            }
        }

        //Belt offset 
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:belt_offset","Belt offset[mm]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:beltOffsetInput
                    text: UM.Preferences.getValue("BeltPlugin/z_offset_gap")
                    validator: RegExpValidator { regExp : /[0-9]+\.[0-9]+/ }
                }
            }
        }

        //secondary fan
        /*
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:enable_secondary_print_fans", "Enable Secondary Print Fans") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                CheckBox
                {
                    id: onSecondaryFans
                    checked: boolCheck(UM.Preferences.getValue("BeltPlugin/secondary_fans_enabled"))
                }
            }
        }
        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: ""
            visible: onBeltPlugin.checked && onSecondaryFans.checked
            Row {
                Label {
                    text: catalog.i18nc("@beltplugin:secondary_print_fan_speed","Secondary Print Fan Speed[%]") + " : "
                    anchors.verticalCenter : parent.verticalCenter
                }
                TextField{
                    id:secondaryFansSpeedInput
                    text: UM.Preferences.getValue("BeltPlugin/secondary_fans_speed")
                    validator: RegExpValidator { regExp : /([0-9]|[1-9][0-9])(\.[0-9]+)?|100/ }
                }
            }
        }
        */

        
    }

    rightButtons: [
        Button
        {
            id: saveButton
            text: catalog.i18nc("@action:button","Save")
            onClicked: {
                UM.Preferences.setValue("BeltPlugin/on_plugin", onBeltPlugin.checked);
                UM.Preferences.setValue("BeltPlugin/gantry_angle", gantryAngleInput.text);

                //repetitions settings
                UM.Preferences.setValue("BeltPlugin/repetitions", parseInt(repetitionsInput.text));
                UM.Preferences.setValue("BeltPlugin/repetitions_distance", parseFloat(repetitionsDistanceInput.text));

                //raft settings
                UM.Preferences.setValue("BeltPlugin/raft", onPrintRaft.checked);
                UM.Preferences.setValue("BeltPlugin/raft_margin",  parseFloat(raftMarginInput.text));
                UM.Preferences.setValue("BeltPlugin/raft_thickness", parseFloat(raftThicknessInput.text));
                UM.Preferences.setValue("BeltPlugin/raft_gap", parseFloat(raftGapInput.text));
                UM.Preferences.setValue("BeltPlugin/raft_speed", parseFloat(raftSpeedInput.text));
                //UM.Preferences.setValue("BeltPlugin/raft_flow", parseFloat(raftFlowInput.text));

                //Belt wall settings
                UM.Preferences.setValue("BeltPlugin/belt_wall_enabled", onAdjustBeltWall.checked);
                UM.Preferences.setValue("BeltPlugin/belt_wall_speed", (parseFloat(beltWallSpeedInput.text) * 60));
                UM.Preferences.setValue("BeltPlugin/belt_wall_flow", (parseFloat(beltWallFlowInput.text) / 100.0));

                //Belt z offset
                UM.Preferences.setValue("BeltPlugin/z_offset_gap", parseFloat(beltOffsetInput.text));

                //Secondary Fans Settings
                //UM.Preferences.setValue("BeltPlugin/secondary_fans_enabled", onSecondaryFans.checked);
                //UM.Preferences.setValue("BeltPlugin/secondary_fans_speed", parseFloat(secondaryFansSpeedInput.text));

                manager.resetSlice();
                base.reject();
            }
        } ,
        Button
        {
            id: cancelButton
            text: catalog.i18nc("@action:button","Close")
            onClicked: base.reject()
        }
    ]
}