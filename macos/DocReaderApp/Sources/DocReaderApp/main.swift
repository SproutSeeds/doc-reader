import AppKit
import Foundation
import Security
import UniformTypeIdentifiers

private enum KeychainStore {
    static let service = "com.sproutseeds.read-docs"
    static let elevenLabsAccount = "elevenlabs-api-key"

    static func password(account: String) -> String {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else {
            return ""
        }
        return String(data: data, encoding: .utf8) ?? ""
    }

    static func setPassword(_ value: String, account: String) {
        let baseQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]

        if value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            SecItemDelete(baseQuery as CFDictionary)
            return
        }

        let data = Data(value.utf8)
        let updateStatus = SecItemUpdate(
            baseQuery as CFDictionary,
            [kSecValueData as String: data] as CFDictionary
        )
        if updateStatus == errSecSuccess {
            return
        }

        var addQuery = baseQuery
        addQuery[kSecValueData as String] = data
        SecItemAdd(addQuery as CFDictionary, nil)
    }
}

private struct ReaderPreferences {
    private static let defaults = UserDefaults.standard
    private static let legacyDefaults = UserDefaults(suiteName: "com.DocReader.DocReader")

    static var mode: String {
        let value = defaults.string(forKey: "reader.mode") ?? "full"
        return ["smart", "full"].contains(value) ? value : "full"
    }

    static var speechBackend: String {
        let value = defaults.string(forKey: "speech.backend") ?? "macsay"
        return ["macsay", "elevenlabs"].contains(value) ? value : "macsay"
    }

    static var elevenLabsVoiceID: String {
        defaults.string(forKey: "elevenlabs.voice_id") ?? ""
    }

    static var elevenLabsVoiceName: String {
        defaults.string(forKey: "elevenlabs.voice_name") ?? ""
    }

    static var elevenLabsAPIKey: String {
        let storedKey = KeychainStore.password(account: KeychainStore.elevenLabsAccount)
        if !storedKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return storedKey
        }
        return legacyString(forKeys: ["elevenlabs.api_key", "elevenlabs/api_key"])
    }

    static func save(mode: String, backend: String, voiceID: String, voiceName: String, apiKey: String) {
        defaults.set(mode, forKey: "reader.mode")
        defaults.set(backend, forKey: "speech.backend")
        defaults.set(voiceID, forKey: "elevenlabs.voice_id")
        defaults.set(voiceName, forKey: "elevenlabs.voice_name")
        KeychainStore.setPassword(apiKey, account: KeychainStore.elevenLabsAccount)
    }

    static func migrateLegacySettingsIfNeeded() {
        let existingKey = KeychainStore.password(account: KeychainStore.elevenLabsAccount)
        let legacyKey = legacyString(forKeys: ["elevenlabs.api_key", "elevenlabs/api_key"])
        if existingKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
           !legacyKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            KeychainStore.setPassword(legacyKey, account: KeychainStore.elevenLabsAccount)
        }

        if defaults.string(forKey: "speech.backend") == nil {
            let backend = legacyString(forKeys: ["voice.backend", "voice/backend"])
            if ["macsay", "pyttsx3", "elevenlabs"].contains(backend) {
                defaults.set(backend == "pyttsx3" ? "macsay" : backend, forKey: "speech.backend")
            }
        }

        if defaults.string(forKey: "elevenlabs.voice_id") == nil {
            let voiceID = legacyString(forKeys: ["voice.value", "voice/value"])
            if !voiceID.isEmpty {
                defaults.set(voiceID, forKey: "elevenlabs.voice_id")
                defaults.set(voiceID, forKey: "elevenlabs.voice_name")
            }
        }
    }

    private static func legacyString(forKeys keys: [String]) -> String {
        for key in keys {
            if let value = legacyDefaults?.string(forKey: key)?.trimmingCharacters(in: .whitespacesAndNewlines),
               !value.isEmpty {
                return value
            }
        }

        let plistURL = URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent("Library/Preferences/com.DocReader.DocReader.plist")
        guard let dictionary = NSDictionary(contentsOf: plistURL) as? [String: Any] else {
            return ""
        }

        for key in keys {
            if let value = dictionary[key] as? String {
                let cleaned = value.trimmingCharacters(in: .whitespacesAndNewlines)
                if !cleaned.isEmpty {
                    return cleaned
                }
            }
        }
        return ""
    }
}

