import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { source } from '../events/pick'
import type { ThreatKind } from '../events/types'
import { useCase } from '../store'
import { COLORS, ease, labelEls, placeLabel, ramp, reducedMotion, useRoomBounds } from './shared'

const PAD = 0.35
export const FLY = 0.55 // seconds for an attack to reach the glass after threat.contained
const ALARM = 2.6

/**
 * The glass sandbox boundary around the room, shown while a sandbox is alive,
 * and the containment effect for each threat.contained.
 */
export function Sandbox() {
  const box = useRoomBounds((s) => s.box)
  if (!box) return null
  return <Boundary box={box} />
}

// Where each kind of attack hits the front glass, as a fraction of the box size.
const HIT: Record<ThreatKind, [number, number]> = {
  prompt_injection: [0, 0.2], download: [-0.3, -0.15], exfiltration: [0.3, 0.3], timeout: [0, 0], memory: [0, 0],
}

function Boundary({ box }: { box: THREE.Box3 }) {
  const size = useMemo(() => box.getSize(new THREE.Vector3()).addScalar(PAD * 2), [box])
  const center = useMemo(() => box.getCenter(new THREE.Vector3()), [box])
  const front = center.z + size.z / 2

  const geo = useMemo(() => new THREE.BoxGeometry(size.x, size.y, size.z), [size])
  const edgesGeo = useMemo(() => new THREE.EdgesGeometry(geo), [geo])
  const edgeMat = useMemo(() => new THREE.LineBasicMaterial({ color: COLORS.amber, transparent: true, toneMapped: false }), [])
  const glassMat = useMemo(() => new THREE.MeshBasicMaterial({ color: COLORS.amber, transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false }), [])
  const payloadMat = useMemo(() => new THREE.MeshBasicMaterial({ color: COLORS.red.clone().multiplyScalar(2.5), toneMapped: false }), [])
  const shockMats = useMemo(
    () => [0, 1, 2].map(() => new THREE.MeshBasicMaterial({ color: COLORS.red.clone().multiplyScalar(2), transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false })),
    [],
  )
  const red = useMemo(() => COLORS.red.clone().multiplyScalar(1.8), [])

  const group = useRef<THREE.Group>(null)
  const payloads = useRef<THREE.Mesh[]>([])
  const shocks = useRef<THREE.Mesh[]>([])
  const corner = useMemo(() => new THREE.Vector3(center.x - size.x / 2, center.y + size.y / 2, center.z + size.z / 2), [center, size])
  const vis = useRef(0)
  const from = useMemo(() => center.clone().setZ(center.z - size.z * 0.15), [center, size])
  const to = useMemo(() => new THREE.Vector3(), [])

  useFrame(({ camera, size: view }, dt) => {
    const s = useCase.getState()
    const now = source.now()
    const live = Object.values(s.sandboxes).filter((x) => x.t <= now && (x.destroyedAt === undefined || x.destroyedAt > now))
    const want = live.length > 0 ? 1 : 0
    vis.current = reducedMotion ? want : vis.current + (want - vis.current) * (1 - Math.exp(-dt * 4))

    // Alarm strength from the most recent hits.
    let alarm = 0
    let blink = 0
    for (const th of s.threats) {
      const hit = now - th.t - FLY
      if (hit >= 0 && hit < ALARM) {
        alarm = Math.max(alarm, 1 - hit / ALARM)
        blink = Math.max(blink, reducedMotion ? 1 : 0.5 + 0.5 * Math.cos(hit * 14))
      }
    }
    const alarmOn = alarm > 0.02
    const shown = Math.max(vis.current, alarmOn ? 1 : 0)
    edgeMat.color.copy(alarmOn ? red : COLORS.amber)
    edgeMat.opacity = shown * (0.4 + 0.6 * Math.max(alarm * 0.6, blink * alarm))
    glassMat.color.copy(alarmOn ? COLORS.red : COLORS.amber)
    glassMat.opacity = shown * (0.025 + 0.16 * alarm * (0.4 + 0.6 * blink))
    if (group.current) group.current.visible = shown > 0.01

    // Each attack flies from inside the room to the glass, then a shockwave.
    const recent = s.threats.slice(-3)
    for (let i = 0; i < 3; i++) {
      const p = payloads.current[i]
      const sh = shocks.current[i]
      const th = recent[i]
      if (!p || !sh) continue
      if (!th || reducedMotion) { p.visible = false; sh.visible = false; continue }
      const age = now - th.t
      const [fx, fy] = HIT[th.kind]
      to.set(center.x + fx * size.x, center.y + fy * size.y, front)
      const f = ramp(age, 0, FLY)
      p.visible = age >= 0 && age < FLY
      p.position.lerpVectors(from, to, ease(f))
      p.rotation.set(age * 6, age * 9, 0)
      const hit = age - FLY
      if (hit >= 0 && hit < 1.6) {
        sh.visible = true
        sh.position.copy(to)
        sh.scale.setScalar(0.1 + hit * 1.4)
        shockMats[i].opacity = 0.9 * (1 - hit / 1.6)
      } else sh.visible = false
    }

    const tag = labelEls.get('sandbox')
    if (tag) {
      const sb = live[live.length - 1]
      tag.style.opacity = String(vis.current)
      placeLabel(tag, corner, camera, view.width, view.height, vis.current > 0.01)
      if (sb) tag.textContent = `${sb.id} · ${sb.kind === 'photo' ? 'microVM' : 'gVisor browser'} · network: ${sb.network}`
    }
  })

  const shapes = [
    <octahedronGeometry key="o" args={[0.12, 0]} />,
    <boxGeometry key="b" args={[0.16, 0.16, 0.16]} />,
    <tetrahedronGeometry key="t" args={[0.14, 0]} />,
  ]

  return (
    <>
      <group ref={group} position={center}>
        <lineSegments geometry={edgesGeo} material={edgeMat} renderOrder={5} />
        <mesh geometry={geo} material={glassMat} renderOrder={4} />
      </group>
      {shapes.map((shape, i) => (
        <mesh key={i} ref={(m) => { if (m) payloads.current[i] = m }} material={payloadMat} visible={false} renderOrder={30}>
          {shape}
        </mesh>
      ))}
      {shockMats.map((m, i) => (
        <mesh key={i} ref={(x) => { if (x) shocks.current[i] = x }} material={m} visible={false} renderOrder={31}>
          <ringGeometry args={[0.9, 1, 64]} />
        </mesh>
      ))}
    </>
  )
}
