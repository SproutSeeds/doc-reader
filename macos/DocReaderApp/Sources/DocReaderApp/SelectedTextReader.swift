import AppKit
import ApplicationServices

struct PasteboardSnapshot {
    struct Entry {
        let type: NSPasteboard.PasteboardType
        let data: Data
    }

    let items: [[Entry]]

    static func capture(from pasteboard: NSPasteboard) -> PasteboardSnapshot {
        let items = (pasteboard.pasteboardItems ?? []).map { item in
            item.types.compactMap { type -> Entry? in
                guard let data = item.data(forType: type) else { return nil }
                return Entry(type: type, data: data)
            }
        }
        return PasteboardSnapshot(items: items)
    }

    func restore(to pasteboard: NSPasteboard) {
        pasteboard.clearContents()
        let restoredItems = items.map { entries -> NSPasteboardItem in
            let item = NSPasteboardItem()
            for entry in entries { item.setData(entry.data, forType: entry.type) }
            return item
        }
        if !restoredItems.isEmpty { pasteboard.writeObjects(restoredItems) }
    }
}

// A copy request never treats the previous clipboard as a selected passage.
// Restoration is conditional so an interrupted request cannot overwrite a new copy.
final class SelectionClipboardTransaction {
    private let pasteboard: NSPasteboard
    private let snapshot: PasteboardSnapshot
    private let clearedChangeCount: Int
    private var completed = false

    init(pasteboard: NSPasteboard) {
        self.pasteboard = pasteboard
        snapshot = .capture(from: pasteboard)
        clearedChangeCount = pasteboard.clearContents()
    }

    func takeCopiedText() -> String? {
        guard !completed else { return nil }
        let copiedChangeCount = pasteboard.changeCount
        // Some writers fill a cleared pasteboard without another changeCount
        // increment. Any text appearing after our clear is still a fresh copy.
        guard let value = pasteboard.string(forType: .string),
              !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }
        let text = value.trimmingCharacters(in: .whitespacesAndNewlines)
        completed = true
        if pasteboard.changeCount == copiedChangeCount { snapshot.restore(to: pasteboard) }
        return text
    }

    func cancel() {
        guard !completed else { return }
        completed = true
        if pasteboard.changeCount == clearedChangeCount && (pasteboard.types ?? []).isEmpty {
            snapshot.restore(to: pasteboard)
        }
    }
}

struct SelectionWindow: Equatable {
    let pid: pid_t
    let id: CGWindowID
    let frame: CGRect
}

struct TerminalSelectionAnchor {
    let window: SelectionWindow
    let point: CGPoint
    let createdAt: Date

    func isUsable(bundleID: String?, window currentWindow: SelectionWindow?, now: Date) -> Bool {
        let age = now.timeIntervalSince(createdAt)
        return bundleID == "com.apple.Terminal" && age >= 0 && age <= 120
            && currentWindow == window && window.frame.contains(point)
    }
}

/// Native selection first, then the foreground app's copy operation. Terminal's
/// app-owned selections (including Codex fullscreen transcripts) use the same
/// right-click copy gesture the user performs, at a recorded selection point.
final class SelectedTextReader {
    var onDiagnostic: ((String) -> Void)?
    struct Selection {
        let text: String
        let method: String
    }

    private static let eventMarker: Int64 = 0x4452434F5059
    private var globalMouseMonitor: Any?
    private var localMouseMonitor: Any?
    private var mouseDown: (point: CGPoint, window: SelectionWindow, clicks: Int)?
    private var mouseDragged = false
    private var lastDragPoint: CGPoint?
    private(set) var anchor: TerminalSelectionAnchor?
    private(set) var inputRevision = 0
    private var expectedCopyKeyUntil = Date.distantPast
    private var expectedRightClick: (point: CGPoint, until: Date)?
    private let windowAtPoint: (CGPoint, pid_t) -> SelectionWindow?

    init(windowAtPoint: @escaping (CGPoint, pid_t) -> SelectionWindow? = SelectedTextReader.window) {
        self.windowAtPoint = windowAtPoint
    }

    static func isOwnEvent(_ event: NSEvent) -> Bool {
        event.cgEvent?.getIntegerValueField(.eventSourceUserData) == eventMarker
    }

    func isExpectedCopyKey(_ event: NSEvent) -> Bool {
        Self.isOwnEvent(event) || (Date() < expectedCopyKeyUntil && event.type == .keyDown
            && event.keyCode == 8 && event.modifierFlags.contains(.command))
    }

