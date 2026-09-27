import { useGLTF } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { source } from '../events/pick'
import { useCase } from '../store'
import { COLORS, ease, ramp, reducedMotion, useRoomBounds } from './shared'

/**
 * The survivor's room, straight from the depth model's room.glb.
 * Reveal: the flat photo becomes a depth-coloured point cloud that pushes back
 * into 3D, then the solid coloured mesh fades in.
 */
export function Room({ url, readyAt }: { url: string; readyAt: number }) {
  const gltf = useGLTF(url)
  const setBounds = useRoomBounds((s) => s.set)

  const geometry = useMemo(() => {
    let found: THREE.BufferGeometry | null = null
    gltf.scene.updateMatrixWorld(true)
    gltf.scene.traverse((o) => {
      if (!found && (o as THREE.Mesh).isMesh) {
        found = (o as THREE.Mesh).geometry.clone().applyMatrix4(o.matrixWorld)
      }
    })
    const g = (found ?? new THREE.BufferGeometry()) as THREE.BufferGeometry
    // Vertex colours come from the photo (sRGB); glTF COLOR_0 is read as linear.
    const col = g.getAttribute('color') as THREE.BufferAttribute | undefined
    if (col) {
      const c = new THREE.Color()
      const out = new Float32Array(col.count * 3)
      for (let i = 0; i < col.count; i++) {
        c.setRGB(col.getX(i), col.getY(i), col.getZ(i), THREE.SRGBColorSpace)
        out.set([c.r, c.g, c.b], i * 3)
      }
      g.setAttribute('color', new THREE.BufferAttribute(out, 3))
    }
    g.computeBoundingBox()
    return g
  }, [gltf])

  useEffect(() => {
    setBounds(geometry.boundingBox!.clone())
    return () => setBounds(null)
  }, [geometry, setBounds])

  const solid = useMemo(
    () => new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0, side: THREE.DoubleSide, toneMapped: false, color: new THREE.Color(0.86, 0.86, 0.86) }),
    [],
  )
  const cloud = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        toneMapped: false,
        uniforms: {
          uGrow: { value: 0 },
          uOpacity: { value: 0 },
          uSize: { value: 4 },
          uNear: { value: COLORS.amber },
          uMid: { value: COLORS.red },
          uFar: { value: COLORS.water },
          uDepth: { value: new THREE.Vector2(1.3, 8.7) },
        },
        vertexShader: /* glsl */ `
          uniform float uGrow; uniform float uSize; uniform vec3 uNear; uniform vec3 uMid; uniform vec3 uFar; uniform vec2 uDepth;
          attribute vec3 color;
          varying vec3 vColor;
          void main() {
            float z = max(0.05, -position.z);
            // Start flat on a plane 2 m out (from the camera it looks exactly like the photo), then push back to true depth.
            vec3 flatP = position * (2.0 / z);
            vec3 p = mix(flatP, position, uGrow);
            float k = clamp((z - uDepth.x) / (uDepth.y - uDepth.x), 0.0, 1.0);
            vec3 dc = k < 0.5 ? mix(uNear, uMid, k * 2.0) : mix(uMid, uFar, (k - 0.5) * 2.0);
            vColor = mix(dc, color, 0.25);
            vec4 mv = modelViewMatrix * vec4(p, 1.0);
            gl_PointSize = uSize * (3.0 / max(0.5, -mv.z));
            gl_Position = projectionMatrix * mv;
          }`,
        fragmentShader: /* glsl */ `
          uniform float uOpacity; varying vec3 vColor;
          void main() {
            vec2 d = gl_PointCoord - 0.5;
            if (dot(d, d) > 0.25) discard;
            gl_FragColor = vec4(vColor * 0.95, uOpacity);
          }`,
      }),
    [],
  )

  useEffect(() => {
    const bb = geometry.boundingBox!
    cloud.uniforms.uDepth.value.set(Math.max(0.3, -bb.max.z), -bb.min.z)
  }, [geometry, cloud])

  const meshRef = useRef<THREE.Mesh>(null)
  const pointsRef = useRef<THREE.Points>(null)
  useFrame((state) => {
    const now = source.now()
    const s = now - readyAt
    const threats = useCase.getState().threats
    const lastHit = threats.length ? now - threats[threats.length - 1].t - 0.55 : -1
    const flash = lastHit >= 0 && lastHit < 2.6 ? 1 - lastHit / 2.6 : 0
    if (reducedMotion) {
      solid.opacity = s >= 0 ? 1 : 0
      cloud.uniforms.uOpacity.value = 0
    } else {
      solid.opacity = ramp(s, 3.2, 5.0)
      cloud.uniforms.uOpacity.value = 0.95 * ramp(s, 0, 0.6) * (1 - ramp(s, 3.6, 5.2))
      cloud.uniforms.uGrow.value = ease(ramp(s, 0.5, 3.3))
    }
    // The room dims and reddens while the alarm plays.
    solid.color.setRGB(0.86, 0.86 - 0.4 * flash, 0.86 - 0.4 * flash)
    cloud.uniforms.uSize.value = 4 * Math.min(2, state.viewport.dpr)
    if (meshRef.current) meshRef.current.visible = solid.opacity > 0.001
    if (pointsRef.current) pointsRef.current.visible = cloud.uniforms.uOpacity.value > 0.001
  })

  return (
    <group>
      <mesh ref={meshRef} geometry={geometry} material={solid} renderOrder={1} />
      <points ref={pointsRef} geometry={geometry} material={cloud} renderOrder={2} />
    </group>
  )
}
