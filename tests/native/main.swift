import Foundation

func require(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() {
        fputs("FAIL: \(message)\n", stderr)
        exit(1)
    }
}

func waitUntil(_ message: String, timeout: TimeInterval = 8, condition: () -> Bool) {
    let deadline = Date().addingTimeInterval(timeout)
    while !condition() && Date() < deadline {
        RunLoop.current.run(until: Date().addingTimeInterval(0.02))
    }
    require(condition(), message)
}

let meter = PCM16LevelMeter()
require(meter.consume(Data([0])) == 0, "odd PCM byte waits for its pair")
require(meter.consume(Data([128])) == 1, "signed -32768 sample is measured without overflow")
require(meter.consume(Data([0, 0, 0, 64])) == 0.5, "current peak uses real samples")
require(meter.peakLevel == 1, "recording peak survives silent buffers")

let directory = FileManager.default.temporaryDirectory.appendingPathComponent("doc-reader-native-test-\(UUID().uuidString)")
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
defer { try? FileManager.default.removeItem(at: directory) }

func capture(_ name: String, source: String, expectSignal: Bool) throws {
    let output = directory.appendingPathComponent(name + ".wav")
    let recorder = try DictationAudioRecorder(inputArguments: ["-re", "-f", "lavfi", "-i", source], url: output)
    var levels: [Double] = []
    var failure: Error?
    recorder.onAudioLevel = { levels.append($0) }
    recorder.onFailure = { failure = $0 }
    require(recorder.start(), "\(name): process starts")
    waitUntil("\(name): actual samples reach the meter") { levels.count >= 3 || failure != nil }
    require(failure == nil, "\(name): capture stays alive: \(String(describing: failure))")
    var callbacks = 0
    var finishError: Error?
    recorder.stop { _, error in callbacks += 1; finishError = error }
    recorder.stop { _, _ in callbacks += 1 }
    waitUntil("\(name): recorder finalizes") { callbacks > 0 }
    require(callbacks == 1, "\(name): completion is delivered once")
    require(finishError == nil, "\(name): WAV finalization succeeds: \(String(describing: finishError))")
    require(!recorder.isRecording, "\(name): recording state clears")
    let data = try Data(contentsOf: output)
    require(data.count > 44 && String(data: data.prefix(4), encoding: .ascii) == "RIFF", "\(name): a WAV with samples is saved")
    if expectSignal {
        require(recorder.peakLevel > 0.005 && levels.contains(where: { $0 > 0.005 }), "\(name): real signal reaches saved and live peaks")
    } else {
        require(recorder.peakLevel == 0 && levels.allSatisfy { $0 == 0 }, "\(name): silence stays zero")
    }
    print("PASS: \(name), \(data.count) bytes, peak \(recorder.peakLevel)")
}

try capture("sine", source: "sine=frequency=440:sample_rate=48000", expectSignal: true)
try capture("silence", source: "anullsrc=r=16000:cl=mono", expectSignal: false)
try capture("right-channel-only", source: "aevalsrc=0|0.2*sin(2*PI*440*t):s=48000", expectSignal: true)

let broken = try DictationAudioRecorder(inputArguments: [], url: directory.appendingPathComponent("failure.wav"), executableURL: URL(fileURLWithPath: "/usr/bin/false"))
var failure: Error?
broken.onFailure = { failure = $0 }
require(broken.start(), "failed input can initially launch")
waitUntil("early recorder exit surfaces without requiring Stop") { failure != nil }
require(!broken.isRecording, "early exit clears recording state")
var callbacks = 0
broken.stop { _, error in
    require(error != nil, "stopping an exited recorder retains its failure")
    callbacks += 1
}
require(callbacks == 1, "exited recorder completes once")
print("PASS: early process failure and stop recovery")
