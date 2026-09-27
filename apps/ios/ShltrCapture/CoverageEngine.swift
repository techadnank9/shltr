import ARKit
import Foundation
import RoomPlan
import simd

/// Tracks which walls have been seen well enough to trust, and says where to point next.
///
/// A wall counts as observed from a viewpoint when it is in front of the camera, within
/// `maxRange`, and viewed at less than `maxObliqueAngle` off its normal. One glance from the
/// doorway is not coverage, so a wall is only done once it has been seen from two viewpoints at
/// least `minBaseline` apart: two separated views are what give a reconstruction its depth.
final class CoverageEngine {
    struct WallState {
        var identifier: UUID
        var centre: simd_float3
        var normal: simd_float3
        var viewpoints: [simd_float3] = []
        var highConfidence = false

        /// Two viewpoints far enough apart to triangulate, and RoomPlan itself is happy.
        var isDone: Bool {
            guard highConfidence else { return false }
            for a in viewpoints {
                for b in viewpoints where simd_distance(a, b) >= CoverageEngine.minBaseline {
                    return true
                }
            }
            return false
        }
    }

    static let minBaseline: Float = 1.0          // metres between two viewpoints
    private let maxRange: Float = 5.0            // metres
    private let maxObliqueAngle: Float = 60      // degrees off the wall normal
    private let minViewpointGap: Float = 0.35    // don't bank a hundred views of one spot

    private(set) var walls: [UUID: WallState] = [:]

    var doneCount: Int { walls.values.filter(\.isDone).count }
    var total: Int { walls.count }
    var isComplete: Bool { total > 0 && doneCount == total }

    /// Take the room as RoomPlan currently understands it. Walls come and go while it refines,
    /// so viewpoints already banked for a wall are carried over.
    func update(room: CapturedRoom) {
        var next: [UUID: WallState] = [:]
        for wall in room.walls {
            let t = wall.transform
            let centre = simd_float3(t.columns.3.x, t.columns.3.y, t.columns.3.z)
            // A RoomPlan surface's +z axis points out of its face.
            let normal = simd_normalize(simd_float3(t.columns.2.x, t.columns.2.y, t.columns.2.z))
            var state = walls[wall.identifier] ?? WallState(identifier: wall.identifier, centre: centre, normal: normal)
            state.centre = centre
            state.normal = normal
            state.highConfidence = wall.confidence == .high
            next[wall.identifier] = state
        }
        walls = next
    }

    /// Fold in where the camera is now. Called per frame while the walk is running.
    func observe(from camera: ARCamera) {
        let eye = simd_float3(camera.transform.columns.3.x, camera.transform.columns.3.y, camera.transform.columns.3.z)
        // The camera looks down its own -z.
        let forward = -simd_normalize(simd_float3(camera.transform.columns.2.x,
                                                  camera.transform.columns.2.y,
                                                  camera.transform.columns.2.z))
        for (id, var state) in walls where !state.isDone {
            let toWall = state.centre - eye
            let distance = simd_length(toWall)
            guard distance > 0.2, distance <= maxRange else { continue }
            let direction = toWall / distance

            // Is the wall actually in front of us?
            guard simd_dot(direction, forward) > 0.5 else { continue }

            // Are we looking at its face, rather than sliding along it?
            let obliqueness = abs(simd_dot(direction, state.normal))
            guard obliqueness > cos(maxObliqueAngle * .pi / 180) else { continue }

            if let last = state.viewpoints.last, simd_distance(last, eye) < minViewpointGap { continue }
            state.viewpoints.append(eye)
            walls[id] = state
        }
    }

    /// One instruction at a time, aimed at the nearest wall still missing a second viewpoint.
    /// Never a percentage and never the word confidence: the survivor is told where to point.
    func instruction(from camera: ARCamera) -> String {
        guard total > 0 else { return "Stand in the doorway and look around slowly." }
        if isComplete { return "You've got the whole room." }

        let eye = simd_float3(camera.transform.columns.3.x, camera.transform.columns.3.y, camera.transform.columns.3.z)
        let pending = walls.values.filter { !$0.isDone }
        guard let target = pending.min(by: { simd_distance($0.centre, eye) < simd_distance($1.centre, eye) }) else {
            return "You've got the whole room."
        }
        if target.viewpoints.isEmpty {
            return "Point the phone at the nearest wall you haven't covered."
        }
        return "Step to one side and look at that wall again from there."
    }
}
