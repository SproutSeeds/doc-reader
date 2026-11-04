import AppKit
import WebKit

/// The installed app owns a window; loopback is an implementation detail.
final class WorkspaceWindowController: NSWindowController, WKNavigationDelegate, WKUIDelegate {
    private let workspaceURL: URL
    let webView: WKWebView
    var permissionAction: ((String) -> Void)?

    init(url: URL) {
        workspaceURL = url
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.addUserScript(WKUserScript(
            source: "window.readDocsDesktop = 'macos';", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        webView = WKWebView(frame: .zero, configuration: configuration)
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1000, height: 780),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Read Docs"
        window.minSize = NSSize(width: 520, height: 520)
        window.setFrameAutosaveName("ReadDocsWorkspace")
        window.center()
        window.contentView = webView
        super.init(window: window)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        showLoading()
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    func present() {
        NSApp.setActivationPolicy(.regular)
        showWindow(nil)
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func loadWorkspace() {
        if webView.url?.host == workspaceURL.host && webView.url?.port == workspaceURL.port { return }
        webView.load(URLRequest(url: workspaceURL))
    }

    private func showLoading(error: Bool = false) {
        let title = error ? "Let’s try again." : "Read Docs"
        let action = error ? "<a href='\(workspaceURL.absoluteString)'>Retry</a>" : "<p>Opening your workspace…</p>"
        webView.loadHTMLString("<html><meta name='color-scheme' content='light dark'><style>body{font:17px system-ui;display:grid;place-content:center;height:90vh;text-align:center}h1{font:52px Georgia;font-weight:400}a{color:inherit;padding:16px}p{opacity:.65}</style><h1>\(title)</h1>\(action)</html>", baseURL: nil)
    }

    private func isWorkspace(_ url: URL?) -> Bool {
        guard let url else { return false }
        return url.scheme == workspaceURL.scheme && url.host == workspaceURL.host && url.port == workspaceURL.port
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if isWorkspace(url) || url.absoluteString == "about:blank" {
            decisionHandler(.allow)
            return
        }
        if action.sourceFrame.isMainFrame && isWorkspace(action.sourceFrame.request.url) {
            if url.scheme == "read-docs", url.host == "permission",
               ["/microphone", "/accessibility", "/input"].contains(url.path) {
                permissionAction?(String(url.path.dropFirst()))
            } else if action.navigationType == .linkActivated && ["https", "http"].contains(url.scheme ?? "") {
                NSWorkspace.shared.open(url)
            }
        }
        decisionHandler(.cancel)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        if (error as NSError).code != NSURLErrorCancelled { showLoading(error: true) }
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        guard isWorkspace(frame.request.url), let window else { completionHandler(nil); return }
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.beginSheetModal(for: window) { response in completionHandler(response == .OK ? panel.urls : nil) }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        guard isWorkspace(frame.request.url), let window else { completionHandler(false); return }
        let alert = NSAlert()
        alert.messageText = message
        alert.addButton(withTitle: "Discard")
        alert.addButton(withTitle: "Keep editing")
        alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn) }
    }
}
