import { create } from 'zustand'
import type { CaseEvent, SandboxKind, ThreatKind, Vec3 } from './events/types'

/** The six stages from the mockup, in order. */
export const STAGES = [
  { key: 'photo', label: 'Photo' },
  { key: 'depth', label: 'Depth' },
  { key: 'room', label: '3D room' },
  { key: 'damage', label: 'Damage' },
  { key: 'contain', label: 'Contained' },
  { key: 'claim', label: 'Claim' },
] as const
export type StageKey = (typeof STAGES)[number]['key']

// Every item remembers `t`: the source clock (seconds) when it arrived. Scene
// animations are "time since t", so seeking and pausing just work.
export type LogKind = 'run' | 'err' | 'model' | 'dispatch' | 'block' | 'ok' | 'wait' | 'code'
export interface LogItem { t: number; kind: LogKind; text: string; detail?: string }
export interface Sandbox { id: string; kind: SandboxKind; t: number; network: string; destroyedAt?: number; lifetime?: number }
export interface Damage { id: string; n: number; label: string; metric: string; cost: number; position: Vec3; t: number }
export interface Threat { kind: ThreatKind; detail: string; t: number }
export interface FormStep { n: number; total: number; title: string; screenshot: string; verified: boolean; note: string; t: number }
export interface Attempt { attempt: number; status: 'running' | 'failed' | 'passed'; t: number }
export type Answer = 'pending' | 'sent' | 'approved' | 'declined'

export interface CaseState {
  caseId: string | null
  createdAt: number | null
  photo: string | null
  plan: { id: string; title: string }[]
  sandboxes: Record<string, Sandbox>
  log: LogItem[]
  room: { url: string; vertices: number; median: number; t: number } | null
  attempts: Attempt[]
  damages: Damage[]
  total: { cost: number; rangePct: number } | null
  threats: Threat[]
  form: FormStep[]
  approval: { summary: string; amount: number; t: number; answer: Answer } | null
  receipt: { id: string; screenshot: string; t: number } | null
  error: string | null
  lastSeq: number
  missed: number
  /** Highest stage reached (index into STAGES), and when each was first reached. */
  stage: number
  stageAt: number[]
}

export const emptyCase = (): CaseState => ({
  caseId: null, createdAt: null, photo: null, plan: [], sandboxes: {}, log: [], room: null, attempts: [],
  damages: [], total: null, threats: [], form: [], approval: null, receipt: null, error: null,
  lastSeq: 0, missed: 0, stage: -1, stageAt: [],
})

export const usd = (n: number) => '$' + Math.round(n).toLocaleString('en-US')

const THREAT_TEXT: Record<ThreatKind, string> = {
  prompt_injection: 'prompt injection ignored',
  download: 'forced download quarantined',
  exfiltration: 'data exfiltration blocked',
  timeout: 'runaway task killed at the time limit',
  memory: 'runaway task killed at the memory limit',
}

/** Which stage an event moves the case into, if any. */
function stageOf(ev: CaseEvent): StageKey | null {
  switch (ev.type) {
    case 'case.created': return 'photo'
    case 'sandbox.started': return ev.data.kind === 'photo' ? 'depth' : null
    case 'depth.ready': return 'room'
    case 'code.attempt':
    case 'damage.found': return 'damage'
    case 'threat.contained': return 'contain'
    case 'form.step':
    case 'approval.needed':
    case 'claim.submitted': return 'claim'
    default: return null
  }
}

