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
