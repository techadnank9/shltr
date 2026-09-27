import { source } from '../events/pick'
import type { ThreatKind } from '../events/types'
import { FLY } from '../scene/Sandbox'
import { labelEls } from '../scene/shared'
import { STAGES, useCase, usd } from '../store'
import { useNow } from './hooks'

const CAPTIONS: Record<string, [string, string]> = {
  photo: ['One photo in', 'The survivor snaps the room. Nothing else to fill in.'],
  depth: ['Photo becomes depth', 'A depth model runs inside a throwaway sandbox with the network off.'],
  room: ['The room, rebuilt', 'The real room from the depth model, in metres.'],
  damage: ['Every loss, located', 'The model writes code to measure the damage. It fails once, reads the error, and fixes it.'],
  contain: ['A fake aid site', 'A link from a text message tries to hijack the agent. The sandbox takes the hit.'],
  claim: ['Ready when you are', 'A sandboxed browser fills in the aid form and waits for your OK.'],
}

const KINDS: [ThreatKind, string][] = [
  ['download', 'Forced download'],
  ['exfiltration', 'Data theft'],
]
const ALARM = 2.6

/** HTML layers over the 3D stage: the photo, the alarm, captions. */
export function Overlays() {
  const now = useNow()
  const s = useCase()

  const photoOn = !!s.photo && (!s.room || now - s.room.t < 0.7)
  const scanning = photoOn && Object.values(s.sandboxes).some((x) => x.kind === 'photo' && x.destroyedAt === undefined)
  // From the first hit on the glass until 2.6 s after the last one.
  const hits = s.threats.map((t) => now - t.t - FLY)
  const alarmOn = hits.length > 0 && Math.max(...hits) >= 0 && Math.min(...hits) < ALARM
  const latest = [...s.threats].reverse().find((t) => now - t.t >= FLY)
  const cap = s.stage >= 0 ? CAPTIONS[STAGES[s.stage].key] : null
  const shutter = s.createdAt !== null && now >= s.createdAt && now - s.createdAt < 0.5

  return (
    <>
      <div className="labels">
        {s.damages.map((d) => (
          <div key={d.id} className="pin" ref={(el) => { if (el) labelEls.set(d.id, el); else labelEls.delete(d.id) }}>
            <div>
              <b>{String(d.n).padStart(2, '0')}</b>
              <span>{d.label}</span>
              <em>{usd(d.cost)}</em>
            </div>
          </div>
        ))}
        <div className="sbx-tag" ref={(el) => { if (el) labelEls.set('sandbox', el); else labelEls.delete('sandbox') }} />
      </div>
      <div className={`alarmwash${alarmOn ? ' on' : ''}`} />
      <figure className={`photoframe${photoOn ? ' on' : ''}${scanning ? ' scanning' : ''}`}>
        {s.photo && <img src={s.photo} alt="The survivor's photo of the room" />}
        <div className="scanline" />
        <figcaption>IMG_4471 · uploaded by survivor{scanning ? ' · depth model running' : ''}</figcaption>
      </figure>
      <div className={`alarm${alarmOn ? ' on' : ''}`} role="status">
        <h3>Contained</h3>
        <ul>
          {KINDS.map(([k, label]) => {
            const th = s.threats.find((t) => t.kind === k)
            return (
              <li key={k} className={th && now - th.t >= FLY ? 'hit' : ''}>
                ✕ {label}
              </li>
            )
          })}
        </ul>
        {latest && <p>Fake aid site blocked · {latest.detail}</p>}
      </div>
      <div className="proto">{source.kind === 'fake' ? 'Demo case · scripted events' : 'Live · control plane'}</div>
      {cap && (
        <div className="caption" key={cap[0]}>
          <strong>{cap[0]}</strong>
          <span>{cap[1]}</span>
        </div>
      )}
      {s.error && (
        <div className="error" role="alert">
          {s.error}
        </div>
      )}
      <div className={`shutter${shutter ? ' on' : ''}`} />
    </>
  )
}
