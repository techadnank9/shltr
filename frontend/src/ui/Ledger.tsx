import { source } from '../events/pick'
import { useCase, usd } from '../store'

/** Damage ledger with the running total, then the aid application and approval. */
export function Ledger() {
  const damages = useCase((s) => s.damages)
  const total = useCase((s) => s.total)
  const form = useCase((s) => s.form)
  const approval = useCase((s) => s.approval)
  const sum = total?.cost ?? damages.reduce((a, d) => a + d.cost, 0)

  return (
    <aside className="panel ledger" aria-label="Damage found">
      <h2>
        <span>Damage found</span>
        <span>{damages.length} item{damages.length === 1 ? '' : 's'}</span>
      </h2>
      <ul className="rows">
        {damages.map((d) => (
          <li key={d.id}>
            <b>{String(d.n).padStart(2, '0')}</b>
            <div>
              <strong>{d.label}</strong>
              <small>{d.metric}</small>
            </div>
            <em>{usd(d.cost)}</em>
          </li>
        ))}
        {damages.length === 0 && <li className="empty">Nothing yet. Damage shows up here as the agent finds it.</li>}
      </ul>
      <div className="total">
        <span>Estimated loss</span>
        <strong>{usd(sum)}</strong>
      </div>
      <p className="note">
        Measured by agent-written code inside the sandbox, checked by glm-5.3 on Vultr Serverless Inference.
        {total ? ` Estimate ±${total.rangePct}%.` : ''}
      </p>
      {(form.length > 0 || approval) && <Claim />}
    </aside>
  )
}

function Claim() {
  const form = useCase((s) => s.form)
  const approval = useCase((s) => s.approval)
  const receipt = useCase((s) => s.receipt)
  const caseId = useCase((s) => s.caseId)
  const answerSent = useCase((s) => s.answerSent)
  const total = form[0]?.total ?? 4
  const latest = form[form.length - 1]

  const answer = (type: 'approve' | 'decline') => {
    if (!caseId) return
    answerSent()
    source.send({ type, case_id: caseId })
  }

  return (
    <div className="claim">
      <h2>
        <span>Aid application</span>
        <span>browser sandbox</span>
      </h2>
      <ol className="steps">
        {Array.from({ length: total }, (_, i) => {
          const f = form.find((x) => x.n === i + 1)
          return (
            <li key={i} className={f ? (f.verified ? 'done' : 'bad') : ''}>
              <span>{f?.title ?? `Step ${i + 1}`}</span>
              {f && <small>{f.verified ? '✓ verified' : 'not verified'} · {f.note}</small>}
            </li>
          )
        })}
        <li className={receipt ? 'done' : approval?.answer === 'declined' ? '' : approval ? 'hold' : ''}>
          <span>Your approval</span>
        </li>
      </ol>
      {latest && !receipt && (
        <figure className="shot">
          <img src={latest.screenshot} alt={`Screenshot of form step ${latest.n}: ${latest.title}`} />
          <figcaption>
            step {latest.n} of {latest.total} · {latest.verified ? <b className="ok">✓ vision check passed</b> : <b className="bad">vision check failed</b>}
          </figcaption>
        </figure>
      )}
      {approval && !receipt && approval.answer !== 'declined' && (
        <div className="approve">
          <p>{approval.summary}</p>
          {approval.answer === 'pending' ? (
            <div className="actions">
              <button className="btn primary" type="button" onClick={() => answer('approve')}>
                Approve and submit
              </button>
              <button className="btn" type="button" onClick={() => answer('decline')}>Not yet</button>
            </div>
          ) : (
            <p className="pending">{approval.answer === 'sent' ? 'Sending your answer…' : 'Approved. Submitting inside the sandbox…'}</p>
          )}
        </div>
      )}
      {approval?.answer === 'declined' && <p className="receipt hold">Not yet. The draft is kept and nothing was submitted.</p>}
      {receipt && (
        <div className="receipt-box">
          <p className="receipt">
            Submitted. Receipt <b>{receipt.id}</b> and the screenshots are saved to your case. The browser sandbox has been destroyed.
          </p>
          <img src={receipt.screenshot} alt={`Receipt ${receipt.id}`} />
        </div>
      )}
    </div>
  )
}
