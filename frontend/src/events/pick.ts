import { FakeEventSource } from './fakeSource'
import type { EventSource } from './source'
import { WebSocketEventSource } from './wsSource'

/**
 * ?source=fake (default) replays the demo case; add &at=<seconds> to start part-way.
 * ?source=ws&case=<id> connects to the control plane (&api=wss://host to point elsewhere).
 */
export function pickSource(search = location.search): EventSource {
  const q = new URLSearchParams(search)
  if (q.get('source') === 'ws') return new WebSocketEventSource(q.get('case') ?? 'c_0927a', q.get('api') ?? undefined)
  return new FakeEventSource(Number(q.get('at')) || 0)
}

/** The one source for this page; components read time from it. */
export const source: EventSource = pickSource()
