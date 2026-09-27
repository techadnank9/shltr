import Foundation

/// Where the control plane lives. The app ships pointing at the live VM 1 host, so a fresh
/// clone needs no address typed in. Override it at run time with a `SHLTR_BASE` environment
/// variable in the scheme when testing against a laptop.
enum Config {
    static var baseURL: URL {
        if let raw = ProcessInfo.processInfo.environment["SHLTR_BASE"], let url = URL(string: raw) {
            return url
        }
        return URL(string: "https://45-76-251-95.sslip.io")!
    }

    /// The control plane refuses anything larger (backend/control/app.py).
    static let maxUploadBytes = 100 * 1024 * 1024

    /// The sandbox samples one frame a second and keeps at most 30
    /// (sandboxes/photo/prepare.py), so a longer walk uploads more without being looked at.
    static let maxSeconds: TimeInterval = 30
    static let minSeconds: TimeInterval = 8
}
