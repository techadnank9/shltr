// Builds the Sheltr pitch deck (out/sheltr-deck.pptx) with pptxgenjs. Same story and palette as the demo video.
const pptxgen = require('pptxgenjs')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const Fi = require('react-icons/fi')
const sharp = require('sharp')
const path = require('path')

const C = { ink: '0B1216', panel: '0F1A1F', line: '22343C', text: 'E6ECEE', muted: '8FA3AA', amber: 'F2A33A', red: 'E5484D', water: '3FA7D6', ok: '4CC38A', white: 'FFFFFF' }
const H = 'Arial', B = 'Calibri', M = 'Courier New'
const P = (p) => path.join(__dirname, p)

async function icon(name, color, px = 256) {
  const svg = renderToStaticMarkup(React.createElement(Fi[name], { color: '#' + color, size: px, strokeWidth: 1.75 }))
  const buf = await sharp(Buffer.from(svg)).png().toBuffer()
  return 'image/png;base64,' + buf.toString('base64')
}

async function main() {
  const pres = new pptxgen()
  pres.layout = 'LAYOUT_WIDE' // 13.33 x 7.5
  pres.author = 'Sheltr team'
  pres.title = 'Sheltr · Vultr Agent Arena 2026'

  const W = 13.33, HGT = 7.5
  const dark = (s) => { s.background = { color: C.ink } }
  const wordmark = (s, x, y, size) => s.addText([{ text: 'SHEL', options: { color: C.text } }, { text: 'TR', options: { color: C.amber } }],
    { x, y, w: size * 0.08, h: size / 60, fontFace: H, bold: true, fontSize: size, charSpacing: 1, margin: 0, isTextBox: true, valign: 'middle' })
  const tag = (s, text, x = 0.6, y = 0.45) => s.addText(text.toUpperCase(), { x, y, w: 9, h: 0.3, fontFace: M, fontSize: 11, color: C.muted, charSpacing: 3, margin: 0, isTextBox: true })
  const title = (s, text, y = 0.85, size = 34, w = 12) => s.addText(text, { x: 0.6, y, w, h: 1.1, fontFace: H, bold: true, fontSize: size, color: C.text, margin: 0, isTextBox: true, valign: 'top' })
  const footer = (s, n) => s.addText(`Sheltr · Vultr Agent Arena 2026 · Blast Radius Zero · ${n}`, { x: 0.6, y: HGT - 0.45, w: 12, h: 0.25, fontFace: M, fontSize: 9, color: C.muted, margin: 0, isTextBox: true })
  const body = (s, text, x, y, w, h, opts = {}) => {
    const { bullet, ...rest } = opts
    if (bullet && Array.isArray(text)) text = text.map((t) => ({ ...t, options: { ...t.options, bullet: { indent: 12 } } }))
    s.addText(text, { x, y, w, h, fontFace: B, fontSize: 16, color: C.text, margin: 0, isTextBox: true, valign: 'top', paraSpaceAfter: 6, ...rest })
  }
  const card = (s, x, y, w, h) => s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: C.panel }, line: { color: C.line, width: 0.75 }, rectRadius: 0.08 })
  const big = (s, n, label, x, y, w, color = C.text) => {
    s.addText(n, { x, y, w, h: 1.2, fontFace: H, bold: true, fontSize: 60, color, margin: 0, isTextBox: true, valign: 'bottom' })
    s.addText(label, { x, y: y + 1.25, w, h: 0.8, fontFace: B, fontSize: 15, color: C.muted, margin: 0, isTextBox: true, valign: 'top' })
  }
  const credit = (s, text, x, y, w = 6) => s.addText(text, { x, y, w, h: 0.25, fontFace: M, fontSize: 8, color: C.muted, margin: 0, isTextBox: true })
  const photo = (s, file, x, y, w, h, dim = 45) => {
    s.addImage({ path: P(file), x, y, w, h, sizing: { type: 'cover', w, h } })
    s.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: C.ink, transparency: 100 - dim }, line: { color: C.ink, transparency: 100 } })
  }
  let n = 0

  // 1 · Title
  {
    const s = pres.addSlide(); dark(s); n++
    photo(s, 'public/fema/liberty-ky.jpg', 0, 0, W, HGT, 78)
    wordmark(s, 0.8, 2.1, 96)
    s.addText([{ text: 'Safe shelter for storm survivors, ', options: { color: C.text } }, { text: 'and for the agent that helps them.', options: { color: C.muted } }],
      { x: 0.8, y: 3.95, w: 10.5, h: 0.6, fontFace: B, fontSize: 24, margin: 0, isTextBox: true })
    s.addText('VULTR AGENT ARENA 2026  ·  TRACK: BLAST RADIUS ZERO  ·  RIKIN SHAH & MOHAMMED ADNAN', { x: 0.8, y: 6.5, w: 12, h: 0.3, fontFace: M, fontSize: 10, color: C.muted, charSpacing: 3, margin: 0, isTextBox: true })
    credit(s, 'Background: Liberty, Kentucky, 2010 · FEMA photo by Liz Roll (public domain)', 0.8, 6.9, 8)
    s.addNotes('Sheltr turns a storm survivor\'s phone photos into a 3D model of the damaged room, finds and prices the damage, and fills in the aid application. Every risky step runs in a throwaway sandbox on Vultr.')
  }

  // 2 · The morning after
  {
    const s = pres.addSlide(); dark(s); n++
    photo(s, 'public/fema/belfry-ky.jpg', 6.9, 0, W - 6.9, HGT, 12)
    credit(s, 'Belfry, Kentucky, 2009 · FEMA photo by Rob Melendez', 7.1, 7.1, 6)
    tag(s, 'The morning after')
    title(s, 'Every family has to do\nthe same thing next.', 0.85, 36, 6)
    body(s, [
      { text: 'Prove what they lost. On a form. While everything is still wet.', options: { breakLine: true, bold: true, fontSize: 18 } },
      { text: 'Photograph every room, measure the damage, estimate repair costs, attach evidence, fill in a long application, and get it right the first time.', options: { breakLine: true } },
      { text: 'Meanwhile the scammers arrive: lookalike relief websites, fake agents, fake fees, texts that promise a payment in 24 hours.', options: {} },
    ], 0.6, 2.9, 5.9, 3.2)
    footer(s, n)
  }

  // 3 · Two numbers
  {
    const s = pres.addSlide(); dark(s); n++
    tag(s, 'Why it matters')
    title(s, 'The paperwork fails families. Fraud finds them.')
    card(s, 0.6, 2.2, 5.9, 3.9); card(s, 6.83, 2.2, 5.9, 3.9)
    big(s, '1.7 million', 'applicants FEMA found ineligible for Individuals and Households assistance, 2016 to 2018. A common reason: no evidence of the damage.', 1.0, 2.5, 5.2)
    big(s, '$9.3 billion', 'lost to post-disaster fraud in the United States in 2023, from fake relief sites to fake contractors.', 7.23, 2.5, 5.2, C.red)
    credit(s, 'Source: U.S. Government Accountability Office, GAO-20-503', 1.0, 5.6, 5.2)
    credit(s, 'Source: National Insurance Crime Bureau, cited in FTC and FCC consumer alerts', 7.23, 5.6, 5.4)
    footer(s, n)
  }

  // 4 · What Sheltr does
  {
    const s = pres.addSlide(); dark(s); n++
    tag(s, 'What Sheltr does')
    title(s, 'One photo in. A priced, evidence-backed claim out.', 0.85, 32)
    const rows = [
      ['FiCamera', 'The survivor takes a phone photo', 'Or a slow 10-second video of each damaged room. That is all we ask of them.'],
      ['FiBox', 'Sheltr rebuilds the room in 3D, in metres', 'A metric depth model runs inside a sealed microVM with the network off. The photo becomes a measurable room.'],
      ['FiCrosshair', 'The agent finds and prices the damage', 'glm-5.3 lists the damage, then writes its own measuring code. Failures come back as errors and it tries again, on screen.'],
      ['FiFileText', 'It fills in the aid application', 'Step by step in a browser sandbox, with a vision check on every screenshot. Nothing is submitted until the survivor taps approve.'],
    ]
    for (let i = 0; i < rows.length; i++) {
      const y = 2.05 + i * 1.22
      s.addShape(pres.ShapeType.ellipse, { x: 0.6, y, w: 0.8, h: 0.8, fill: { color: C.panel }, line: { color: C.line, width: 0.75 } })
      s.addImage({ data: await icon(rows[i][0], C.amber), x: 0.78, y: y + 0.18, w: 0.44, h: 0.44 })
      s.addText(rows[i][1], { x: 1.7, y: y - 0.02, w: 10.8, h: 0.4, fontFace: H, bold: true, fontSize: 18, color: C.text, margin: 0, isTextBox: true })
      s.addText(rows[i][2], { x: 1.7, y: y + 0.4, w: 10.8, h: 0.5, fontFace: B, fontSize: 14, color: C.muted, margin: 0, isTextBox: true })
    }
    footer(s, n)
  }

  // 5 · Live demo: every loss located
  {
    const s = pres.addSlide(); dark(s); n++
    s.addImage({ path: P('footage/check/fake_20.jpg'), x: 0, y: 0, w: W, h: HGT, sizing: { type: 'cover', w: W, h: HGT } })
    s.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: W, h: 1.6, fill: { color: C.ink, transparency: 25 }, line: { color: C.ink, transparency: 100 } })
    tag(s, 'The product · live on Vultr')
    title(s, 'Every loss, located and priced in the 3D room.', 0.8, 30)
    card(s, 8.7, 4.75, 4.2, 2.0)
    body(s, [
      { text: 'Six damage items pinned to the surfaces of the real room.glb', options: { breakLine: true } },
      { text: 'Each with a measurement (m², metres, count) and a repair estimate', options: { breakLine: true } },
      { text: 'Every sandbox in the log: started, what it did, destroyed', options: {} },
    ], 8.9, 4.9, 3.85, 1.8, { fontSize: 11.5, bullet: true, paraSpaceAfter: 4 })
    footer(s, n)
  }

  // 6 · The agent writes code, fails, retries
  {
    const s = pres.addSlide(); dark(s); n++
    tag(s, 'Agent autonomy, made visible')
    title(s, 'The agent writes its own measuring code.\nWhen it fails, you watch it recover.', 0.75, 30, 12)
    s.addImage({ path: P('footage/check/fake_12.jpg'), x: 0.6, y: 2.55, w: 7.4, h: 4.16 })
    card(s, 8.4, 2.55, 4.33, 4.16)
    body(s, [
      { text: 'Pattern A: code in a box', options: { bold: true, fontSize: 17, breakLine: true } },
      { text: 'glm-5.3 on Vultr Serverless Inference writes measure.py against the depth map and masks.', options: { breakLine: true } },
      { text: 'The runner executes it in a fresh microVM: 2 CPUs, 1 GB, no network, 3-second lifetime.', options: { breakLine: true } },
      { text: 'A KeyError comes back as data. The model rewrites the code. Attempt 2 passes.', options: { breakLine: true } },
      { text: 'The survivor sees every attempt in the sandbox log. No hidden magic.', options: {} },
    ], 8.65, 2.8, 3.85, 3.8, { fontSize: 13, paraSpaceAfter: 8 })
    footer(s, n)
  }

  // 7 · The containment moment
  {
    const s = pres.addSlide(); dark(s); n++
    tag(s, 'The containment moment')
    title(s, 'A fake aid site attacks the agent. The sandbox holds.', 0.85, 32)
    s.addImage({ path: P('footage/scam.png'), x: 0.6, y: 2.1, w: 5.6, h: 3.5, sizing: { type: 'crop', x: 0, y: 0, w: 16, h: 10 } })
    credit(s, 'disaster-relief-claims.help · our own lookalike test page, mapped inside the sandbox', 0.6, 5.65, 5.6)
    s.addImage({ path: P('deck-web/assets/contained.jpg'), x: 6.6, y: 2.1, w: 6.13, h: 3.45 })
    credit(s, 'Live case · browser microVM on VM 2 · two threats contained · destroyed after 6.5 s', 6.6, 5.65, 6)
    const threats = [['Forced malware download', 'relief-update.apk fires on page load. Captured inside the microVM and destroyed with it. It never reached the phone.'],
      ['Data theft', 'POST to 203.0.113.9/collect with the survivor\'s data and cookies. Not on the network allowlist: blocked.']]
    for (let i = 0; i < 2; i++) {
      const x = 0.6 + i * 6.2
      s.addShape(pres.ShapeType.rect, { x, y: 6.05, w: 0.12, h: 0.12, fill: { color: C.red }, line: { color: C.red } })
      s.addText(threats[i][0], { x: x + 0.25, y: 5.95, w: 5.6, h: 0.3, fontFace: H, bold: true, fontSize: 13, color: C.text, margin: 0, isTextBox: true })
      s.addText(threats[i][1], { x: x + 0.25, y: 6.25, w: 5.6, h: 0.7, fontFace: B, fontSize: 10.5, color: C.muted, margin: 0, isTextBox: true })
    }
  }

  // 8 · Architecture
  {
    const s = pres.addSlide(); dark(s); n++
    tag(s, 'Under the hood')
    title(s, 'Two Vultr machines. One private network.', 0.85, 34)
    // phone
    s.addShape(pres.ShapeType.roundRect, { x: 0.6, y: 3.2, w: 1.7, h: 1.3, fill: { color: C.panel }, line: { color: C.line, width: 0.75 }, rectRadius: 0.08 })
    s.addImage({ data: await icon('FiSmartphone', C.muted), x: 1.2, y: 3.32, w: 0.5, h: 0.5 })
    s.addText('Survivor\nHTTPS · approve / decline', { x: 0.6, y: 3.85, w: 1.7, h: 0.6, fontFace: M, fontSize: 8, color: C.muted, align: 'center', margin: 0, isTextBox: true })
    s.addShape(pres.ShapeType.line, { x: 2.3, y: 3.85, w: 0.6, h: 0, line: { color: C.line, width: 1.5 } })
    // VM1
    s.addShape(pres.ShapeType.roundRect, { x: 2.9, y: 2.05, w: 4.6, h: 4.5, fill: { color: C.panel }, line: { color: C.amber, width: 1.5 }, rectRadius: 0.08 })
    s.addText('VM 1 · CONTROL PLANE', { x: 3.15, y: 2.2, w: 4.2, h: 0.4, fontFace: H, bold: true, fontSize: 16, color: C.text, margin: 0, isTextBox: true })
    s.addText('Vultr Cloud Compute · 10.40.0.3 · public HTTPS via Caddy', { x: 3.15, y: 2.6, w: 4.2, h: 0.3, fontFace: M, fontSize: 8.5, color: C.amber, margin: 0, isTextBox: true })
    body(s, [
      { text: 'FastAPI, SQLite case store, WebSocket with replay', options: { breakLine: true } },
      { text: 'Planner on glm-5.3, Vultr Serverless Inference', options: { breakLine: true } },
      { text: 'Holds every API key. Keys never enter a sandbox', options: { breakLine: true } },
      { text: 'Never runs untrusted code, never opens untrusted pages', options: { breakLine: true } },
      { text: 'Approval gate: nothing is submitted without a human', options: {} },
    ], 3.15, 3.05, 4.2, 3.3, { fontSize: 12.5, bullet: true, paraSpaceAfter: 7 })
    s.addShape(pres.ShapeType.line, { x: 7.5, y: 3.85, w: 0.6, h: 0, line: { color: C.line, width: 1.5 } })
    s.addText('VPC only\ntoken auth', { x: 7.4, y: 3.95, w: 0.8, h: 0.4, fontFace: M, fontSize: 7.5, color: C.muted, align: 'center', margin: 0, isTextBox: true })
    // VM2
    s.addShape(pres.ShapeType.roundRect, { x: 8.1, y: 2.05, w: 4.63, h: 4.5, fill: { color: C.panel }, line: { color: C.water, width: 1.5 }, rectRadius: 0.08 })
    s.addText('VM 2 · SANDBOX HOST', { x: 8.35, y: 2.2, w: 4.2, h: 0.4, fontFace: H, bold: true, fontSize: 16, color: C.text, margin: 0, isTextBox: true })
    s.addText('Vultr VX1 · 10.40.0.4 · closed to the internet', { x: 8.35, y: 2.6, w: 4.2, h: 0.3, fontFace: M, fontSize: 8.5, color: C.water, margin: 0, isTextBox: true })
    s.addText('Runner: one fresh Microsandbox microVM per task', { x: 8.35, y: 3.0, w: 4.2, h: 0.3, fontFace: B, fontSize: 12, color: C.muted, margin: 0, isTextBox: true })
    const vms = [['photo microVM', 'depth model · own kernel · no network · 23 s'], ['code microVM', 'agent-written measuring code · 3 s'], ['browser microVM', 'Chromium + Playwright · allowlist: our demo server · 6 s']]
    for (let i = 0; i < 3; i++) {
      const y = 3.45 + i * 0.95
      s.addShape(pres.ShapeType.roundRect, { x: 8.35, y, w: 4.15, h: 0.8, fill: { color: C.ink }, line: { color: C.ok, width: 1, dashType: 'dash' }, rectRadius: 0.06 })
      s.addText(vms[i][0], { x: 8.5, y: y + 0.08, w: 3.0, h: 0.3, fontFace: M, fontSize: 10.5, color: C.text, margin: 0, isTextBox: true })
      s.addText(vms[i][1], { x: 8.5, y: y + 0.4, w: 3.9, h: 0.3, fontFace: B, fontSize: 10, color: C.muted, margin: 0, isTextBox: true })
      s.addText('DESTROYED', { x: 11.25, y: y + 0.08, w: 1.2, h: 0.3, fontFace: M, fontSize: 8, color: C.red, align: 'right', margin: 0, isTextBox: true })
    }
    footer(s, n)
  }

  // 9 · Sandbox rules table
  {
    const s = pres.addSlide(); dark(s); n++
    tag(s, 'Blast radius zero')
    title(s, 'Every risky step gets its own box. Then the box is gone.', 0.85, 30)
    const hdr = { bold: true, color: C.muted, fontFace: M, fontSize: 9.5, fill: { color: C.panel } }
    const cell = { color: C.text, fontFace: B, fontSize: 12.5, fill: { color: C.ink } }
    const rows = [
      ['TASK', 'RUNS IN', 'NETWORK', 'LIMITS', 'LIFETIME', 'WHAT LEAVES THE BOX'].map((t) => ({ text: t, options: hdr })),
      ['Rebuild the room from a photo or video', 'Microsandbox microVM, own kernel, read-only root', 'None', '4 vCPU · 3 GB · 180 s', 'about 23 s, then destroyed', 'room.glb, depth.png, a metadata-free photo.jpg, stats.json'],
      ['Measure and price the damage (agent-written code)', 'Microsandbox microVM', 'None', '2 vCPU · 1 GB · 60 s', 'about 3 s, then destroyed', 'One JSON of items and costs, or the error text'],
      ['Open a suspicious link', 'Browser microVM, Chromium + Playwright', 'Allowlist: our demo server only', '2 vCPU · 2 GB · 120 s', 'about 6 s, then destroyed', 'Screenshot, contained threats, verdict'],
      ['Fill in the aid application', 'Browser microVM', 'Allowlist: our mock portal only', '2 vCPU · 2 GB · 180 s', 'Until approval or timeout', 'Screenshots per step, receipt id'],
      ['Hold API keys and the case record', 'VM 1 only, never a sandbox', 'Public HTTPS in, private VPC out', '', 'Always on', 'Events to the survivor over WebSocket'],
    ].map((r, i) => i === 0 ? r : r.map((t) => ({ text: t, options: cell })))
    s.addTable(rows, { x: 0.6, y: 2.05, w: 12.13, colW: [2.5, 2.4, 1.9, 1.7, 1.63, 2.0], border: { type: 'solid', color: C.line, pt: 0.5 }, rowH: 0.62, margin: 0.08, valign: 'middle' })
    credit(s, 'Smoke tests on the live servers: sandbox kernel 6.12 vs host 6.8 · outbound blocked · endless loop killed at 15 s · nothing left running · VM 2 closed on 22/80/443 from the internet', 0.6, 6.55, 12)
    footer(s, n)
  }

  // 10 · Real numbers
  {
    const s = pres.addSlide(); dark(s); n++
    s.addImage({ path: P('footage/check/live2_46.jpg'), x: 0, y: 0, w: W, h: HGT, sizing: { type: 'cover', w: W, h: HGT } })
    s.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: W, h: HGT, fill: { color: C.ink, transparency: 12 }, line: { color: C.ink, transparency: 100 } })
    tag(s, 'This is real · a FEMA photo through the public URL, this morning')
    title(s, 'Photo to priced claim in 34 seconds.', 0.85, 36)
    const cells = [['34 s', 'end to end, photo upload to estimate'], ['5', 'damage items, each pinned in the 3D room'], ['$1,960', 'repair estimate, ±25 %, from agent-written code'], ['3 → 0', 'sandboxes started, sandboxes left running']]
    for (let i = 0; i < 4; i++) {
      const x = 0.6 + (i % 2) * 6.3, y = 2.3 + Math.floor(i / 2) * 2.2
      big(s, cells[i][0], cells[i][1], x, y, 5.5)
    }
    credit(s, 'Also: control-plane end-to-end test 7/7 · runner regression 11/11 · smoke tests 8/8 · both servers about $0.18 per hour', 0.6, 6.75, 12)
    footer(s, n)
  }

  // 11 · Built at the event
  {
    const s = pres.addSlide(); dark(s); n++
    tag(s, 'Built in 36 hours, all of it on Vultr')
    title(s, 'What is live, and what comes next.', 0.85, 36)
    card(s, 0.6, 2.05, 6.0, 4.6); card(s, 6.83, 2.05, 5.9, 4.6)
    s.addText('LIVE NOW', { x: 0.9, y: 2.25, w: 5, h: 0.3, fontFace: M, fontSize: 10, color: C.ok, charSpacing: 3, margin: 0, isTextBox: true })
    body(s, [
      { text: 'Public app at 45-76-251-95.sslip.io: upload, live 3D scene, damage ledger, sandbox log', options: { breakLine: true } },
      { text: 'Photo and video sandbox: Depth Anything V2 metric-indoor, textured mesh, 250k+ vertices', options: { breakLine: true } },
      { text: 'Planner and judge on glm-5.3, Vultr Serverless Inference', options: { breakLine: true } },
      { text: 'Runner with per-job microVMs, token auth, private network only', options: { breakLine: true } },
      { text: 'Link check: forced download and data theft contained, plain-language verdict', options: { breakLine: true } },
      { text: 'Front end on a versioned event contract, fake and live sources', options: {} },
    ], 0.9, 2.65, 5.4, 3.8, { fontSize: 12.5, bullet: true, paraSpaceAfter: 7 })
    s.addText('NEXT', { x: 7.13, y: 2.25, w: 5, h: 0.3, fontFace: M, fontSize: 10, color: C.amber, charSpacing: 3, margin: 0, isTextBox: true })
    body(s, [
      { text: 'Mock aid portal and form filling with the approval gate, end to end on the live servers', options: { breakLine: true } },
      { text: 'Multi-room cases and video walk-throughs stitched into one home', options: { breakLine: true } },
      { text: 'Export packs for insurers and legal aid: the 3D room, measurements, receipts', options: { breakLine: true } },
      { text: 'Partner with disaster legal-aid clinics for the first real pilots', options: {} },
    ], 7.13, 2.65, 5.3, 3.8, { fontSize: 12.5, bullet: true, paraSpaceAfter: 7 })
    footer(s, n)
  }

  // 12 · Close
  {
    const s = pres.addSlide(); dark(s); n++
    photo(s, 'public/fema/ponce-pr.jpg', 0, 0, W, HGT, 84)
    s.addText('After the storm, the hardest part\nshouldn\'t be the paperwork.', { x: 0.8, y: 1.6, w: 11.5, h: 2.0, fontFace: H, bold: true, fontSize: 44, color: C.text, margin: 0, isTextBox: true })
    wordmark(s, 0.8, 4.0, 60)
    s.addText('45-76-251-95.sslip.io  ·  github.com/techadnank9/shltr', { x: 0.8, y: 5.3, w: 11, h: 0.35, fontFace: M, fontSize: 13, color: C.text, margin: 0, isTextBox: true })
    s.addText('Rikin Shah · Mohammed Adnan  ·  Vultr Agent Arena 2026 · Blast Radius Zero', { x: 0.8, y: 5.7, w: 11, h: 0.35, fontFace: M, fontSize: 11, color: C.muted, margin: 0, isTextBox: true })
    credit(s, 'Background: Ponce, Puerto Rico, 2008 · FEMA photo by Andrea Booher (public domain)', 0.8, 6.9, 8)
  }

  const out = P('out/sheltr-deck.pptx')
  await pres.writeFile({ fileName: out })
  console.log('wrote', out, n, 'slides')
}
main().catch((e) => { console.error(e); process.exit(1) })
