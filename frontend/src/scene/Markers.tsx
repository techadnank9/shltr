import { Billboard, Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { source } from '../events/pick'
import { useCase, usd, type Damage } from '../store'
import { COLORS, reducedMotion } from './shared'

/** One pulsing red marker per damage.found, at its position in room.glb metres. */
export function Markers() {
  const damages = useCase((s) => s.damages)
  const room = useCase((s) => s.room)
  if (!room) return null
  return (
    <>
      {damages.map((d) => (
        <Marker key={d.id} d={d} />
      ))}
    </>
  )
}

const RED_HOT = COLORS.red.clone().multiplyScalar(2.2) // over 1, so bloom picks it up

function Marker({ d }: { d: Damage }) {
  const ring = useRef<THREE.Mesh>(null)
  const group = useRef<THREE.Group>(null)
  const label = useRef<HTMLDivElement>(null)
  const ringMat = useMemo(() => new THREE.MeshBasicMaterial({ color: RED_HOT, transparent: true, depthTest: false, toneMapped: false, side: THREE.DoubleSide }), [])
  const dotMat = useMemo(() => new THREE.MeshBasicMaterial({ color: RED_HOT, transparent: true, depthTest: false, toneMapped: false }), [])

  useFrame(({ clock }) => {
    const s = useCase.getState()
    const now = source.now()
    const age = now - d.t
    const k = reducedMotion ? 1 : Math.min(1, Math.max(0, age / 0.4))
    const pulse = reducedMotion ? 1 : 1 + Math.sin(clock.elapsedTime * 4 + d.n) * 0.18
    ringMat.opacity = k
    dotMat.opacity = k
    ring.current?.scale.setScalar(pulse * (0.4 + 0.6 * k))
    // Labels step aside while the containment scene plays.
    const sinceThreat = s.threats.length ? now - s.threats[s.threats.length - 1].t : 99
    const hide = s.stage === 4 && sinceThreat < 4.5
    if (label.current) label.current.style.opacity = hide ? '0' : String(k)
    if (group.current) group.current.visible = age >= 0
  })

  return (
    <group ref={group} position={d.position}>
      <Billboard>
        <mesh ref={ring} material={ringMat} renderOrder={20}>
          <ringGeometry args={[0.11, 0.15, 40]} />
        </mesh>
        <mesh material={dotMat} renderOrder={21}>
          <circleGeometry args={[0.045, 20]} />
        </mesh>
      </Billboard>
      <Html zIndexRange={[3, 0]} style={{ pointerEvents: 'none' }}>
        <div ref={label} className="pin">
          <b>{String(d.n).padStart(2, '0')}</b>
          <span>{d.label}</span>
          <em>{usd(d.cost)}</em>
        </div>
      </Html>
    </group>
  )
}
