import AppKit
import Foundation

func require(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fputs("FAIL: \(message)\n", stderr); exit(1) }
}

let now = Date(timeIntervalSince1970: 1000)
let window = SelectionWindow(pid: 42, id: 12, frame: CGRect(x: 100, y: 100, width: 500, height: 300))
let anchor = TerminalSelectionAnchor(window: window, point: CGPoint(x: 250, y: 200), createdAt: now)
require(anchor.isUsable(bundleID: "com.apple.Terminal", window: window, now: now.addingTimeInterval(2)),
        "a fresh selection in the same Terminal window permits the copy gesture")
require(!anchor.isUsable(bundleID: "com.google.Chrome", window: window, now: now),
        "another app must never receive the Terminal right-click")
require(!anchor.isUsable(bundleID: "com.apple.Terminal", window: nil, now: now),
        "a missing or covered window blocks automation")
require(!anchor.isUsable(bundleID: "com.apple.Terminal", window: SelectionWindow(pid: 42, id: 13, frame: window.frame), now: now),
        "another window in the same Terminal process cannot inherit the selection")
require(!anchor.isUsable(bundleID: "com.apple.Terminal", window: SelectionWindow(pid: 43, id: 12, frame: window.frame), now: now),
        "a different process cannot inherit the selection")
require(!anchor.isUsable(bundleID: "com.apple.Terminal", window: SelectionWindow(pid: 42, id: 12, frame: window.frame.offsetBy(dx: 1, dy: 0)), now: now),
        "moving the original window invalidates the recorded click coordinates")
require(!anchor.isUsable(bundleID: "com.apple.Terminal", window: window, now: now.addingTimeInterval(121)),
        "stale selections cannot trigger later clicks")
require(!anchor.isUsable(bundleID: "com.apple.Terminal", window: window, now: now.addingTimeInterval(-1)),
        "clock reversal fails closed")
let outside = TerminalSelectionAnchor(window: window, point: CGPoint(x: 0, y: 0), createdAt: now)
require(!outside.isUsable(bundleID: "com.apple.Terminal", window: window, now: now),
        "points outside the recorded window are rejected")
print("PASS: Terminal selection target, window geometry, and freshness guards")

var currentWindow: SelectionWindow? = window
let tracker = SelectedTextReader(windowAtPoint: { point, pid in
    guard let currentWindow, currentWindow.pid == pid, currentWindow.frame.contains(point) else { return nil }
    return currentWindow
})
let start = CGPoint(x: 180, y: 150)
let end = CGPoint(x: 300, y: 340)
func mouse(_ type: NSEvent.EventType, at point: CGPoint = end, seconds: TimeInterval = 1) {
    tracker.observeTerminalMouse(type: type, point: point, ownerPID: window.pid,
                                 now: now.addingTimeInterval(seconds))
}

mouse(.scrollWheel)
require(tracker.anchor == nil, "scrolling alone must not invent a text selection")
mouse(.leftMouseDown, at: start)
mouse(.leftMouseDragged)
mouse(.scrollWheel, seconds: 2)
mouse(.scrollWheel, seconds: 3)
mouse(.leftMouseUp, seconds: 4)
require(tracker.anchor?.point == end, "scrolling while extending a selection must preserve the drag until release")
let revisionBeforeScroll = tracker.inputRevision
mouse(.scrollWheel, at: start, seconds: 5)
require(tracker.anchor?.point == end, "scrolling a completed highlight must keep the copy target in its original text area")
require(tracker.inputRevision > revisionBeforeScroll, "scrolling still cancels a copy already in flight")
require(tracker.anchor?.createdAt == now.addingTimeInterval(5), "interaction with a valid selection refreshes its lifetime")

// Continue extending after a scroll and release beyond the window, as when
// dragging past a viewport edge to select multiple screens of transcript.
mouse(.leftMouseDown, at: start)
mouse(.leftMouseDragged)
mouse(.scrollWheel)
let lastInsidePoint = CGPoint(x: 300, y: 390)
mouse(.leftMouseDragged, at: lastInsidePoint)
mouse(.leftMouseUp, at: CGPoint(x: 300, y: 420))
require(tracker.anchor?.point == lastInsidePoint, "a long drag released outside the viewport keeps its last in-window target")

currentWindow = SelectionWindow(pid: window.pid, id: 99, frame: window.frame)
mouse(.scrollWheel)
require(tracker.anchor == nil, "scrolling another Terminal window must discard the previous target")
currentWindow = window
mouse(.leftMouseDown, at: start)
mouse(.leftMouseDragged)
currentWindow = SelectionWindow(pid: window.pid, id: window.id, frame: window.frame.offsetBy(dx: 10, dy: 0))
mouse(.scrollWheel)
currentWindow = window
mouse(.leftMouseUp)
require(tracker.anchor == nil, "a window moved mid-drag must not leave a reusable selection")

