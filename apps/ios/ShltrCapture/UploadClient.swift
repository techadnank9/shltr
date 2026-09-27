import Foundation

/// Sends the walk to the control plane using the same endpoint the web pages use:
/// POST /api/cases, multipart, fields `file` and `title` (backend/control/app.py).
/// Nothing server-side had to change for the phone to work.
struct UploadClient {
    struct Created: Decodable {
        let case_id: String
        let url: String
    }

    enum UploadError: LocalizedError {
        case tooLarge(Int)
        case server(String)
        var errorDescription: String? {
            switch self {
            case .tooLarge(let bytes):
                return "That recording is \(bytes / 1_048_576) MB. The limit is 100 MB — record a shorter walk."
            case .server(let detail):
                return detail
            }
        }
    }

    var baseURL: URL = Config.baseURL

    func upload(file: URL, title: String) async throws -> Created {
        let size = (try FileManager.default.attributesOfItem(atPath: file.path)[.size] as? Int) ?? 0
        guard size <= Config.maxUploadBytes else { throw UploadError.tooLarge(size) }

        // The body is assembled on disk and uploaded from there. Reading a 100 MB walkthrough
        // into Data and then copying it into a request body would hold ~200 MB at once, which is
        // how a capture app gets killed on a phone that is already running ARKit.
        let boundary = "shltr.\(UUID().uuidString)"
        let bodyURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("upload-\(UUID().uuidString).multipart")
        FileManager.default.createFile(atPath: bodyURL.path, contents: nil)
        let handle = try FileHandle(forWritingTo: bodyURL)
        defer {
            try? handle.close()
            try? FileManager.default.removeItem(at: bodyURL)
        }

        var head = Data()
        head.append("--\(boundary)\r\n".data(using: .utf8)!)
        head.append("Content-Disposition: form-data; name=\"file\"; filename=\"walkthrough.mp4\"\r\n".data(using: .utf8)!)
        head.append("Content-Type: video/mp4\r\n\r\n".data(using: .utf8)!)
        try handle.write(contentsOf: head)

        let source = try FileHandle(forReadingFrom: file)
        defer { try? source.close() }
        while let chunk = try source.read(upToCount: 1 << 20), !chunk.isEmpty {
            try handle.write(contentsOf: chunk)
        }

        var tail = Data()
        tail.append("\r\n--\(boundary)\r\n".data(using: .utf8)!)
        tail.append("Content-Disposition: form-data; name=\"title\"\r\n\r\n".data(using: .utf8)!)
        tail.append("\(title)\r\n".data(using: .utf8)!)
        tail.append("--\(boundary)--\r\n".data(using: .utf8)!)
        try handle.write(contentsOf: tail)
        try handle.close()

        var request = URLRequest(url: baseURL.appendingPathComponent("api/cases"))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 300  // venue wifi

        let (responseData, response) = try await URLSession.shared.upload(for: request, fromFile: bodyURL)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            let detail = (try? JSONSerialization.jsonObject(with: responseData) as? [String: Any])?["detail"] as? String
            throw UploadError.server(detail ?? "The upload failed (\(status)).")
        }
        return try JSONDecoder().decode(Created.self, from: responseData)
    }

    /// Where to watch the case run, for the web view we hand the survivor afterwards.
    func caseURL(_ created: Created) -> URL {
        URL(string: created.url, relativeTo: baseURL) ?? baseURL
    }
}
