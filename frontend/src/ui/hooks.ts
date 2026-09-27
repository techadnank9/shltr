import { useEffect, useState, useSyncExternalStore } from 'react'
import { source } from '../events/pick'

/** Source clock for UI timing windows, sampled a few times a second. */
export function useNow(hz = 12) {
  const [now, setNow] = useState(() => source.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(source.now()), 1000 / hz)
    return () => clearInterval(id)
  }, [hz])
  return now
}

const noop = () => () => {}

/** Re-render when fake playback state changes; null for the live source. */
export function usePlayback() {
  const pb = source.playback
  useSyncExternalStore(pb ? pb.subscribe : noop, () => (pb ? pb.playing() : false))
  return pb ?? null
}

export const clock = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`