mouse(.leftMouseDown, at: start)
mouse(.leftMouseDragged)
mouse(.leftMouseUp, seconds: 1)
mouse(.scrollWheel, seconds: 122)
require(tracker.anchor == nil, "scrolling must not revive an expired selection")
mouse(.leftMouseDown, at: start)
mouse(.leftMouseDragged)
mouse(.leftMouseUp)
mouse(.leftMouseDown, at: start)
mouse(.leftMouseUp, at: start)
require(tracker.anchor == nil, "a plain click still clears the tracked highlight")
print("PASS: scroll during and after selection, viewport edges, copy cancellation, and stale-window guards")

let source = CGEventSource(stateID: .privateState)
if let copy = CGEvent(keyboardEventSource: source, virtualKey: 8, keyDown: true) {
    copy.flags = .maskCommand
    copy.setIntegerValueField(.eventSourceUserData, value: 0x4452434F5059)
    guard let event = NSEvent(cgEvent: copy) else { fatalError("Could not wrap a test copy event") }
    let reader = SelectedTextReader()
    require(reader.isExpectedCopyKey(event), "tagged synthetic copy must not cancel its own capture")
    guard let plainCopy = CGEvent(keyboardEventSource: CGEventSource(stateID: .privateState), virtualKey: 8, keyDown: true) else {
        fatalError("Could not create an untagged key event")
    }
    plainCopy.flags = .maskCommand
    guard let untagged = NSEvent(cgEvent: plainCopy) else { fatalError("Could not wrap an untagged key event") }
    require(!reader.isExpectedCopyKey(untagged), "an unrelated Command-C cannot impersonate the tagged event")
}
print("PASS: generated copy events are distinguished from other keyboard input")

let pasteboard = NSPasteboard.withUniqueName()
defer { pasteboard.releaseGlobally() }

func setOriginal() {
    pasteboard.clearContents()
    let item = NSPasteboardItem()
    item.setString("original clipboard", forType: .string)
    item.setData(Data([0, 1, 2, 255]), forType: NSPasteboard.PasteboardType("test.readback.rich-data"))
    pasteboard.writeObjects([item])
}

setOriginal()
let empty = SelectionClipboardTransaction(pasteboard: pasteboard)
require(empty.takeCopiedText() == nil, "a failed copy never returns stale original clipboard text")
empty.cancel()
require(pasteboard.string(forType: .string) == "original clipboard", "timeout restores the previous clipboard")
require(pasteboard.data(forType: NSPasteboard.PasteboardType("test.readback.rich-data")) == Data([0, 1, 2, 255]),
        "clipboard restoration preserves non-text representations")

let successful = SelectionClipboardTransaction(pasteboard: pasteboard)
require(successful.takeCopiedText() == nil, "polling waits for an actual copy")
pasteboard.clearContents()
pasteboard.setString("  selected Codex passage\n", forType: .string)
require(successful.takeCopiedText() == "selected Codex passage", "new copied text is returned")
require(pasteboard.string(forType: .string) == "original clipboard", "success preserves the preexisting clipboard")
require(successful.takeCopiedText() == nil, "a completed capture cannot read the restored old clipboard on a second poll")

let largeSelection = (1...2500).map { "Paragraph \($0): selected text, Unicode café, and another line.\n" }.joined()
let largeCopy = SelectionClipboardTransaction(pasteboard: pasteboard)
pasteboard.clearContents()
pasteboard.setString(largeSelection, forType: .string)
require(largeCopy.takeCopiedText() == largeSelection.trimmingCharacters(in: .whitespacesAndNewlines),
        "a large multi-paragraph selection is captured completely without a character cutoff")
require(pasteboard.string(forType: .string) == "original clipboard", "large copies still restore the previous clipboard")
print("PASS: complete large selection capture (\(largeSelection.count) characters)")

let interrupted = SelectionClipboardTransaction(pasteboard: pasteboard)
pasteboard.clearContents()
pasteboard.setString("a newer user copy", forType: .string)
interrupted.cancel()
require(pasteboard.string(forType: .string) == "a newer user copy", "cancellation does not overwrite a newer user copy")

let nontext = SelectionClipboardTransaction(pasteboard: pasteboard)
pasteboard.clearContents()
pasteboard.setData(Data([1, 2, 3]), forType: .png)
require(nontext.takeCopiedText() == nil, "non-text clipboard changes are never spoken")
nontext.cancel()
require(pasteboard.data(forType: .png) == Data([1, 2, 3]), "new non-text clipboard data is preserved")

pasteboard.clearContents()
let initiallyEmpty = SelectionClipboardTransaction(pasteboard: pasteboard)
pasteboard.setString("new selection", forType: .string)
require(initiallyEmpty.takeCopiedText() == "new selection", "copy works with an initially empty clipboard")
require(pasteboard.string(forType: .string) == nil, "an originally empty clipboard is restored to empty")
print("PASS: fresh copy capture, rich clipboard preservation, timeout, cancellation, and non-text handling")
