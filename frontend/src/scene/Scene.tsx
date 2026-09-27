import { Canvas } from '@react-three/fiber'
import { Bloom, EffectComposer, Vignette } from '@react-three/postprocessing'
import { Suspense } from 'react'
import { useCase } from '../store'
import { CameraDirector } from './CameraDirector'
import { Markers } from './Markers'
import { Room } from './Room'
import { Sandbox } from './Sandbox'
import { COLORS } from './shared'
import { Weather } from './Weather'

export function Scene() {
  const room = useCase((s) => s.room)
  return (
    <Canvas
      className="gl"
      dpr={[1, 1.75]}
      camera={{ position: [0, 0, 0], fov: 45, near: 0.05, far: 80 }}
      gl={{ antialias: false, powerPreference: 'high-performance' }}
      aria-label="3D reconstruction of the survivor's room"
    >
      <fogExp2 attach="fog" args={[COLORS.ink, 0.035]} />
      <ambientLight intensity={0.4} color="#9fb4c0" />
      <hemisphereLight args={['#8fb2c8', '#2a2016', 0.5]} />
      <Weather />
      <Suspense fallback={null}>
        {room && <Room key={room.url} url={room.url} readyAt={room.t} />}
      </Suspense>
      <Sandbox />
      <Markers />
      <CameraDirector />
      <EffectComposer multisampling={4}>
        <Bloom mipmapBlur intensity={0.9} luminanceThreshold={1} luminanceSmoothing={0.2} />
        <Vignette offset={0.3} darkness={0.7} />
      </EffectComposer>
    </Canvas>
  )
}
