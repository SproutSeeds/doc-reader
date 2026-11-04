import AppKit
import WebKit

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let url = URL(string: ProcessInfo.processInfo.environment["WORKSPACE_PREVIEW_URL"] ?? "http://127.0.0.1:18766")!
let controller = WorkspaceWindowController(url: url)
controller.present()
controller.loadWorkspace()
var attempts = 0
var complete = false
let timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { timer in
    guard !complete else { return }
    attempts += 1
    controller.webView.evaluateJavaScript("JSON.stringify({desktop:window.readDocsDesktop, setup:document.querySelector('#setupWizard')?.open, title:document.querySelector('#setupTitle')?.textContent, guides:document.querySelectorAll('.shortcut-guide button').length})") { result, error in
        if let value = result as? String, value.contains("\"setup\":true"), value.contains("\"desktop\":\"macos\"") {
            complete = true
            timer.invalidate()
            controller.webView.takeSnapshot(with: nil) { image, error in
                if let path = ProcessInfo.processInfo.environment["WORKSPACE_NATIVE_SCREENSHOT"], let image,
                   let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff),
                   let png = bitmap.representation(using: .png, properties: [:]) {
                    try? png.write(to: URL(fileURLWithPath: path))
                }
                print("PASS: native WKWebView window, desktop context and first-run setup: \(value)")
                app.terminate(nil)
            }
        } else if attempts > 80 {
            fputs("FAIL: native workspace did not become ready: \(String(describing: result)) \(String(describing: error))\n", stderr)
            exit(1)
        }
    }
}
app.run()
