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
        let data = try Data(contentsOf: file)
        guard data.count <= Config.maxUploadBytes else { throw UploadError.tooLarge(data.count) }

        let boundary = "shltr.\(UUID().uuidString)"
        var request = URLRequest(url: baseURL.appendingPathComponent("api/cases"))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        func field(_ name: String, _ value: String) {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(value)\r\n".data(using: .utf8)!)
        }
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"walkthrough.mp4\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: video/mp4\r\n\r\n".data(using: .utf8)!)
        body.append(data)
        body.append("\r\n".data(using: .utf8)!)
        field("title", title)
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        let (responseData, response) = try await URLSession.shared.upload(for: request, from: body)
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
