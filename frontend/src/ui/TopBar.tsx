import { source } from '../events/pick'
import { STAGES, useCase } from '../store'
import { usePlayback } from './hooks'

// Jumping lands a little before a stage so its lead-in plays (for Contained: the link check).
const LEAD: Record<string, number> = { contain: 1.8 }

export function TopBar() {
  const stage = useCase((s) => s.stage)
  const caseId = useCase((s) => s.caseId)
  const threats = useCase((s) => s.threats.length)
  const pb = usePlayback()

  const jump = (i: number) => {
    if (!pb) return
    const t = pb.stageTimes()[i]
    if (t !== undefined) pb.seek(Math.max(0, t - (LEAD[STAGES[i].key] ?? 0) + 0.01))
  }

  return (
    <header className="topbar">
      <div className="brand">
        <h1>Shel<span>tr</span></h1>
        <p>{caseId ? `Case ${caseId.replace(/^c_/, '').toUpperCase()} · 14 Alder Lane, ground floor` : 'Waiting for a case…'}</p>
      </div>
      <nav className="chips" aria-label="Stages">
        {STAGES.map((s, i) => {
          const cls = ['chip', i < stage && 'done', i === stage && 'now', i === stage && s.key === 'contain' && threats > 0 && 'alert'].filter(Boolean).join(' ')
          return (
            <button key={s.key} type="button" className={cls} aria-current={i === stage ? 'step' : undefined} disabled={!pb} onClick={() => jump(i)} title={pb ? `Jump to ${s.label}` : undefined}>
              <i />
              {s.label}
            </button>
          )
        })}
      </nav>
      {pb ? (
        <div className="transport">
          <button className="btn" type="button" onClick={() => (pb.playing() ? pb.pause() : pb.play())}>
            {pb.playing() ? 'Pause' : 'Play'}
          </button>
          <button className="btn" type="button" onClick={() => pb.replay()}>Replay</button>
        </div>
      ) : (
        <span className="mode live">live · {source.kind}</span>
      )}
    </header>
  )
}