    private func isExpectedRightClick(_ event: NSEvent) -> Bool {
        if Self.isOwnEvent(event) { return true }
        guard event.type == .rightMouseDown, let expectedRightClick,
              Date() < expectedRightClick.until, let point = event.cgEvent?.location else { return false }
        return hypot(point.x - expectedRightClick.point.x, point.y - expectedRightClick.point.y) <= 3
    }

    func startMonitoring() {
        guard globalMouseMonitor == nil else { return }
        let mask: NSEvent.EventTypeMask = [.leftMouseDown, .leftMouseDragged, .leftMouseUp,
                                          .rightMouseDown, .otherMouseDown, .scrollWheel]
        globalMouseMonitor = NSEvent.addGlobalMonitorForEvents(matching: mask) { [weak self] event in
            self?.observeMouse(event)
        }
        localMouseMonitor = NSEvent.addLocalMonitorForEvents(matching: mask) { [weak self] event in
            self?.observeMouse(event)
            return event
        }
    }

    deinit {
        if let globalMouseMonitor { NSEvent.removeMonitor(globalMouseMonitor) }
        if let localMouseMonitor { NSEvent.removeMonitor(localMouseMonitor) }
    }

    func invalidate(reason: String = "input") {
        if let anchor { onDiagnostic?("terminal-selection invalidated reason=\(reason) window=\(anchor.window.id)") }
        inputRevision += 1
        anchor = nil
        mouseDown = nil
        mouseDragged = false
        lastDragPoint = nil
    }

    func noteNonReadbackKey(_ event: NSEvent) {
        // Codex's fullscreen transcript can deliver non-copy key events while
        // keeping its own selection visible. Cancel an active copy, but retain
        // the last mouse selection until a new click or Escape removes it.
        inputRevision += 1
        if event.keyCode == 53 { invalidate(reason: "escape") }
    }

    private func observeMouse(_ event: NSEvent) {
        guard !isExpectedRightClick(event) else { return }
        guard let point = event.cgEvent?.location,
              let app = NSWorkspace.shared.frontmostApplication,
              app.bundleIdentifier == "com.apple.Terminal" else {
            invalidate(reason: "frontmost-app-or-point")
            return
        }
        observeTerminalMouse(type: event.type, point: point,
                             clickCount: event.type == .leftMouseDown ? event.clickCount : 1,
                             ownerPID: app.processIdentifier)
    }

    // Separate event decoding from selection tracking so complete gestures,
    // including scrolling during a drag, can be checked without sending input.
    func observeTerminalMouse(type: NSEvent.EventType, point: CGPoint, clickCount: Int = 1,
                              ownerPID: pid_t, now: Date = Date()) {
        switch type {
        case .leftMouseDown:
            invalidate(reason: "new-mouse-selection")
            guard let window = windowAtPoint(point, ownerPID) else {
                onDiagnostic?("terminal-mouse down ignored reason=no-terminal-window")
                return
            }
            mouseDown = (point, window, clickCount)
            onDiagnostic?("terminal-mouse down window=\(window.id) clicks=\(clickCount)")
        case .leftMouseDragged:
            guard let mouseDown else { return }
            if hypot(point.x - mouseDown.point.x, point.y - mouseDown.point.y) >= 3 {
                if !mouseDragged { onDiagnostic?("terminal-mouse drag window=\(mouseDown.window.id)") }
                mouseDragged = true
                lastDragPoint = point
            }
        case .leftMouseUp:
            guard let down = mouseDown, mouseDragged || down.clicks >= 2 else {
                onDiagnostic?("terminal-mouse up ignored reason=no-drag")
                invalidate(reason: "no-text-selection")
                return
            }
            // Codex renders tool output, messages, and its input with different
            // accessibility roles. Keep a point in the same Terminal window;
            // the ensuing fresh copy determines whether text is selected.
            let candidates = [point, lastDragPoint, down.point].compactMap { $0 }
            guard let textPoint = candidates.first(where: {
                windowAtPoint($0, ownerPID) == down.window
            }) else {
                onDiagnostic?("terminal-selection missed reason=no-terminal-window-point window=\(down.window.id)")
                invalidate(reason: "no-terminal-window-point")
                return
            }
            anchor = TerminalSelectionAnchor(window: down.window, point: textPoint, createdAt: now)
            mouseDown = nil
            mouseDragged = false
            lastDragPoint = nil
            onDiagnostic?("terminal-selection tracked window=\(down.window.id)")
        case .scrollWheel:
            // Scrolling can extend a drag or move a selected transcript through
            // the viewport without clearing the app-owned selection. Cancel an
            // in-flight copy, but preserve that gesture in its original window.
            inputRevision += 1
            guard let selectionWindow = mouseDown?.window ?? anchor?.window else { return }
            guard windowAtPoint(point, ownerPID) == selectionWindow else {
                invalidate(reason: "scroll-window-changed")
                return
            }
            if let anchor {
                guard anchor.isUsable(bundleID: "com.apple.Terminal", window: selectionWindow, now: now) else {
                    invalidate(reason: "scroll-selection-expired")
                    return
                }
                // Keep the click in the original text area, even if the pointer
                // is now over another pane. Only a fresh copy can supply text.
                self.anchor = TerminalSelectionAnchor(window: anchor.window, point: anchor.point, createdAt: now)
                onDiagnostic?("terminal-selection retained reason=scroll window=\(selectionWindow.id)")
            }
        default:
            invalidate(reason: "mouse-\(type.rawValue)")
        }
    }

