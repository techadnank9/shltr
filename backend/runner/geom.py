"""Geometry helpers for agent-written code. Copied into every code sandbox as /in/geom.py.

The 3D room comes from depth.py: a pinhole camera at the origin looking down -z, y up,
units in metres. A pixel (px, py) at depth z sits at ((px - cx) / f * z, -(py - cy) / f * z, -z)
with cx = (width - 1) / 2, cy = (height - 1) / 2 and f = focal_px (all from stats.json).

Positions in the photo are given normalised: u from 0 (left) to 1 (right), v from 0 (top) to 1 (bottom).

    import geom
    room = geom.load_room()             # .vertices (N, 3), .faces (M, 3), .face_areas, .floor_y
    stats = geom.load_stats()
    geom.point_at(room, 0.42, 0.63, stats)          -> [x, y, z] on the surface, or None
    geom.area_in_box(room, [u0, v0, u1, v1], stats) -> square metres of surface seen in that box
    geom.height_of(room, point)                     -> metres above the lowest floor point
"""
import json

import numpy as np
import trimesh


class Room:
    def __init__(self, vertices: np.ndarray, faces: np.ndarray):
        self.vertices = vertices
        self.faces = faces
        self.triangles = vertices[faces]  # (M, 3, 3)
        a, b, c = self.triangles[:, 0], self.triangles[:, 1], self.triangles[:, 2]
        self.face_areas = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
        self.centroids = self.triangles.mean(axis=1)
        self.floor_y = float(np.percentile(vertices[:, 1], 2))


def load_room(path: str = "/in/room.glb") -> Room:
    mesh = trimesh.load(path, force="mesh", process=False)
    return Room(np.asarray(mesh.vertices, dtype=np.float64), np.asarray(mesh.faces, dtype=np.int64))


def load_stats(path: str = "/in/stats.json") -> dict:
    with open(path) as fh:
        return json.load(fh)


def _camera(stats: dict) -> tuple[float, float, float, float, float]:
    w, h, f = float(stats["width"]), float(stats["height"]), float(stats["focal_px"])
    return w, h, f, (w - 1) / 2, (h - 1) / 2


def ray_for(u: float, v: float, stats: dict) -> np.ndarray:
    """Unit direction from the camera through the normalised photo position (u, v)."""
    w, h, f, cx, cy = _camera(stats)
    d = np.array([(u * (w - 1) - cx) / f, -(v * (h - 1) - cy) / f, -1.0])
    return d / np.linalg.norm(d)


def point_at(room: Room, u: float, v: float, stats: dict) -> list[float] | None:
    """First point where the camera ray through (u, v) hits the room surface (Moller-Trumbore)."""
    d = ray_for(u, v, stats)
    tri = room.triangles
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    p = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, p)
    ok = np.abs(det) > 1e-12
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    s = -tri[:, 0]  # ray origin is (0, 0, 0)
    bu = np.einsum("ij,ij->i", s, p) * inv
    q = np.cross(s, e1)
    bv = (q @ d) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    hit = ok & (bu >= 0) & (bv >= 0) & (bu + bv <= 1) & (t > 0)
    if not hit.any():
        return None
    return (d * t[hit].min()).round(4).tolist()


def area_in_box(room: Room, box: list[float], stats: dict) -> float:
    """Surface area (m^2) of the faces whose centre appears inside the photo box [u0, v0, u1, v1]."""
    w, h, f, cx, cy = _camera(stats)
    c = room.centroids
    z = -c[:, 2]
    front = z > 1e-6
    u = np.full(len(c), -1.0)
    v = np.full(len(c), -1.0)
    u[front] = (c[front, 0] / z[front] * f + cx) / (w - 1)
    v[front] = (-c[front, 1] / z[front] * f + cy) / (h - 1)
    u0, v0, u1, v1 = box
    inside = front & (u >= min(u0, u1)) & (u <= max(u0, u1)) & (v >= min(v0, v1)) & (v <= max(v0, v1))
    return round(float(room.face_areas[inside].sum()), 3)


def height_of(room: Room, point: list[float]) -> float:
    """Height of a point above the floor (the lowest 2% of the room), in metres."""
    return round(float(point[1]) - room.floor_y, 3)
