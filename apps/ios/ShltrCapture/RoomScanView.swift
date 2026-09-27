import RoomPlan
import SwiftUI

/// RoomPlan's own guided camera view. The controller owns it, because the session that drives
/// the scan belongs to the view, not the other way round.
struct RoomScanView: UIViewRepresentable {
    let controller: CaptureController

    func makeUIView(context: Context) -> RoomCaptureView { controller.roomView }

    func updateUIView(_ uiView: RoomCaptureView, context: Context) {}
}