    func read(from app: NSRunningApplication, completion: @escaping (Result<Selection, Error>) -> Void) {
        let revision = inputRevision
        let selectedAnchor = anchor
        onDiagnostic?("selected-text request app=\(app.bundleIdentifier ?? "unknown") anchor=\(selectedAnchor?.window.id.description ?? "none")")
        let deadline = Date().addingTimeInterval(3)
        // A right-click with Command still held has different semantics in some
        // apps. Keep the source fixed, and wait for the initiating keys to lift.
        waitForModifiers(app: app, revision: revision, deadline: deadline) { [weak self] ready in
            guard let self else { return }
            guard ready else {
                completion(.failure(Self.error("Selection changed or shortcut was held. Select the text and tap Right Command again.")))
                return
            }
            if let text = Self.accessibleSelectedText(pid: app.processIdentifier) {
                guard self.isCurrent(app: app, revision: revision) else {
                    completion(.failure(Self.error("Selection changed while reading. Try again.")))
                    return
                }
                completion(.success(Selection(text: text, method: "accessibility")))
                return
            }
            let usableAnchor = selectedAnchor.flatMap { candidate in
                candidate.isUsable(bundleID: app.bundleIdentifier,
                                   window: self.windowAtPoint(candidate.point, app.processIdentifier),
                                   now: Date())
                    ? candidate : nil
            }
            // A recorded but no longer usable Terminal selection must not send
            // input to a moved/covered window or read some unrelated clipboard.
            if selectedAnchor != nil && usableAnchor == nil {
                completion(.failure(Self.error("Terminal selection moved or expired. Highlight the text again.")))
                return
            }
            if app.bundleIdentifier == "com.apple.Terminal" && usableAnchor == nil {
                completion(.failure(Self.error("Doc Reader did not detect a Terminal text selection. Drag to highlight it again.")))
                return
            }
            guard self.isCurrent(app: app, revision: revision) else {
                completion(.failure(Self.error("Selection changed before copying. Try again.")))
                return
            }
            let transaction = SelectionClipboardTransaction(pasteboard: .general)
            let method = usableAnchor == nil ? "command-c" : "terminal-right-click"
            self.onDiagnostic?("selected-text copy app=\(app.bundleIdentifier ?? "unknown") method=\(method)")
            let posted: Bool
            if let usableAnchor {
                // Keep the anchor while the selection and window remain in place,
                // so another press can read the same highlighted passage again.
                self.expectedRightClick = (usableAnchor.point, Date().addingTimeInterval(0.5))
                posted = Self.sendRightClick(at: usableAnchor.point)
            } else {
                self.expectedCopyKeyUntil = Date().addingTimeInterval(0.5)
                posted = Self.sendCopyShortcut()
            }
            guard posted else {
                transaction.cancel()
                completion(.failure(Self.error("Could not send the copy action.")))
                return
            }
            self.pollCopy(transaction, app: app, revision: revision, method: method,
                          deadline: Date().addingTimeInterval(1.2), completion: completion)
        }
    }

    private func isCurrent(app: NSRunningApplication, revision: Int) -> Bool {
        inputRevision == revision && !app.isTerminated
            && NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier
    }

