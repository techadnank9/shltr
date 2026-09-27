import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { reducedMotion, useRoomBounds } from './shared'

const N = 2400

/** Rain outside the room and a wet ground plane, as in the mockup. */
export function Weather() {
  const box = useRoomBounds((s) => s.box)
  const pts = useRef<THREE.Points>(null)

  const geo = useMemo(() => {
    const b = box ?? new THREE.Box3(new THREE.Vector3(-4, -1.2, -9), new THREE.Vector3(2, 2.5, -1))
    const p = new Float32Array(N * 3)
    const cx = (b.min.x + b.max.x) / 2
    const cz = (b.min.z + b.max.z) / 2
    for (let i = 0; i < N; i++) {
      let x: number, z: number
      do {
        x = cx + (Math.random() - 0.5) * 30
        z = cz + (Math.random() - 0.5) * 30
      } while (x > b.min.x - 0.6 && x < b.max.x + 0.6 && z > b.min.z - 0.6 && z < b.max.z + 0.6)
      p.set([x, b.min.y + Math.random() * 10, z], i * 3)
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(p, 3))
    return g
  }, [box])

  const floorY = (box?.min.y ?? -1.2) - 0.03
  useFrame((_, dt) => {
    if (reducedMotion || !pts.current) return
    const a = geo.getAttribute('position') as THREE.BufferAttribute
    const arr = a.array as Float32Array
    for (let i = 1; i < arr.length; i += 3) {
      arr[i] -= dt * 9
      if (arr[i] < floorY) arr[i] += 10
    }
    a.needsUpdate = true
  })

  return (
    <>
      <points ref={pts} geometry={geo}>
        <pointsMaterial color="#9FB8C8" size={0.035} transparent opacity={0.5} depthWrite={false} />
      </points>
      <mesh rotation-x={-Math.PI / 2} position={[0, floorY, -5]}>
        <circleGeometry args={[32, 48]} />
        <meshStandardMaterial color="#0E171B" roughness={0.35} metalness={0.2} />
      </mesh>
    </>
  )
}
