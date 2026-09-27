import { Billboard } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { source } from '../events/pick'
import { useCase, type Damage } from '../store'
import { COLORS, labelEls, placeLabel, reducedMotion } from './shared'

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
  const pos = useMemo(() => new THREE.Vector3(...d.position), [d.position])
  const ringMat = useMemo(() => new THREE.MeshBasicMaterial({ color: RED_HOT, transparent: true, depthTest: false, toneMapped: false, side: THREE.DoubleSide }), [])
  const dotMat = useMemo(() => new THREE.MeshBasicMaterial({ color: RED_HOT, transparent: true, depthTest: false, toneMapped: false }), [])

  useFrame(({ clock, camera, size }) => {
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
    const label = labelEls.get(d.id)
    if (label) {
      label.style.opacity = hide ? '0' : String(k)
      placeLabel(label, pos, camera, size.width, size.height, age >= 0)
    }
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
    </group>
  )
}
