// The live event contract from docs/EVENTS.md (draft v0). Keep in sync with that file.

export type SandboxKind = 'photo' | 'browser'
export type ThreatKind = 'prompt_injection' | 'download' | 'exfiltration' | 'timeout' | 'memory'
export type Vec3 = [number, number, number]

export interface EventData {
  'case.created': { photos: { id: string; url: string }[] }
  'plan.ready': { steps: { id: string; title: string }[] }
  'sandbox.started': {
    sandbox_id: string
    kind: SandboxKind
    limits: { cpus: number; memory_mb: number; timeout_s: number; network: string }
  }
  'log.line': { sandbox_id: string; stream: 'stdout' | 'stderr'; text: string }
  'depth.ready': { glb_url: string; vertices: number; median_depth_m: number }
  'code.attempt': { attempt: number; code: string; status: 'running' | 'failed' | 'passed'; stderr?: string }
  'damage.found': { id: string; label: string; metric: string; cost_usd: number; position: Vec3 }
  'estimate.total': { cost_usd: number; range_pct: number }
  'threat.contained': { sandbox_id: string; kind: ThreatKind; detail: string }
  'form.step': { n: number; total: number; title: string; screenshot_url: string; verified: boolean; note: string }
  'approval.needed': { summary: string; amount_usd: number }
  'approval.result': { approved: boolean }
  'claim.submitted': { receipt_id: string; screenshot_url: string }
  'sandbox.destroyed': { sandbox_id: string; lifetime_s: number }
  'case.error': { message: string }
}

export type EventType = keyof EventData

export type CaseEvent = {
  [K in EventType]: { type: K; case_id: string; seq: number; ts: string; data: EventData[K] }
}[EventType]

export type ClientMessage =
  | { type: 'approve'; case_id: string }
  | { type: 'decline'; case_id: string }
  | { type: 'check_link'; case_id: string; url: string }
