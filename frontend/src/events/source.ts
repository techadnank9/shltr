import type { CaseEvent, ClientMessage } from './types'

/** Where events come from. The UI only ever talks to this interface. */
export interface EventSource {
  readonly kind: 'fake' | 'ws'
  /** Start delivering events. `t` is the source clock (seconds) when the event arrived. */
  start(onEvent: (ev: CaseEvent, t: number) => void, onReset: () => void): void
  send(msg: ClientMessage): void
  stop(): void
  /** Seconds on this source's clock. Scene animations run on it, so pause freezes them. */
  now(): number
  /** Playback controls; only the fake source supports them. */
  playback?: Playback
}

export interface Playback {
  playing(): boolean
  duration(): number
  /** Playback time at which each stage (see STAGES) is first reached. */
  stageTimes(): number[]
  play(): void
  pause(): void
  replay(): void
  seek(t: number): void
  subscribe(fn: () => void): () => void
}
