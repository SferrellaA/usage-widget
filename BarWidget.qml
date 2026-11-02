import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Format.js" as Format

// Bar label for the weekly SuperGrok pool: "59% · 3d 4h", or "59% · 0h 42m"
// in the last hour. The collector owns login. This file only paints the
// public status record.
BarWidget {
  id: root
  moduleName: "usage.limits"

  property string auth: ""
  property bool ok: false
  property var percentUsed: null
  property string resetsAt: ""
  property string plan: ""
  property string message: ""
  property string fetchedAt: ""
  property bool fetchRunning: false
  property int remaining: -1
  property double expiryRefreshAt: 0

  readonly property int refreshIntervalSec: {
    var value = Number(setting("refreshIntervalSec", 300))
    if (!isFinite(value)) return 300
    return Math.max(60, Math.min(3600, Math.round(value)))
  }

  readonly property string collectorPath: fileUrlToPath(Qt.resolvedUrl("bin/usage-collect"))

  function fileUrlToPath(url) {
    var text = String(url)
    if (text.startsWith("file://")) text = text.substring(7)
    return decodeURIComponent(text)
  }

  function recompute() {
    if (resetsAt === "") {
      remaining = -1
      return
    }
    var end = Date.parse(resetsAt)
    remaining = isNaN(end) ? -1 : Math.floor((end - Date.now()) / 1000)
    // The percent belongs to that window. Once it has ended, do not keep
    // painting it as 100% · 0h 0m while the next window's reading is in flight.
    if (remaining < 0 && ok && !fetchRunning && Date.now() - expiryRefreshAt > 10000) {
      expiryRefreshAt = Date.now()
      refresh()
    }
  }

  readonly property bool windowOpen: ok && percentUsed !== null && remaining >= 0
  readonly property string barText: {
    if (windowOpen) return Format.label(percentUsed, remaining)
    if (auth === "signed-out") return "sign in"
    if (auth === "missing") return "no grok"
    if (auth === "" || (ok && remaining < 0)) return "…"
    return "usage?"
  }
  readonly property bool urgent: windowOpen && (remaining < 3600 || Number(percentUsed) >= 90)
  readonly property string tooltipText: {
    if (ok && remaining < 0) return "Usage window reset, refreshing"
    if (!ok) return message !== "" ? message : "Usage unavailable"
    var when = Qt.formatDateTime(new Date(resetsAt), "ddd HH:mm")
    var planText = plan !== "" ? plan : "SuperGrok"
    return planText + " · " + Math.round(Number(percentUsed)) + "% used · resets " + when
  }

  function apply(text) {
    var parsed
    try {
      parsed = JSON.parse(String(text).trim())
    } catch (error) {
      if (!ok) {
        auth = "error"
        message = "Usage unavailable"
      }
      return
    }
    if (!parsed || parsed.provider !== "grok") return
    auth = String(parsed.auth || "error")
    message = String(parsed.message || "")
    fetchedAt = String(parsed.fetchedAt || "")
    if (parsed.ok === true && parsed.percentUsed !== null && parsed.percentUsed !== undefined) {
      ok = true
      percentUsed = Number(parsed.percentUsed)
      resetsAt = String(parsed.resetsAt || "")
      plan = String(parsed.plan || "")
      recompute()
    } else if (auth === "signed-out" || auth === "missing") {
      ok = false
      percentUsed = null
      resetsAt = ""
      recompute()
    }
  }

  function refresh() {
    if (fetchRunning) return
    fetchRunning = true
    collector.command = ["python3", collectorPath]
    collector.running = true
  }

  function tick() {
    recompute()
  }

  function signIn() {
    if (root.bar) root.bar.run("omarchy launch terminal grok login")
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Timer {
    interval: root.refreshIntervalSec * 1000
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Timer {
    interval: 15000
    repeat: true
    running: true
    onTriggered: root.tick()
  }

  Process {
    id: collector
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.apply(text)
    }
    onExited: root.fetchRunning = false
  }

  IpcHandler {
    target: "usage.limits"

    function refresh(): void { root.broadcast("refresh") }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.barText
    labelVisible: false
    hasVisualContent: true
    tooltipText: root.tooltipText
    active: root.urgent
    horizontalMargin: 8.75
    verticalPadding: 8.75
    fixedWidth: contentRow.implicitWidth + scaledHorizontalMargin * 2

    readonly property color ink: active && useActiveColor ? activeColor : foreground
    readonly property bool lightForeground: (foreground.r + foreground.g + foreground.b) / 3 >= 0.5

    onPressed: function(b) {
      if (b === Qt.RightButton) root.refresh()
      else if (root.auth === "signed-out" || root.auth === "missing") root.signIn()
      else root.refresh()
    }

    Row {
      id: contentRow
      anchors.centerIn: parent
      spacing: 5

      Image {
        visible: root.windowOpen
        source: button.lightForeground
          ? Qt.resolvedUrl("assets/Grok_Logomark_Light.svg")
          : Qt.resolvedUrl("assets/Grok_Logomark_Dark.svg")
        sourceSize.width: button.fontSize
        sourceSize.height: button.fontSize
        width: button.fontSize
        height: button.fontSize
        fillMode: Image.PreserveAspectFit
        anchors.verticalCenter: parent.verticalCenter
      }

      Text {
        text: root.barText
        color: button.ink
        font.family: button.fontFamily
        font.pixelSize: button.fontSize
        renderType: Text.NativeRendering
        anchors.verticalCenter: parent.verticalCenter
      }
    }
  }
}
