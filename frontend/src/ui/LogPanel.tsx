import { useEffect, useRef } from 'react'
import { useCase } from '../store'
import { clock } from './hooks'

/** Sandbox activity: log.line, code.attempt and the sandbox lifecycle, as they happen. */
export function LogPanel() {
  const log = useCase((s) => s.log)
  const createdAt = useCase((s) => s.createdAt) ?? 0
  const attempts = useCase((s) => s.attempts)
  const list = useRef<HTMLOListElement>(null)

  useEffect(() => {
    const el = list.current
    if (el) el.scrollTop = el.scrollHeight
  }, [log.length])

  const retry = attempts.length > 1 && attempts.some((a) => a.status === 'failed')
  return (
    <section className="panel log" aria-label="Sandbox activity">
      <h2>
        <span>Control plane · Vultr</span>
        {retry ? (
          <span className="retry">retry loop {attempts.map((a) => (a.status === 'passed' ? '✓' : a.status === 'failed' ? '✕' : '…')).join(' ')}</span>
        ) : (
          <span className="live">live</span>
        )}
      </h2>
      <ol ref={list} aria-live="polite">
        {log.map((l, i) => (
          <li key={i} className={l.kind}>
            <time>{clock(Math.max(0, l.t - createdAt))}</time>
            <span>
              {l.text}
              {l.detail && <pre>{l.detail}</pre>}
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}
