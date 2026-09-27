import { chromium } from 'playwright'
import path from 'node:path'
const b = await chromium.launch({ headless: true }); const p = await b.newPage({ viewport: { width: 1600, height: 900 } })
const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()) })
await p.goto('file://' + path.resolve('deck-web/index.html')); await p.waitForTimeout(3500)
const want = [1, 4, 5, 6, 8, 12, 13, 15, 16]; let i = 1
for (const n of want) { while (i < n) { await p.keyboard.press('ArrowRight'); i++; await p.waitForTimeout(700) } await p.waitForTimeout(n === 15 ? 12500 : 3200); await p.screenshot({ path: `deck-web/check-${n}.jpg`, quality: 60, type: 'jpeg' }) }
await p.setViewportSize({ width: 400, height: 800 }); await p.waitForTimeout(1500); await p.screenshot({ path: 'deck-web/check-phone.jpg', quality: 60, type: 'jpeg' })
console.log('errors:', errs.slice(0, 5)); await b.close()