private func configureDocumentPanel(_ panel: NSOpenPanel) {
    panel.allowedContentTypes = ["pdf", "docx", "txt", "md", "markdown"].compactMap {
        UTType(filenameExtension: $0)
    }
    panel.allowsMultipleSelection = false
    panel.canChooseDirectories = false
}

private final class ReaderEngine: NSObject {
    private var process: Process?
    private let managedRoot = URL(fileURLWithPath: NSHomeDirectory())
        .appendingPathComponent(".doc-reader-managed", isDirectory: true)

    var onStatus: ((String) -> Void)?
    var isRunning: Bool {
        process?.isRunning ?? false
    }

    private var venvURL: URL {
        if let value = ProcessInfo.processInfo.environment["DOC_READER_VENV_DIR"], !value.isEmpty {
            return URL(fileURLWithPath: value, isDirectory: true)
        }
        return managedRoot.appendingPathComponent(".venv", isDirectory: true)
    }

    private var pythonURL: URL {
        venvURL.appendingPathComponent("bin/python")
    }

    var serviceInboxURL: URL {
        managedRoot.appendingPathComponent("service-inbox", isDirectory: true)
    }

    func readText(_ text: String) {
        let cleaned = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else {
            onStatus?("No text to read.")
            return
        }

        let runtimeDir = managedRoot.appendingPathComponent("runtime", isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: runtimeDir, withIntermediateDirectories: true)
            let file = runtimeDir.appendingPathComponent("inline-\(UUID().uuidString).txt")
            try cleaned.write(to: file, atomically: true, encoding: .utf8)
            readFile(file)
        } catch {
            onStatus?("Could not prepare text: \(error.localizedDescription)")
        }
    }

    func readFile(_ file: URL) {
        if isRunning {
            stop()
        }

        guard FileManager.default.isExecutableFile(atPath: pythonURL.path) else {
            onStatus?("Reader environment missing. Run read-docs install.")
            return
        }

        var args = [
            "-m",
            "doc_reader",
            file.path,
            "--mode",
            ReaderPreferences.mode,
            "--style",
            "balanced",
            "--rate",
            "180",
            "--speech-backend",
            effectiveBackend(),
            "--verbose",
        ]

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONPATH"] = managedRoot.path

        if effectiveBackend() == "elevenlabs" {
            let voiceID = ReaderPreferences.elevenLabsVoiceID.trimmingCharacters(in: .whitespacesAndNewlines)
            let apiKey = ReaderPreferences.elevenLabsAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
            if !voiceID.isEmpty {
                args.append(contentsOf: ["--elevenlabs-voice-id", voiceID])
            }
            if !apiKey.isEmpty {
                environment["ELEVENLABS_API_KEY"] = apiKey
            }
        }

        let task = Process()
        task.executableURL = pythonURL
        task.arguments = args
        task.currentDirectoryURL = managedRoot
        task.environment = environment

        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else {
                return
            }
            let line = text
                .split(whereSeparator: \.isNewline)
                .last
                .map(String.init) ?? text.trimmingCharacters(in: .whitespacesAndNewlines)
            if !line.isEmpty {
                DispatchQueue.main.async {
                    self?.onStatus?(line)
                }
            }
        }

        task.terminationHandler = { [weak self] finished in
            pipe.fileHandleForReading.readabilityHandler = nil
            DispatchQueue.main.async {
                self?.process = nil
                self?.onStatus?(finished.terminationStatus == 0 ? "Ready." : "Reader stopped.")
            }
        }

        do {
            try task.run()
            process = task
            onStatus?("Reading \(file.lastPathComponent)")
        } catch {
            onStatus?("Could not start reader: \(error.localizedDescription)")
        }
    }

    func stop() {
        guard let task = process else {
            return
        }

        let pid = task.processIdentifier
        _ = Process.launchedProcess(launchPath: "/usr/bin/pkill", arguments: ["-TERM", "-P", "\(pid)"])
        task.terminate()

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
            guard task.isRunning else {
                return
            }
            _ = Process.launchedProcess(launchPath: "/usr/bin/pkill", arguments: ["-KILL", "-P", "\(pid)"])
            task.interrupt()
        }
    }

    private func effectiveBackend() -> String {
        if ReaderPreferences.speechBackend == "elevenlabs",
           !ReaderPreferences.elevenLabsAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
           !ReaderPreferences.elevenLabsVoiceID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "elevenlabs"
        }
        return "macsay"
    }
}