    private func waitForModifiers(app: NSRunningApplication, revision: Int, deadline: Date,
                                  completion: @escaping (Bool) -> Void) {
        guard isCurrent(app: app, revision: revision) else { completion(false); return }
        let relevant: CGEventFlags = [.maskCommand, .maskControl, .maskAlternate, .maskShift]
        let flags = CGEventSource.flagsState(.combinedSessionState).union(CGEventSource.flagsState(.hidSystemState))
        if flags.intersection(relevant).isEmpty { completion(true); return }
        guard Date() < deadline else { completion(false); return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.025) { [weak self] in
            self?.waitForModifiers(app: app, revision: revision, deadline: deadline, completion: completion)
        }
    }

    private func pollCopy(_ transaction: SelectionClipboardTransaction, app: NSRunningApplication,
                          revision: Int, method: String, deadline: Date,
                          completion: @escaping (Result<Selection, Error>) -> Void) {
        guard isCurrent(app: app, revision: revision) else {
            transaction.cancel()
            completion(.failure(Self.error("Selection changed while copying. Try again.")))
            return
        }
        if let text = transaction.takeCopiedText() {
            completion(.success(Selection(text: text, method: method)))
            return
        }
        guard Date() < deadline else {
            transaction.cancel()
            completion(.failure(Self.error("No selected text copied. Highlight the text and tap Right Command again.")))
            return
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.04) { [weak self] in
            self?.pollCopy(transaction, app: app, revision: revision, method: method,
                           deadline: deadline, completion: completion)
        }
    }

    private static func accessibleSelectedText(pid: pid_t) -> String? {
        let app = AXUIElementCreateApplication(pid)
        AXUIElementSetMessagingTimeout(app, 0.25)
        var focused: CFTypeRef?
        guard AXUIElementCopyAttributeValue(app, kAXFocusedUIElementAttribute as CFString, &focused) == .success,
              let focused, CFGetTypeID(focused) == AXUIElementGetTypeID() else { return nil }
        let element = unsafeBitCast(focused, to: AXUIElement.self)
        var selected: CFTypeRef?
        guard AXUIElementCopyAttributeValue(element, kAXSelectedTextAttribute as CFString, &selected) == .success,
              let text = selected as? String else { return nil }
        let cleaned = text.trimmingCharacters(in: .whitespacesAndNewlines)
        return cleaned.isEmpty ? nil : cleaned
    }

    private static func window(at point: CGPoint, ownerPID: pid_t) -> SelectionWindow? {
        guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
            as? [[String: Any]] else { return nil }
        for info in windows {
            guard let bounds = info[kCGWindowBounds as String] as? [String: Any],
                  let frame = CGRect(dictionaryRepresentation: bounds as CFDictionary), frame.contains(point),
                  let pid = info[kCGWindowOwnerPID as String] as? Int32,
                  pid == ownerPID,
                  let id = info[kCGWindowNumber as String] as? UInt32 else { continue }
            if let alpha = info[kCGWindowAlpha as String] as? Double, alpha == 0 { continue }
            return SelectionWindow(pid: pid, id: id, frame: frame)
        }
        return nil
    }

    private static func sendCopyShortcut() -> Bool {
        let source = CGEventSource(stateID: .privateState)
        guard let down = CGEvent(keyboardEventSource: source, virtualKey: 0x08, keyDown: true),
              let up = CGEvent(keyboardEventSource: source, virtualKey: 0x08, keyDown: false) else { return false }
        for event in [down, up] {
            event.flags = .maskCommand
            event.setIntegerValueField(.eventSourceUserData, value: eventMarker)
            event.post(tap: .cghidEventTap)
        }
        return true
    }

    private static func sendRightClick(at point: CGPoint) -> Bool {
        let source = CGEventSource(stateID: .privateState)
        guard let down = CGEvent(mouseEventSource: source, mouseType: .rightMouseDown, mouseCursorPosition: point, mouseButton: .right),
              let up = CGEvent(mouseEventSource: source, mouseType: .rightMouseUp, mouseCursorPosition: point, mouseButton: .right) else { return false }
        // Posting at the selection point also works if the pointer moved after
        // selecting. Restore its location only if the user has not moved it.
        let pointer = CGEvent(source: nil)?.location
        for event in [down, up] {
            event.flags = []
            event.setIntegerValueField(.eventSourceUserData, value: eventMarker)
            event.setIntegerValueField(.mouseEventClickState, value: 1)
            event.post(tap: .cghidEventTap)
        }
        if let pointer {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                if let current = CGEvent(source: nil)?.location,
                   hypot(current.x - point.x, current.y - point.y) <= 2 { CGWarpMouseCursorPosition(pointer) }
            }
        }
        return true
    }

    private static func error(_ message: String) -> Error {
        NSError(domain: "DocReader.SelectedText", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
    }
}
