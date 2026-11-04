import Foundation

/// A downloaded app carries its own Python and packages. npm installations
/// continue to use their managed environment.
enum DesktopRuntime {
    static var python: URL? {
        guard let resources = Bundle.main.resourceURL else { return nil }
        let candidate = resources.appendingPathComponent("runtime/bin/python3")
        return FileManager.default.isExecutableFile(atPath: candidate.path) ? candidate : nil
    }

    static func environment(managedRoot: URL) -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        env["DOC_READER_MANAGED_ROOT"] = managedRoot.path
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if let python {
            env["PYTHONPATH"] = python.deletingLastPathComponent().deletingLastPathComponent()
                .appendingPathComponent("lib/python3.11/site-packages").path
            env["DOC_READER_TTS_DEVICE"] = "cpu"
            env["DOC_READER_STT_MODEL"] = "base"
            env["DOC_READER_STT_COMPUTE_TYPE"] = "int8"
            env["DOC_READER_TTS_ENGINES"] = "kokoro,whisper"
        }
        return env
    }
}