/** The one reducer: every event from the source goes through here. */
export function reduce(s: CaseState, ev: CaseEvent, t: number): CaseState {
  if (s.caseId && ev.case_id !== s.caseId) return s // not our case
  if (ev.seq <= s.lastSeq) return s // duplicate, e.g. after a reconnect
  const n: CaseState = { ...s, caseId: ev.case_id, lastSeq: ev.seq }
  const log = (kind: LogKind, text: string, detail?: string) => { n.log = [...n.log, { t, kind, text, detail }] }
  if (s.lastSeq && ev.seq > s.lastSeq + 1) {
    n.missed += ev.seq - s.lastSeq - 1
    log('err', `missed ${ev.seq - s.lastSeq - 1} event(s) · seq ${s.lastSeq} → ${ev.seq}`)
  }

  switch (ev.type) {
    case 'case.created':
      n.createdAt = t
      n.photo = ev.data.photos[0]?.url ?? null
      break
    case 'plan.ready':
      n.plan = ev.data.steps
      log('model', 'plan: ' + ev.data.steps.map((x) => x.title.toLowerCase()).join(' → '))
      break
    case 'sandbox.started': {
      const d = ev.data
      n.sandboxes = { ...n.sandboxes, [d.sandbox_id]: { id: d.sandbox_id, kind: d.kind, t, network: d.limits.network } }
      const tool = d.kind === 'photo' ? 'microVM' : 'Playwright · gVisor'
      log('dispatch', `dispatch → ${d.sandbox_id} · ${tool} · ${d.limits.cpus} vCPU · ${+(d.limits.memory_mb / 1024).toFixed(1)} GB · ${d.limits.timeout_s} s cap · network: ${d.limits.network}`)
      break
    }
    case 'log.line': {
      const d = ev.data
      const control = d.sandbox_id === 'control'
      const kind: LogKind = d.stream === 'stderr' ? 'err' : control && d.text.startsWith('glm') ? 'model' : 'run'
      log(kind, (control ? '' : `${d.sandbox_id}  `) + d.text)
      break
    }
    case 'depth.ready':
      n.room = { url: ev.data.glb_url, vertices: ev.data.vertices, median: ev.data.median_depth_m, t }
      log('ok', `3D room ready · ${ev.data.vertices.toLocaleString('en-US')} vertices · median depth ${ev.data.median_depth_m.toFixed(1)} m`)
      break
    case 'code.attempt': {
      const d = ev.data
      n.attempts = [...n.attempts.filter((a) => a.attempt !== d.attempt), { attempt: d.attempt, status: d.status, t }]
      if (d.status === 'running') log('code', `attempt ${d.attempt} · running agent-written measure.py`, d.code)
      else if (d.status === 'failed') log('err', `attempt ${d.attempt} · failed · error sent back to the model`, d.stderr)
      else log('ok', `attempt ${d.attempt} · passed · exit 0`)
      break
    }
    case 'damage.found': {
      const d = ev.data
      if (n.damages.some((x) => x.id === d.id)) break
      n.damages = [...n.damages, { id: d.id, n: n.damages.length + 1, label: d.label, metric: d.metric, cost: d.cost_usd, position: d.position, t }]
      log('run', `found ${n.damages.length}: ${d.label.toLowerCase()} · ${usd(d.cost_usd)}`)
      break
    }
    case 'estimate.total':
      n.total = { cost: ev.data.cost_usd, rangePct: ev.data.range_pct }
      log('ok', `estimate ${usd(ev.data.cost_usd)} ±${ev.data.range_pct}%`)
      break
    case 'threat.contained':
      n.threats = [...n.threats, { kind: ev.data.kind, detail: ev.data.detail, t }]
      log('block', `${ev.data.sandbox_id}  ${THREAT_TEXT[ev.data.kind]} · ${ev.data.detail}`)
      break
    case 'form.step': {
      const d = ev.data
      const step = { n: d.n, total: d.total, title: d.title, screenshot: d.screenshot_url, verified: d.verified, note: d.note, t }
      n.form = [...n.form.filter((f) => f.n !== d.n), step].sort((a, b) => a.n - b.n)
      log('run', `form ${d.n}/${d.total} ${d.title.toLowerCase()} · ${d.verified ? 'screenshot verified' : 'screenshot NOT verified'}`)
      break
    }
    case 'approval.needed':
      n.approval = { summary: ev.data.summary, amount: ev.data.amount_usd, t, answer: 'pending' }
      log('wait', 'paused before submit · waiting for survivor approval')
      break
    case 'approval.result':
      if (n.approval) n.approval = { ...n.approval, answer: ev.data.approved ? 'approved' : 'declined' }
      break
    case 'claim.submitted':
      n.receipt = { id: ev.data.receipt_id, screenshot: ev.data.screenshot_url, t }
      log('ok', `receipt ${ev.data.receipt_id} saved to the case`)
      break
    case 'sandbox.destroyed': {
      const d = ev.data
      const sb = n.sandboxes[d.sandbox_id]
      if (sb) n.sandboxes = { ...n.sandboxes, [d.sandbox_id]: { ...sb, destroyedAt: t, lifetime: d.lifetime_s } }
      const left = Object.values(n.sandboxes).filter((x) => x.destroyedAt === undefined).length
      log('ok', `${d.sandbox_id} destroyed after ${d.lifetime_s.toFixed(1)} s · ${left} sandbox${left === 1 ? '' : 'es'} running`)
      break
    }
    case 'case.error':
      n.error = ev.data.message
      log('err', ev.data.message)
      break
  }

  const st = stageOf(ev)
  if (st) {
    const i = STAGES.findIndex((x) => x.key === st)
    if (i > n.stage) {
      const at = [...n.stageAt]
      for (let k = n.stage + 1; k <= i; k++) at[k] = t
      n.stage = i
      n.stageAt = at
    }
  }
  return n
}

interface Store extends CaseState {
  dispatch: (ev: CaseEvent, t: number) => void
  reset: () => void
  answerSent: () => void
}

export const useCase = create<Store>((set) => ({
  ...emptyCase(),
  dispatch: (ev, t) => set((s) => reduce(s, ev, t)),
  reset: () => set(emptyCase()),
  answerSent: () => set((s) => (s.approval ? { approval: { ...s.approval, answer: 'sent' } } : {})),
}))
