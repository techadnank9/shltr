import SafariServices
import SwiftUI

private enum Palette {
    static let ink = Color(red: 0x0B / 255, green: 0x12 / 255, blue: 0x16 / 255)
    static let panel = Color(red: 0x10 / 255, green: 0x1C / 255, blue: 0x22 / 255)
    static let line = Color(red: 0x22 / 255, green: 0x34 / 255, blue: 0x3C / 255)
    static let text = Color(red: 0xE6 / 255, green: 0xEC / 255, blue: 0xEE / 255)
    static let muted = Color(red: 0x8F / 255, green: 0xA3 / 255, blue: 0xAA / 255)
    static let amber = Color(red: 0xF2 / 255, green: 0xA3 / 255, blue: 0x3A / 255)
    static let green = Color(red: 0x3D / 255, green: 0xD6 / 255, blue: 0x8C / 255)
}

struct RootView: View {
    @StateObject private var controller = CaptureController()
    @State private var caseLink: CaseLink?

    var body: some View {
        ZStack {
            Palette.ink.ignoresSafeArea()
            if !CaptureController.isSupported {
                UnsupportedView()
            } else {
                switch controller.phase {
                case .intro:      IntroView(controller: controller)
                case .scanning:   ScanningView(controller: controller)
                case .review:     ReviewView(controller: controller, caseLink: $caseLink)
                case .uploading:  Busy(message: "Sending your room…")
                case .failed(let why): FailureView(why: why, controller: controller)
                }
            }
        }
        .foregroundStyle(Palette.text)
        .preferredColorScheme(.dark)
        .sheet(item: $caseLink) { link in SafariView(url: link.url) }
    }
}

/// Says what does work, rather than what does not.
private struct UnsupportedView: View {
    var body: some View {
        VStack(spacing: 14) {
            Text("Shel").font(.largeTitle.bold()) + Text("tr").font(.largeTitle.bold()).foregroundColor(Palette.amber)
            Text("This iPhone has no depth sensor, so it cannot measure a room.")
                .foregroundStyle(Palette.muted).multilineTextAlignment(.center)
            Text("Open shltr on this phone's browser and record the room there instead — it works on any phone.")
                .foregroundStyle(Palette.muted).multilineTextAlignment(.center).font(.footnote)
            Link("Open the web recorder", destination: Config.baseURL.appendingPathComponent("capture"))
                .foregroundStyle(Palette.amber)
        }
        .padding(28)
    }
}

private struct IntroView: View {
    @ObservedObject var controller: CaptureController

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Record the room").font(.title2.bold())
            Text("Walk slowly around the room. We'll tell you where to point, then rebuild it in 3D and price the damage. Nothing is submitted without your approval.")
                .foregroundStyle(Palette.muted)
            TextField("14 Alder Lane, ground floor", text: $controller.title)
                .textFieldStyle(.plain).padding(12)
                .background(Palette.ink).overlay(RoundedRectangle(cornerRadius: 5).stroke(Palette.line))
            VStack(alignment: .leading, spacing: 8) {
                Label("Start in the doorway, phone upright.", systemImage: "1.circle")
                Label("Walk slowly — sweeping fast blurs every frame.", systemImage: "2.circle")
                Label("Look at each wall from two spots, a step apart.", systemImage: "3.circle")
            }
            .font(.footnote).foregroundStyle(Palette.muted)
            Button("Start recording") { controller.begin() }
                .buttonStyle(Primary())
            Spacer()
        }
        .padding(24)
    }
}

private struct ScanningView: View {
    @ObservedObject var controller: CaptureController

    var body: some View {
        ZStack {
            RoomScanView(controller: controller).ignoresSafeArea()
            VStack {
                HStack(alignment: .top) {
                    Text(controller.instruction)
                        .font(.headline).shadow(radius: 6)
                    Spacer()
                    Text(clock).font(.system(.footnote, design: .monospaced))
                        .padding(.horizontal, 10).padding(.vertical, 5)
                        .background(Palette.ink.opacity(0.7), in: Capsule())
                }
                Spacer()
                VStack(spacing: 14) {
                    // One segment per wall, filling in as each is covered. No percentage.
                    if controller.wallsTotal > 0 {
                        HStack(spacing: 5) {
                            ForEach(0..<controller.wallsTotal, id: \.self) { i in
                                Capsule()
                                    .fill(i < controller.wallsDone ? Palette.green : Palette.text.opacity(0.2))
                                    .frame(height: 4)
                            }
                        }
                    }
                    if controller.isComplete {
                        Text("You've got the whole room.")
                            .font(.headline).foregroundStyle(Palette.green)
                    }
                    Button { controller.finish() } label: {
                        Circle().fill(Palette.ink)
                            .frame(width: 74, height: 74)
                            .overlay(RoundedRectangle(cornerRadius: 3).fill(Color.red).frame(width: 24, height: 24))
                            .overlay(Circle().stroke(.white.opacity(0.9), lineWidth: 4))
                    }
                    .accessibilityLabel("Done")
                }
            }
            .padding(20)
        }
    }

    private var clock: String {
        let t = Int(controller.elapsed)
        return String(format: "%d:%02d / 0:%.0f", t / 60, t % 60, Config.maxSeconds)
    }
}

private struct ReviewView: View {
    @ObservedObject var controller: CaptureController
    @Binding var caseLink: CaseLink?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(controller.isComplete ? "That looks good" : "That will work")
                .font(.title2.bold())
            Text(controller.isComplete
                 ? "Every wall was seen from two places, so the room can be measured properly."
                 : "Some walls were only seen once. You can send it, or walk the room again for a better estimate.")
                .foregroundStyle(Palette.muted)
            Button("Send this recording") {
                Task { caseLink = (await controller.upload()).map(CaseLink.init) }
            }
            .buttonStyle(Primary())
            Button("Record again") { controller.discard() }
                .buttonStyle(Ghost())
            Spacer()
        }
        .padding(24)
    }
}

private struct FailureView: View {
    let why: String
    @ObservedObject var controller: CaptureController

    var body: some View {
        VStack(spacing: 16) {
            Text(why).multilineTextAlignment(.center).foregroundStyle(Palette.muted)
            Button("Try again") { controller.discard() }.buttonStyle(Primary())
        }
        .padding(28)
    }
}

private struct Busy: View {
    let message: String
    var body: some View {
        VStack(spacing: 14) {
            ProgressView().tint(Palette.amber)
            Text(message).foregroundStyle(Palette.muted)
        }
    }
}

private struct Primary: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline).frame(maxWidth: .infinity).padding(13)
            .background(Palette.amber, in: RoundedRectangle(cornerRadius: 5))
            .foregroundStyle(Palette.ink)
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

private struct Ghost: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline).frame(maxWidth: .infinity).padding(13)
            .overlay(RoundedRectangle(cornerRadius: 5).stroke(Palette.line))
            .foregroundStyle(Palette.text)
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

/// The case runs in the existing web front end, so the phone shows that rather than a second
/// copy of the same screens.
private struct SafariView: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> SFSafariViewController { SFSafariViewController(url: url) }
    func updateUIViewController(_ controller: SFSafariViewController, context: Context) {}
}

/// A sheet's item has to be Identifiable, and conforming URL itself would be a conformance
/// to two types we do not own.
private struct CaseLink: Identifiable {
    let url: URL
    var id: String { url.absoluteString }
}
