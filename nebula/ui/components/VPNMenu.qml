/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

import QtQuick 2.5
import QtQuick.Controls 2.14

import Mozilla.VPN 1.0
import themes 0.1

Item {
    id: menuBar

    property alias objectName: iconButton.objectName
    property alias title: title.text
    property alias rightTitle: rightTitle.text
    property bool isSettingsView: false
    property bool isMultiHopView: false
    property bool isMainView: false
    property bool accessibleIgnored: false
    property bool btnDisabled: false
    property alias forceFocus: iconButton.focus
    property var currentStackView: ({})
    signal clicked(QtObject mouse)

    width: parent.width
    height: Theme.menuHeight
    // Ensure that menu is on top of possible scrollable
    // content.
    z: 2

    MouseArea {
        // Prevent mouse events from passing through to
        // underlying elements
        anchors.fill: menuBar
        preventStealing: true
        propagateComposedEvents: false
        hoverEnabled: true
        onClicked: mouse => menuBar.clicked(mouse)
    }

    Rectangle {
        id: menuBackground
        color: Theme.bgColor
        y: 0
        width: parent.width
        height: 55
    }

    VPNIconButton {
        id: iconButton

        skipEnsureVisible: true // prevents scrolling of lists when this is focused

        onClicked: handleGoBack()
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.topMargin: Theme.windowMargin / 2
        anchors.leftMargin: Theme.windowMargin / 2
        //% "Back"
        //: Go back
        accessibleName: qsTrId("vpn.main.back")
        Accessible.ignored: accessibleIgnored

        enabled: !btnDisabled
        opacity: enabled ? 1 : .4
        Image {
            id: backImage

            source: "qrc:/nebula/resources/back.svg"
            sourceSize.width: Theme.iconSize
            fillMode: Image.PreserveAspectFit
            anchors.centerIn: iconButton
        }

    }

    VPNBoldLabel {
        id: title

        anchors.top: menuBar.top
        anchors.centerIn: menuBar
        Accessible.ignored: accessibleIgnored
    }

    VPNLightLabel {
        id: rightTitle

        anchors.verticalCenter: menuBar.verticalCenter
        anchors.right: menuBar.right
        anchors.rightMargin: Theme.windowMargin
        Accessible.ignored: accessibleIgnored
    }

    Rectangle {
        color: "#0C0C0D0A"
        y: 55
        width: parent.width
        height: 1
    }

    function handleGoBack() {
        isMultiHopView ? handleMultiHopNav() : currentStackView.pop();
    }

    function setCurrentStackView() {
        if (isMainView) {
            currentStackView = mainStackView;
        } else if (isSettingsView) {
            currentStackView = settingsStackView;
        } else if (stackview) {
            currentStackView = stackview;
        }
    }

    function clearViewStack() {
        currentStackView.pop(null, StackView.Immediate);

        if (stackview) {
            stackview.pop(StackView.Immediate);
        }
    }

    Component.onCompleted: () => {
        setCurrentStackView();
    }

    Connections {
        target: VPN

        function onClearCurrentViewStack() {
            console.log("onClearCurrentViewStack");
            menuBar.clearViewStack();
        }
    }

}
