import AVFoundation
import Foundation
import Darwin

// The meter reads the same mono PCM stream that is written to the recording.
final class PCM16LevelMeter {
    private let lock = NSLock()
    private var pendingByte: UInt8?
    private var peak = 0.0

    var peakLevel: Double {
        lock.lock()
        defer { lock.unlock() }
        return peak
    }

    func consume(_ data: Data) -> Double {
        lock.lock()
        defer { lock.unlock() }
        var level = 0.0
        for byte in data {
            if let low = pendingByte {
                let sample = Int16(bitPattern: UInt16(low) | (UInt16(byte) << 8))
                level = max(level, abs(Double(sample)) / 32768.0)
                pendingByte = nil
            } else {
                pendingByte = byte
            }
        }
        peak = max(peak, level)
        return level
    }
}

final class DictationAudioRecorder {
    let url: URL
    let contentType = "audio/wav"
    var onAudioLevel: ((Double) -> Void)?
    var onFailure: ((Error) -> Void)?
    private(set) var isRecording = false
    var peakLevel: Double { meter.peakLevel }

    private let ffmpegURL: URL
    private let inputArguments: [String]
    private let meter = PCM16LevelMeter()
    private let readers = DispatchGroup()
    private var process: Process?
    private var stdinPipe: Pipe?
    private var finished = false
    private var finishing = false
    private var finishError: Error?
    private var stopCompletion: ((URL, Error?) -> Void)?
    private var stderr = Data()

    convenience init(device: AVCaptureDevice, url: URL) throws {
        try self.init(inputArguments: ["-f", "avfoundation", "-i", ":\(device.localizedName)"], url: url)
    }

    // An explicit input makes the actual capture/finalization path testable with
    // FFmpeg's synthetic sources, without opening a physical microphone.
    init(inputArguments: [String], url: URL, executableURL: URL? = nil) throws {
        guard let executable = executableURL ?? Self.ffmpegExecutableURL() else {
            throw Self.error("ffmpeg is required for microphone recording.")
        }
        self.ffmpegURL = executable
        self.inputArguments = inputArguments
        self.url = url
    }

    func start() -> Bool {
        guard process == nil else { return false }
        let inputPipe = Pipe()
        let outputPipe = Pipe()
        let errorPipe = Pipe()
        let child = Process()
        child.executableURL = ffmpegURL
        child.arguments = ["-hide_banner", "-loglevel", "error", "-y"] + inputArguments + [
            "-filter_complex",
            "[0:a]aformat=sample_fmts=s16:sample_rates=16000:channel_layouts=mono,asplit=2[recording][meter]",
            "-map", "[recording]", "-acodec", "pcm_s16le", "-f", "wav", url.path,
            "-map", "[meter]", "-acodec", "pcm_s16le", "-f", "s16le", "pipe:1",
        ]
        child.standardInput = inputPipe
        child.standardOutput = outputPipe
        child.standardError = errorPipe
        // Register before run(): an unavailable/disconnected input can exit at once.
        readers.enter()
        readers.enter()
        child.terminationHandler = { [weak self] child in
            guard let self else { return }
            self.readers.notify(queue: .main) { self.processDidFinish(child) }
        }
        do {
            try child.run()
        } catch {
            readers.leave()
            readers.leave()
            child.terminationHandler = nil
            finishError = error
            return false
        }
        process = child
        stdinPipe = inputPipe
        isRecording = true
        DispatchQueue.global(qos: .userInitiated).async { [self] in
            defer {
                try? outputPipe.fileHandleForReading.close()
                readers.leave()
            }
            while let data = try? outputPipe.fileHandleForReading.read(upToCount: 4096), !data.isEmpty {
                let level = meter.consume(data)
                DispatchQueue.main.async { [weak self] in
                    guard let self, self.isRecording else { return }
                    self.onAudioLevel?(level)
                }
            }
        }
        DispatchQueue.global(qos: .utility).async { [self] in
            defer {
                try? errorPipe.fileHandleForReading.close()
                readers.leave()
            }
            while let data = try? errorPipe.fileHandleForReading.read(upToCount: 4096), !data.isEmpty {
                stderr.append(data)
                // Drain the pipe continuously; a noisy failure must not deadlock.
                if stderr.count > 16384 { stderr = Data(stderr.suffix(16384)) }
            }
        }
        return true
    }

    func stop(completion: @escaping (URL, Error?) -> Void) {
        guard !finishing else { return }
        finishing = true
        isRecording = false
        stopCompletion = completion
        if finished {
            deliverStop()
            return
        }
        guard let child = process else {
            finishError = finishError ?? Self.error("Recorder process was not running.")
            finished = true
            deliverStop()
            return
        }
        if child.isRunning {
            try? stdinPipe?.fileHandleForWriting.write(contentsOf: Data("q\n".utf8))
            try? stdinPipe?.fileHandleForWriting.close()
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { [weak child] in
            guard let child, child.isRunning else { return }
            child.interrupt()
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 5) { [weak self, weak child] in
            guard let child, child.isRunning else { return }
            self?.finishError = Self.error("Recording finalization timed out.")
            kill(child.processIdentifier, SIGKILL)
        }
    }

    private func processDidFinish(_ child: Process) {
        guard !finished else { return }
        finished = true
        isRecording = false
        child.terminationHandler = nil
        let size = (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? NSNumber)?.int64Value ?? 0
        let detail = String(data: stderr, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !finishing || child.terminationStatus != 0 || size <= 44 {
            finishError = finishError ?? Self.error(detail.isEmpty ? "Microphone recording ended before usable audio was captured." : detail)
        }
        if finishing {
            deliverStop()
        } else if let finishError {
            onFailure?(finishError)
        }
    }

    private func deliverStop() {
        guard let completion = stopCompletion else { return }
        stopCompletion = nil
        completion(url, finishError)
    }

    private static func ffmpegExecutableURL() -> URL? {
        let paths = (ProcessInfo.processInfo.environment["PATH"] ?? "")
            .split(separator: ":").map { String($0) + "/ffmpeg" }
        return (paths + ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"])
            .first { FileManager.default.isExecutableFile(atPath: $0) }
            .map { URL(fileURLWithPath: $0) }
    }

    private static func error(_ message: String) -> NSError {
        NSError(domain: "com.sproutseeds.read-docs.dictation", code: 1,
                userInfo: [NSLocalizedDescriptionKey: message])
    }
}
