import ARKit
import AVFoundation
import CoreImage
import Foundation

/// Writes the walk to an H.264 file from the frames RoomPlan's own ARSession is already
/// producing. It never starts a second camera session: two AVCaptureSessions on one camera is
/// the classic way to get a black preview and a thermal spike.
final class WalkthroughRecorder {
    enum RecorderError: LocalizedError {
        case couldNotStart(String)
        var errorDescription: String? {
            switch self {
            case .couldNotStart(let why): return "The recording could not start: \(why)"
            }
        }
    }

    private let size = CGSize(width: 1280, height: 960)
    private let queue = DispatchQueue(label: "app.shltr.recorder")
    private let context = CIContext()

    private var writer: AVAssetWriter?
    private var input: AVAssetWriterInput?
    private var adaptor: AVAssetWriterInputPixelBufferAdaptor?
    private var started = false
    private var firstFrameTime: CMTime?
    private var lastWritten = CMTime.negativeInfinity
    private(set) var outputURL: URL?

    /// Frames per second we aim for. Dropped to `thermalFPS` when the phone starts to struggle,
    /// because a throttled phone drops tracking, and tracking is what the measurement rests on.
    private let normalFPS: Double = 15
    private let thermalFPS: Double = 10
    private var targetFPS: Double {
        switch ProcessInfo.processInfo.thermalState {
        case .serious, .critical: return thermalFPS
        default: return normalFPS
        }
    }

    func start() throws {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("walkthrough-\(UUID().uuidString).mp4")
        let writer: AVAssetWriter
        do {
            writer = try AVAssetWriter(outputURL: url, fileType: .mp4)
        } catch {
            throw RecorderError.couldNotStart(error.localizedDescription)
        }
        let settings: [String: Any] = [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: size.width,
            AVVideoHeightKey: size.height,
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: 6_000_000,
                AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
            ],
        ]
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
        input.expectsMediaDataInRealTime = true
        let adaptor = AVAssetWriterInputPixelBufferAdaptor(
            assetWriterInput: input,
            sourcePixelBufferAttributes: [
                kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
                kCVPixelBufferWidthKey as String: size.width,
                kCVPixelBufferHeightKey as String: size.height,
            ])
        guard writer.canAdd(input) else { throw RecorderError.couldNotStart("the video track was refused") }
        writer.add(input)
        guard writer.startWriting() else {
            throw RecorderError.couldNotStart(writer.error?.localizedDescription ?? "unknown")
        }

        self.writer = writer
        self.input = input
        self.adaptor = adaptor
        self.started = false
        self.firstFrameTime = nil
        self.lastWritten = .negativeInfinity
        self.outputURL = url
    }

    /// Hand it an ARFrame. Frames arriving faster than the target rate are dropped, and frames
    /// recorded while tracking is poor are skipped: they are the blurred ones anyway.
    func append(frame: ARFrame) {
        guard let writer, let input, let adaptor, writer.status == .writing else { return }
        if case .limited = frame.camera.trackingState { return }

        let time = CMTime(seconds: frame.timestamp, preferredTimescale: 600)
        if !started {
            writer.startSession(atSourceTime: time)
            firstFrameTime = time
            started = true
        } else {
            let minGap = CMTime(seconds: 1.0 / targetFPS, preferredTimescale: 600)
            guard CMTimeSubtract(time, lastWritten) >= minGap else { return }
        }
        guard input.isReadyForMoreMediaData, let pool = adaptor.pixelBufferPool else { return }

        var buffer: CVPixelBuffer?
        guard CVPixelBufferPoolCreatePixelBuffer(nil, pool, &buffer) == kCVReturnSuccess,
              let out = buffer else { return }

        // ARKit hands over YCbCr; the writer wants BGRA, and the camera image is landscape-right
        // relative to a portrait phone, so it is rotated on the way through.
        let image = CIImage(cvPixelBuffer: frame.capturedImage)
            .oriented(.right)
        let scale = max(size.width / image.extent.width, size.height / image.extent.height)
        let scaled = image.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
        context.render(scaled, to: out)

        adaptor.append(out, withPresentationTime: time)
        lastWritten = time
    }

    /// Close the file. Returns nil if nothing usable was written.
    func finish() async -> URL? {
        guard let writer, let input, writer.status == .writing else { return nil }
        input.markAsFinished()
        await writer.finishWriting()
        self.writer = nil
        self.input = nil
        self.adaptor = nil
        guard writer.status == .completed else { return nil }
        return outputURL
    }

    func cancel() {
        writer?.cancelWriting()
        writer = nil; input = nil; adaptor = nil
        if let url = outputURL { try? FileManager.default.removeItem(at: url) }
        outputURL = nil
    }
}