private final class ReaderWindowController: NSWindowController {
    private let engine: ReaderEngine
    private let textView = NSTextView()
    private let statusLabel = NSTextField(labelWithString: "Ready.")

    init(engine: ReaderEngine) {
        self.engine = engine

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 520, height: 390),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Doc Reader"
        window.isReleasedWhenClosed = false
        super.init(window: window)
        buildUI()
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private func buildUI() {
        guard let contentView = window?.contentView else {
            return
        }

        let stack = NSStackView()
        stack.orientation = .vertical
        stack.spacing = 12
        stack.edgeInsets = NSEdgeInsets(top: 16, left: 16, bottom: 16, right: 16)
        stack.translatesAutoresizingMaskIntoConstraints = false

        let scrollView = NSScrollView()
        scrollView.hasVerticalScroller = true
        scrollView.borderType = .bezelBorder
        scrollView.documentView = textView
        textView.font = NSFont.systemFont(ofSize: 14)
        textView.string = ""
        scrollView.heightAnchor.constraint(equalToConstant: 220).isActive = true

        let buttonRow = NSStackView()
        buttonRow.orientation = .horizontal
        buttonRow.spacing = 8

        let browseButton = NSButton(title: "Choose Document", target: self, action: #selector(chooseDocument))
        let readTextButton = NSButton(title: "Read Text", target: self, action: #selector(readText))
        let clipboardButton = NSButton(title: "Read Clipboard", target: self, action: #selector(readClipboard))
        let stopButton = NSButton(title: "Stop", target: self, action: #selector(stopReading))

        for button in [browseButton, readTextButton, clipboardButton, stopButton] {
            button.bezelStyle = .rounded
            buttonRow.addArrangedSubview(button)
        }

        statusLabel.lineBreakMode = .byTruncatingTail
        statusLabel.maximumNumberOfLines = 2

        stack.addArrangedSubview(NSTextField(labelWithString: "Paste text or choose a document to read."))
        stack.addArrangedSubview(scrollView)
        stack.addArrangedSubview(buttonRow)
        stack.addArrangedSubview(statusLabel)

        contentView.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            stack.topAnchor.constraint(equalTo: contentView.topAnchor),
            stack.bottomAnchor.constraint(equalTo: contentView.bottomAnchor),
        ])

        engine.onStatus = { [weak self] status in
            self?.statusLabel.stringValue = status
        }
    }

    func show() {
        showWindow(nil)
        window?.center()
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc private func chooseDocument() {
        let panel = NSOpenPanel()
        configureDocumentPanel(panel)
        panel.begin { [weak self] response in
            guard response == .OK, let url = panel.url else {
                return
            }
            self?.engine.readFile(url)
        }
    }

    @objc private func readText() {
        engine.readText(textView.string)
    }

    @objc private func readClipboard() {
        let text = NSPasteboard.general.string(forType: .string) ?? ""
        engine.readText(text)
    }

    @objc private func stopReading() {
        engine.stop()
    }
}

private struct ElevenLabsVoicesResponse: Decodable {
    let voices: [ElevenLabsVoice]
}

private struct ElevenLabsVoice: Decodable {
    let voiceID: String
    let name: String

    private enum CodingKeys: String, CodingKey {
        case voiceID = "voice_id"
        case name
    }
}

private final class PreferencesWindowController: NSWindowController {
    private let modePopup = NSPopUpButton()
    private let backendPopup = NSPopUpButton()
    private let apiKeyField = NSSecureTextField()
    private let voicePopup = NSPopUpButton()
    private let statusLabel = NSTextField(labelWithString: "")

    init() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 480, height: 250),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = "Doc Reader Settings"
        window.isReleasedWhenClosed = false
        super.init(window: window)
        buildUI()
        loadStoredValues()
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private func buildUI() {
        guard let contentView = window?.contentView else {
            return
        }

        let stack = NSStackView()
        stack.orientation = .vertical
        stack.spacing = 10
        stack.edgeInsets = NSEdgeInsets(top: 16, left: 16, bottom: 16, right: 16)
        stack.translatesAutoresizingMaskIntoConstraints = false

        modePopup.addItems(withTitles: ["Full Reading", "Smart Summary"])
        backendPopup.addItems(withTitles: ["System Voice", "ElevenLabs"])
        apiKeyField.placeholderString = "ElevenLabs API key"
        voicePopup.addItem(withTitle: "No ElevenLabs voice selected")

        let loadButton = NSButton(title: "Load Voices", target: self, action: #selector(loadVoices))
        let saveButton = NSButton(title: "Save", target: self, action: #selector(savePreferences))

        stack.addArrangedSubview(row(label: "Mode", control: modePopup))
        stack.addArrangedSubview(row(label: "Speech", control: backendPopup))
        stack.addArrangedSubview(row(label: "API Key", control: apiKeyField))
        stack.addArrangedSubview(row(label: "Voice", control: voicePopup))

        let buttons = NSStackView()
        buttons.orientation = .horizontal
        buttons.spacing = 8
        buttons.addArrangedSubview(loadButton)
        buttons.addArrangedSubview(saveButton)
        stack.addArrangedSubview(buttons)
        stack.addArrangedSubview(statusLabel)

        contentView.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            stack.topAnchor.constraint(equalTo: contentView.topAnchor),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: contentView.bottomAnchor),
        ])
    }

    private func row(label: String, control: NSView) -> NSStackView {
        let stack = NSStackView()
        stack.orientation = .horizontal
        stack.spacing = 12
        let text = NSTextField(labelWithString: label)
        text.widthAnchor.constraint(equalToConstant: 80).isActive = true
        control.widthAnchor.constraint(greaterThanOrEqualToConstant: 280).isActive = true
        stack.addArrangedSubview(text)
        stack.addArrangedSubview(control)
        return stack
    }

    private func loadStoredValues() {
        modePopup.selectItem(at: ReaderPreferences.mode == "smart" ? 1 : 0)
        backendPopup.selectItem(at: ReaderPreferences.speechBackend == "elevenlabs" ? 1 : 0)
        apiKeyField.stringValue = ReaderPreferences.elevenLabsAPIKey

        let voiceID = ReaderPreferences.elevenLabsVoiceID
        let voiceName = ReaderPreferences.elevenLabsVoiceName
        if !voiceID.isEmpty {
            voicePopup.removeAllItems()
            voicePopup.addItem(withTitle: voiceName.isEmpty ? voiceID : voiceName)
            voicePopup.lastItem?.representedObject = voiceID
        }
    }

    func show() {
        showWindow(nil)
        window?.center()
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc private func loadVoices() {
        let apiKey = apiKeyField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !apiKey.isEmpty else {
            statusLabel.stringValue = "Enter an ElevenLabs API key first."
            return
        }

        var components = URLComponents(string: "https://api.elevenlabs.io/v2/voices")!
        components.queryItems = [
            URLQueryItem(name: "page_size", value: "50"),
            URLQueryItem(name: "include_total_count", value: "false"),
        ]
        var request = URLRequest(url: components.url!)
        request.addValue(apiKey, forHTTPHeaderField: "xi-api-key")
        request.addValue("application/json", forHTTPHeaderField: "Accept")

        statusLabel.stringValue = "Loading voices..."
        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self?.statusLabel.stringValue = "Voice load failed: \(error.localizedDescription)"
                    return
                }
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode),
                      let data = data else {
                    self?.statusLabel.stringValue = "Voice load failed."
                    return
                }
                do {
                    let decoded = try JSONDecoder().decode(ElevenLabsVoicesResponse.self, from: data)
                    self?.voicePopup.removeAllItems()
                    for voice in decoded.voices.sorted(by: { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }) {
                        self?.voicePopup.addItem(withTitle: voice.name)
                        self?.voicePopup.lastItem?.representedObject = voice.voiceID
                    }
                    self?.statusLabel.stringValue = decoded.voices.isEmpty ? "No voices returned." : "Loaded \(decoded.voices.count) voices."
                } catch {
                    self?.statusLabel.stringValue = "Could not parse voice list."
                }
            }
        }.resume()
    }

    @objc private func savePreferences() {
        let mode = modePopup.indexOfSelectedItem == 1 ? "smart" : "full"
        let backend = backendPopup.indexOfSelectedItem == 1 ? "elevenlabs" : "macsay"
        let voiceID = voicePopup.selectedItem?.representedObject as? String ?? ""
        let voiceName = voicePopup.selectedItem?.title ?? ""
        ReaderPreferences.save(
            mode: mode,
            backend: backend,
            voiceID: voiceID,
            voiceName: voiceName,
            apiKey: apiKeyField.stringValue
        )
        statusLabel.stringValue = "Saved."
    }
}

