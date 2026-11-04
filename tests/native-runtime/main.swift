import Foundation

let arguments = CommandLine.arguments
guard arguments.count == 3 else { fatalError("Expected Python executable and source root") }
let python = arguments[1]
let source = URL(fileURLWithPath: arguments[2]).standardizedFileURL
let legacy = FileManager.default.temporaryDirectory.appendingPathComponent("read-docs-legacy-\(UUID().uuidString)")
let stalePackage = legacy.appendingPathComponent("doc_reader")
try FileManager.default.createDirectory(at: stalePackage, withIntermediateDirectories: true)
defer { try? FileManager.default.removeItem(at: legacy) }
try "raise RuntimeError('Loaded obsolete npm code from the user profile')\n".write(
    to: stalePackage.appendingPathComponent("__init__.py"), atomically: true, encoding: .utf8)
let process = Process()
process.executableURL = URL(fileURLWithPath: python)
process.arguments = ["-c", "import doc_reader; from pathlib import Path; import sys; assert Path(doc_reader.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())", source.path]
process.currentDirectoryURL = legacy
var environment = DesktopRuntime.environment(managedRoot: legacy)
environment["PYTHONPATH"] = source.path
process.environment = environment
try process.run()
process.waitUntilExit()
guard process.terminationStatus == 0 else { fatalError("Legacy profile shadowed the selected runtime") }
print("PASS: native runtime imports shipped code even with obsolete source in the user profile")
