// Records app footage for the demo video with Playwright (headed Chromium so WebGL uses the GPU).
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'
const BASE = 'https://45-76-251-95.sslip.io'
const OUT = path.resolve('footage')
fs.mkdirSync(OUT, { recursive: true })
const which = process.argv[2] || 'all'
const args = ['--autoplay-policy=no-user-gesture-required', '--hide-scrollbars', '--force-device-scale-factor=1']

async function withRecording(name, fn) {
  const browser = await chromium.launch({ headless: false, args })
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1,
    recordVideo: { dir: OUT, size: { width: 1920, height: 1080 } }, acceptDownloads: true })
  const page = await ctx.newPage()
  const t0 = Date.now(); const marks = {}
  const mark = (k) => { marks[k] = (Date.now() - t0) / 1000; console.log(name, k, marks[k].toFixed(1) + 's') }
  try { await fn(page, mark, ctx) } catch (e) { console.error(name, 'ERROR', e.message); marks.error = e.message }
  await ctx.close()
  const v = await page.video().path()
  fs.renameSync(v, path.join(OUT, name + '.webm'))
  fs.writeFileSync(path.join(OUT, name + '.marks.json'), JSON.stringify(marks, null, 1))
  await browser.close()
}

if (which === 'all' || which === 'fake') {
  await withRecording('fake', async (page, mark) => {
    await page.goto(BASE + '/?source=fake', { waitUntil: 'networkidle' })
    mark('loaded')
    const approve = page.getByRole('button', { name: 'Approve and submit' })
    await approve.waitFor({ timeout: 60000 })
    mark('approve_visible')
    await page.waitForTimeout(2500)
    await approve.click(); mark('approved')
    await page.getByText('Submitted. Receipt').waitFor({ timeout: 30000 }).catch(() => {})
    mark('receipt')
    await page.waitForTimeout(5000)
  })
}

if (which === 'all' || which === 'live') {
  await withRecording(process.env.LIVE_NAME || 'live', async (page, mark, ctx) => {
    await page.goto(BASE + '/start', { waitUntil: 'networkidle' })
    mark('start_loaded')
    await page.waitForTimeout(1500)
    await page.fill('#title', '14 Alder Lane, ground floor')
    await page.setInputFiles('#file', path.resolve('../test-photos/fema/liberty-ky.jpg'))
    await page.waitForTimeout(1200)
    await page.click('#go'); mark('uploaded')
    await page.waitForURL((u) => !u.pathname.endsWith('/start'), { timeout: 60000 })
    const caseUrl = page.url(); const caseId = new URL(caseUrl).searchParams.get('case') || caseUrl.match(/c_[0-9a-f]+/)?.[0]
    console.log('case', caseUrl, caseId); mark('case_page')
    // wait for the estimate (the ledger total) or 75 s
    await page.getByText(/\$\s?[1-9][0-9,]{2,}/).first().waitFor({ timeout: 110000 }).catch(() => {})
    mark('estimate'); await page.waitForTimeout(7000)
    // containment moment: ask the control plane to check the lookalike link
    const r = await page.request.post(`${BASE}/api/cases/${caseId}/check-link`, { data: { url: 'http://disaster-relief-claims.help/scam/' } })
    console.log('check-link', r.status()); mark('check_link_sent')
    await page.getByText(/threat|contained|quarantin|blocked/i).first().waitFor({ timeout: 60000 }).catch(() => {})
    mark('contained')
    await page.getByText(/verdict|is a scam|looks like a scam|scam\b/i).first().waitFor({ timeout: 60000 }).catch(() => {})
    mark('verdict')
    await page.waitForTimeout(10000)
    mark('end')
    fs.writeFileSync(path.join(OUT, 'live.case.txt'), `${caseId}\n${caseUrl}\n`)
  })
}

if (which === 'all' || which === 'shots') {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, acceptDownloads: true })
  const page = await ctx.newPage()
  await page.goto('file://' + path.resolve('../sandboxes/browser/testsite/scam/index.html'))
  await page.waitForTimeout(800)
  await page.screenshot({ path: path.join(OUT, 'scam.png') })
  await page.goto(BASE + '/start', { waitUntil: 'networkidle' }); await page.waitForTimeout(1000)
  await page.screenshot({ path: path.join(OUT, 'start.png') })
  for (const at of [7, 14, 18, 22, 27, 30]) {
    await page.goto(`${BASE}/?source=fake&at=${at}`, { waitUntil: 'networkidle' }); await page.waitForTimeout(3500)
    await page.screenshot({ path: path.join(OUT, `fake-at${at}.png`) })
  }
  await browser.close()
}
console.log('done', which)
