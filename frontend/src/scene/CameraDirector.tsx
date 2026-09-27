import { OrbitControls } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { source } from '../events/pick'
import { useCase } from '../store'
import { FLY } from './Sandbox'
import { reducedMotion, useRoomBounds } from './shared'

/**
 * Scripted fly-through driven by case state, not by a fixed timeline, so it
 * works the same for fake and live events. Dragging hands control to the
 * viewer until the next stage.
 */
export function CameraDirector() {
  const { camera, size } = useThree()
  const controls = useRef<{ target: THREE.Vector3 } | null>(null)
  const user = useRef(false)
  const lastStage = useRef(-1)
  const pos = useMemo(() => new THREE.Vector3(), [])
  const tgt = useMemo(() => new THREE.Vector3(0, 0, -5), [])
  const lookAt = useMemo(() => new THREE.Vector3(0, 0, -5), [])
  const tmp = useMemo(() => new THREE.Vector3(), [])

  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera
    cam.fov = size.width / size.height < 0.9 ? 62 : 45
    cam.updateProjectionMatrix()
  }, [camera, size])

  // A reset (Replay, jump) gives the camera back to the script.
  useEffect(() => useCase.subscribe((s, prev) => { if (s.lastSeq < prev.lastSeq) user.current = false }), [])

  useFrame((_, dt) => {
    const s = useCase.getState()
    const box = useRoomBounds.getState().box
    const now = source.now()
    if (s.stage !== lastStage.current) { lastStage.current = s.stage; user.current = false }
    if (user.current) return

    const c = box ? box.getCenter(tmp) : tmp.set(0, 0, -5)
    const sinceRoom = s.room ? now - s.room.t : -1
    const lastThreat = s.threats.length ? now - s.threats[s.threats.length - 1].t : 99
    const lastDamage = s.damages[s.damages.length - 1]
    const narrow = size.width / size.height < 0.9
    const browserLive = Object.values(s.sandboxes).some((x) => x.kind === 'browser' && x.destroyedAt === undefined)

    if (!s.room || sinceRoom < 2.4 || !box) {
      // Photo view: the camera stands where the survivor stood.
      pos.set(0, 0, 0); tgt.set(0, 0, -5)
    } else if (s.approval || s.receipt || s.form.length) {
      // Claim: a slow, shallow orbit in front of the room.
      const a = reducedMotion ? 0.25 : Math.sin(now * 0.09) * 0.45
      const r = narrow ? 10 : 7.2
      pos.set(c.x + Math.sin(a) * r, c.y + 2.3, c.z + Math.cos(a) * r); tgt.copy(c)
    } else if (s.stage >= 4 || browserLive) {
      // Containment: pull back to see the whole glass box and its front face.
      pos.set(c.x + 0.8, c.y + 1.4, c.z + (narrow ? 13 : 9.5)); tgt.set(c.x, c.y, c.z + 1)
    } else if (s.total && lastDamage && now - lastDamage.t > 1.2) {
      // All damage found: a wide view with every marker.
      pos.set(1.2, 1.3, 1.2); tgt.copy(c)
    } else if (lastDamage) {
      // Visit each damage as it is found, from the survivor's side of the room.
      tgt.set(...lastDamage.position)
      pos.set(-0.2, 0.3, 0).sub(tgt).normalize().multiplyScalar(narrow ? 3.6 : 2.6).add(tgt)
      pos.y += 0.35
    } else if (sinceRoom < 7) {
      // The reveal: swing out to a three-quarter view.
      pos.set(c.x + 3.6, c.y + 2.6, c.z + 5.8); tgt.copy(c)
    } else {
      pos.set(c.x + 2.4, c.y + 1.8, c.z + 5.4); tgt.copy(c)
    }

    const fast = s.threats.length > 0 && lastThreat < FLY + 0.3
    const k = reducedMotion ? 1 : 1 - Math.exp(-dt * (fast ? 3 : 1.7))
    camera.position.lerp(pos, k)
    lookAt.lerp(tgt, k)
    camera.lookAt(lookAt)
    controls.current?.target.copy(lookAt)
  })

  return (
    <OrbitControls
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ref={controls as any}
      makeDefault
      enablePan={false}
      enableDamping
      minDistance={0.5}
      maxDistance={16}
      onStart={() => { user.current = true }}
    />
  )
}
