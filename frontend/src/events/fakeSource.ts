import demo from '../demo/case-0927a.json'
import { emptyCase, reduce } from '../store'
import type { EventSource, Playback } from './source'
import type { CaseEvent, ClientMessage, EventType } from './types'

interface Scripted { at: number; type: string; data: unknown }

/**
 * Replays the scripted demo case on a timeline. Answers approve / decline with
 * the scripted follow-up events, the way the control plane will.
 */
export class FakeEventSource implements EventSource {
  readonly kind = 'fake' as const
  readonly playback: Playback
  private script: Scripted[] = [...demo.events]
  private emitted = 0
  private seq = 0
  private clock = 0 // seconds of playback
  private last = 0
  private isPlaying = true
  private raf = 0
  private onEvent: (ev: CaseEvent, t: number) => void = () => {}
  private onReset: () => void = () => {}
  private listeners = new Set<() => void>()
  private stageTimes: number[] = []

  /** @param startAt start playback at this many seconds (the `?at=` URL flag). */
  constructor(private readonly startAt = 0) {
    this.playback = {
      playing: () => this.isPlaying,
      duration: () => demo.events[demo.events.length - 1].at,
      stageTimes: () => this.stageTimes,
      play: () => { this.isPlaying = true; this.notify() },
      pause: () => { this.isPlaying = false; this.notify() },
      replay: () => { this.isPlaying = true; this.seek(0) },
      seek: (t) => this.seek(t),
      subscribe: (fn) => { this.listeners.add(fn); return () => { this.listeners.delete(fn) } },
    }
  }

  private computeStageTimes() {
    // Run the real reducer over the script once, so chips jump exactly where each stage begins.
    let st = emptyCase()
    let seq = 0
    for (const e of demo.events) st = reduce(st, { type: e.type, case_id: demo.case_id, seq: ++seq, ts: '', data: e.data } as CaseEvent, e.at)
    this.stageTimes = st.stageAt
  }

  start(onEvent: (ev: CaseEvent, t: number) => void, onReset: () => void) {
    this.onEvent = onEvent
    this.onReset = onReset
    this.computeStageTimes()
    this.last = performance.now()
    const tick = (now: number) => {
      if (this.isPlaying) this.clock += Math.min(0.1, (now - this.last) / 1000)
      this.last = now
      this.flush()
      this.raf = requestAnimationFrame(tick)
    }
    this.raf = requestAnimationFrame(tick)
    if (this.startAt > 0) this.seek(this.startAt)
  }

  stop() { cancelAnimationFrame(this.raf) }
  now() { return this.clock }

  send(msg: ClientMessage) {
    if (msg.type === 'check_link') return
    const follow = msg.type === 'approve' ? demo.after_approve : demo.after_decline
    // Splice the scripted reply into the timeline, starting now.
    const base = this.clock
    this.script = [...this.script.slice(0, this.emitted), ...follow.map((e) => ({ ...e, at: base + e.at }))]
    this.isPlaying = true
    this.notify()
  }

  private seek(t: number) {
    this.script = [...demo.events]
    this.emitted = 0
    this.seq = 0
    this.clock = Math.max(0, t)
    this.onReset()
    this.flush() // everything up to t lands at once, stamped with its scripted time
    this.notify()
  }

  private flush() {
    while (this.emitted < this.script.length && this.script[this.emitted].at <= this.clock) {
      const e = this.script[this.emitted++]
      const ev = {
        type: e.type as EventType,
        case_id: demo.case_id,
        seq: ++this.seq,
        ts: new Date(Date.parse(demo.started) + e.at * 1000).toISOString(),
        data: e.data,
      } as CaseEvent
      this.onEvent(ev, e.at)
    }
  }

  private notify() { this.listeners.forEach((fn) => fn()) }
}
