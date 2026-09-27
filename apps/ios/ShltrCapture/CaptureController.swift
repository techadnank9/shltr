import ARKit
import Combine
import Foundation
import RoomPlan
import UIKit

/// Runs one walk: RoomPlan's guided session, the coverage engine on top of it, and the video
/// being written from the same frames. Everything the screens show comes from here.
@MainActor
final class CaptureController: NSObject, ObservableObject {
    enum Phase: Equatable {
        case intro
        case scanning
        case review(URL)
        case uploading
        case failed(String)
    }

    @Published private(set) var phase: Phase = .intro
    @Published private(set) var instruction = "Stand in the doorway and look around slowly."
    @Published private(set) var wallsDone = 0
    @Published private(set) var wallsTotal = 0
    @Published private(set) var elapsed: TimeInterval = 0
    @Published private(set) var isComplete = false
    @Published var title = ""

    /// RoomCaptureView owns its own RoomCaptureSession, so the view is the thing that must be
    /// created first and the session taken from it. Running a session we made ourselves would
    /// leave the one on screen untouched. Built lazily: an unsupported phone never makes one.
    lazy var roomView = RoomCaptureView(frame: .zero)
    var captureSession: RoomCaptureSession { roomView.captureSession }

    private let coverage = CoverageEngine()
    private let recorder = WalkthroughRecorder()
    private var displayLink: CADisplayLink?
    private var startedAt: Date?

    static var isSupported: Bool {
        #if targetEnvironment(simulator)
        // A simulator has no depth sensor and can never scan. SHLTR_SIM_UI=1 gets past the
        // unsupported screen so the rest of the screens can be looked at; the scan itself
        // still cannot run there.
        if ProcessInfo.processInfo.environment["SHLTR_SIM_UI"] == "1" { return true }
        #endif
        return RoomCaptureSession.isSupported
    }

    /// Begin the walk. RoomPlan drives the camera; we read its frames rather than opening our own.
    func begin() {
        guard phase == .intro || isFailed else { return }
        do {
            try recorder.start()
        } catch {
            phase = .failed(error.localizedDescription)
            return
        }
        captureSession.delegate = self
        captureSession.run(configuration: RoomCaptureSession.Configuration())
        startedAt = Date()
        phase = .scanning

        let link = CADisplayLink(target: self, selector: #selector(onFrame))
        link.add(to: .main, forMode: .common)
        displayLink = link
    }

    /// Stop early or when the cap is reached. Pressing Done always works, however little is covered.
    func finish() {
        guard phase == .scanning else { return }
        displayLink?.invalidate()
        displayLink = nil
        captureSession.stop()
        Task {
            if let url = await recorder.finish() {
                phase = .review(url)
            } else {
                phase = .failed("Nothing was recorded. Try the walk again.")
            }
        }
    }

    func discard() {
        if case .review(let url) = phase { try? FileManager.default.removeItem(at: url) }
        recorder.cancel()
        coverageReset()
        phase = .intro
        elapsed = 0
    }

    func upload() async -> URL? {
        guard case .review(let file) = phase else { return nil }
        phase = .uploading
        do {
            let client = UploadClient()
            let created = try await client.upload(file: file, title: title)
            try? FileManager.default.removeItem(at: file)
            return client.caseURL(created)
        } catch {
            phase = .failed(error.localizedDescription)
            return nil
        }
    }

    private var isFailed: Bool { if case .failed = phase { return true }; return false }

    private func coverageReset() {
        wallsDone = 0; wallsTotal = 0; isComplete = false
        instruction = "Stand in the doorway and look around slowly."
    }

    /// Per display refresh: bank the video frame, fold the camera into coverage, refresh the advice.
    @objc private func onFrame() {
        // The clock and the cap run off the display link, not off frame arrival. If ARKit stalls
        // or loses tracking, a walk driven by frames would freeze here and never stop itself.
        if let startedAt {
            elapsed = Date().timeIntervalSince(startedAt)
            if elapsed >= Config.maxSeconds {
                finish()
                return
            }
        }

        guard let frame = captureSession.arSession.currentFrame else { return }
        recorder.append(frame: frame)
        coverage.observe(from: frame.camera)

        instruction = coverage.instruction(from: frame.camera)
        wallsDone = coverage.doneCount
        wallsTotal = coverage.total
        isComplete = coverage.isComplete
    }
}

extension CaptureController: RoomCaptureSessionDelegate {
    nonisolated func captureSession(_ session: RoomCaptureSession, didUpdate room: CapturedRoom) {
        Task { @MainActor in self.coverage.update(room: room) }
    }

    nonisolated func captureSession(_ session: RoomCaptureSession, didEndWith data: CapturedRoomData, error: Error?) {
        guard let error else { return }
        Task { @MainActor in self.phase = .failed(error.localizedDescription) }
    }
}
