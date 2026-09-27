import type { EventSource } from './source'
import type { CaseEvent, ClientMessage } from './types'

/**
 * Live events from the control plane at /ws/cases/{case_id} (docs/EVENTS.md).
 * Reconnects with backoff; the reducer drops duplicates by `seq`.
 */
export class WebSocketEventSource implements EventSource {
  readonly kind = 'ws' as const
  private ws: WebSocket | null = null
  private t0 = performance.now()
  private retry = 0
  private stopped = false
  private timer = 0
  private outbox: ClientMessage[] = []
  private onEvent: (ev: CaseEvent, t: number) => void = () => {}
  private readonly caseId: string
  private readonly url: string

  constructor(caseId: string, base?: string) {
    this.caseId = caseId
    const origin = base ?? `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`
    this.url = `${origin}/ws/cases/${encodeURIComponent(caseId)}`
  }

  start(onEvent: (ev: CaseEvent, t: number) => void) {
    this.onEvent = onEvent
    this.stopped = false
    this.connect()
  }

  private connect() {
    const ws = new WebSocket(this.url)
    this.ws = ws
    ws.onopen = () => {
      this.retry = 0
      this.outbox.splice(0).forEach((m) => ws.send(JSON.stringify(m)))
    }
    ws.onmessage = (msg) => {
      try {
        const ev = JSON.parse(msg.data as string) as CaseEvent
        if (ev && typeof ev.type === 'string' && typeof ev.seq === 'number') this.onEvent(ev, this.now())
      } catch {
        console.warn('[sheltr] ignored a malformed event')
      }
    }
    ws.onclose = () => {
      if (this.stopped) return
      const wait = Math.min(10_000, 500 * 2 ** this.retry++)
      this.timer = window.setTimeout(() => this.connect(), wait)
    }
  }

  send(msg: ClientMessage) {
    if (msg.case_id !== this.caseId) return
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg))
    else this.outbox.push(msg)
  }

  stop() {
    this.stopped = true
    clearTimeout(this.timer)
    this.ws?.close()
  }

  now() { return (performance.now() - this.t0) / 1000 }
}
