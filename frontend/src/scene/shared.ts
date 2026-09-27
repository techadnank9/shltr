import * as THREE from 'three'
import { create } from 'zustand'

export const COLORS = {
  ink: '#0B1216',
  amber: new THREE.Color('#F2A33A'),
  red: new THREE.Color('#E5484D'),
  water: new THREE.Color('#3FA7D6'),
}

export const reducedMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Room bounds from the loaded room.glb (metres, room.glb coordinates). */
export const useRoomBounds = create<{ box: THREE.Box3 | null; set: (b: THREE.Box3 | null) => void }>((set) => ({
  box: null,
  set: (box) => set({ box }),
}))

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x))
export const ramp = (t: number, a: number, b: number) => clamp01((t - a) / (b - a))
export const ease = (x: number) => x * x * x * (x * (x * 6 - 15) + 10)

/** HTML labels rendered outside the Canvas (see ui/Overlays), positioned by the scene each frame. */
export const labelEls = new Map<string, HTMLDivElement>()

const tmp = new THREE.Vector3()
/** Move an HTML label to a 3D point; hides it when the point is behind the camera or off screen. */
export function placeLabel(el: HTMLElement, p: THREE.Vector3, camera: THREE.Camera, w: number, h: number, show = true) {
  tmp.copy(p).project(camera)
  const on = show && tmp.z < 1 && Math.abs(tmp.x) < 1 && Math.abs(tmp.y) < 1
  el.style.visibility = on ? 'visible' : 'hidden'
  if (on) el.style.transform = `translate(${((tmp.x * 0.5 + 0.5) * w).toFixed(1)}px, ${((-tmp.y * 0.5 + 0.5) * h).toFixed(1)}px)`
}