private final class AppDelegate: NSObject, NSApplicationDelegate {
    private let engine = ReaderEngine()
    private var statusItem: NSStatusItem?
    private var readerWindow: ReaderWindowController?
    private var preferencesWindow: PreferencesWindowController?
    private var serviceTimer: Timer?
    private let statusMenuItem = NSMenuItem(title: "Ready.", action: nil, keyEquivalent: "")

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        ReaderPreferences.migrateLegacySettingsIfNeeded()
        engine.onStatus = { [weak self] status in
            self?.statusMenuItem.title = status
        }
        FileManager.default.createDirectoryIfNeeded(at: engine.serviceInboxURL)
        buildMenu()
        serviceTimer = Timer.scheduledTimer(
            timeInterval: 0.6,
            target: self,
            selector: #selector(drainServiceInbox),
            userInfo: nil,
            repeats: true
        )
    }

    private func buildMenu() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        statusItem = item
        item.button?.image = NSImage(systemSymbolName: "doc.text.fill", accessibilityDescription: "Doc Reader")
        item.button?.imagePosition = .imageOnly

        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open Doc Reader", action: #selector(openReader), keyEquivalent: "o"))
        menu.addItem(NSMenuItem(title: "Choose Document...", action: #selector(chooseDocument), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Read Clipboard", action: #selector(readClipboard), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Stop Reading", action: #selector(stopReading), keyEquivalent: ""))
        menu.addItem(.separator())
        statusMenuItem.isEnabled = false
        menu.addItem(statusMenuItem)
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Settings...", action: #selector(openSettings), keyEquivalent: ","))
        menu.addItem(NSMenuItem(title: "Quit", action: #selector(quit), keyEquivalent: "q"))

        for menuItem in menu.items where menuItem.action != nil {
            menuItem.target = self
        }
        item.menu = menu
    }

    @objc private func openReader() {
        if readerWindow == nil {
            readerWindow = ReaderWindowController(engine: engine)
        }
        readerWindow?.show()
    }

    @objc private func openSettings() {
        if preferencesWindow == nil {
            preferencesWindow = PreferencesWindowController()
        }
        preferencesWindow?.show()
    }

    @objc private func chooseDocument() {
        let panel = NSOpenPanel()
        configureDocumentPanel(panel)
        panel.begin { [weak self] response in
            guard response == .OK, let url = panel.url else {
                return
            }
            self?.engine.readFile(url)
        }
    }

    @objc private func readClipboard() {
        let text = NSPasteboard.general.string(forType: .string) ?? ""
        engine.readText(text)
    }

    @objc private func stopReading() {
        engine.stop()
    }

    @objc private func quit() {
        engine.stop()
        NSApp.terminate(nil)
    }

    @objc private func drainServiceInbox() {
        guard !engine.isRunning else {
            return
        }

        let files = (try? FileManager.default.contentsOfDirectory(
            at: engine.serviceInboxURL,
            includingPropertiesForKeys: [.contentModificationDateKey],
            options: [.skipsHiddenFiles]
        ))?.filter { $0.pathExtension == "txt" } ?? []

        guard let latest = files.max(by: { lhs, rhs in
            let lhsDate = (try? lhs.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            let rhsDate = (try? rhs.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            return lhsDate < rhsDate
        }) else {
            return
        }

        for file in files where file != latest {
            try? FileManager.default.removeItem(at: file)
        }

        let text = (try? String(contentsOf: latest, encoding: .utf8)) ?? ""
        try? FileManager.default.removeItem(at: latest)
        engine.readText(text)
    }
}

private extension FileManager {
    func createDirectoryIfNeeded(at url: URL) {
        try? createDirectory(at: url, withIntermediateDirectories: true)
    }
}

private let app = NSApplication.shared
private let delegate = AppDelegate()
app.delegate = delegate
app.run()
