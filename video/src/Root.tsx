import { Composition } from 'remotion'
import { Demo, FPS, totalFrames } from './Video'
export const RemotionRoot = () => (
  <Composition id="Demo" component={Demo} durationInFrames={totalFrames()} fps={FPS} width={1920} height={1080} />
)
