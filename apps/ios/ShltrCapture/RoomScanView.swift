import RoomPlan
import SwiftUI

/// RoomPlan's own guided camera view, driven by the session the controller owns.
struct RoomScanView: UIViewRepresentable {
    let session: RoomCaptureSession

    func makeUIView(context: Context) -> RoomCaptureView {
        // Handing it an existing session keeps one ARSession for the scan, the coverage
        // engine and the video recorder alike.
        let view = RoomCaptureView(frame: .zero, arSession: session.arSession)
        return view
    }

    func updateUIView(_ uiView: RoomCaptureView, context: Context) {}
}
