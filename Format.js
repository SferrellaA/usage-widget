.pragma library

// Keep in sync with usage_widget/display.py. tests/vectors.json covers both.

function countdown(remainingSeconds) {
  var remaining = Math.floor(Number(remainingSeconds))
  if (!isFinite(remaining) || remaining <= 0) return "0h 0m"
  if (remaining < 86400) {
    var hours = Math.floor(remaining / 3600)
    var minutes = Math.floor((remaining % 3600) / 60)
    return hours + "h " + minutes + "m"
  }
  var days = Math.floor(remaining / 86400)
  var hourPart = Math.floor((remaining % 86400) / 3600)
  return days + "d " + hourPart + "h"
}

function percentText(percent) {
  var value = Number(percent)
  if (!isFinite(value)) return ""
  var rounded = value >= 0 ? Math.floor(value + 0.5) : 0
  if (rounded < 0) rounded = 0
  if (rounded > 100) rounded = 100
  return rounded + "%"
}

function label(percent, remainingSeconds) {
  var used = percentText(percent)
  if (used === "") return ""
  return used + " · " + countdown(remainingSeconds)
}
