import { useEffect } from 'react'
import { source } from './events/pick'
import { Scene } from './scene/Scene'
import { useCase } from './store'
import { Ledger } from './ui/Ledger'
import { LogPanel } from './ui/LogPanel'
import { Overlays } from './ui/Overlays'
import { TopBar } from './ui/TopBar'

export function App() {
  useEffect(() => {
    const { dispatch, reset } = useCase.getState()
    source.start(dispatch, reset)
    return () => source.stop()
  }, [])

  return (
    <div className="app">
      <TopBar />
      <div className="stage">
        <Scene />
        <Overlays />
      </div>
      <LogPanel />
      <Ledger />
    </div>
  )
}
