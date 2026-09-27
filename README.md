# Sheltr

**Safe shelter for storm survivors, and for the agent that helps them.**

After a flood, families have to prove their losses to get aid, and scammers target them with fake relief websites the same week. Sheltr takes one phone photo or video of a damaged room. An agent on Vultr rebuilds the room in 3D, finds and prices the damage, writes a PDF evidence report, checks suspicious "aid" links in a sealed browser, and fills in the aid application live on screen. Nothing is submitted until the survivor approves it. Every risky step runs in a throwaway microVM that is destroyed afterwards.

Built during the Vultr Agent Arena Hackathon 2026 (September 26–27), track **Blast Radius Zero: Safe Agent Execution on Vultr**. Everything in this repository was written during the event.

**Live:** https://45-76-251-95.sslip.io/start (upload a photo) · a finished real case: https://45-76-251-95.sslip.io/case/c_3a778588

## What happens to one photo

| Step | Where it runs | What you see |
|---|---|---|
| 1. Rebuild the room in 3D | Photo microVM, no network | Textured 3D room (Depth Anything V2 metric indoor) |
| 2. Find the damage | glm-5.3 on Vultr Serverless Inference | Damaged items with boxes, severity and a price |
| 3. Measure it | glm-5.3 writes Python, run in a fresh microVM | The code, its output, and the retry when it fails (Pattern A) |
| 4. Evidence report | Report microVM | 4-page PDF: photo, damage table, 3D views, SHA-256 fingerprints, sandbox ids |
| 5. Check a scam link | Browser microVM, allowlisted network | The page tries a forced malware download and data theft; both are captured and blocked, then judged |
| 6. File the claim | Browser microVM, live frames | The agent fills the mock aid portal step by step, pauses for approval, submits, returns a receipt (Pattern B) |

## Containment (Blast Radius Zero)

- **Microsandbox microVMs** on a Vultr VX1 host: each job gets its own VM with `--no-net` plus a single allow rule, read-only input, a separate output folder, and CPU, memory and time limits. The VM is destroyed after the job.
- **Keys never enter a sandbox.** They stay on the control plane (VM 1). The sandbox host (VM 2) has no public ports and is reachable only inside the Vultr VPC.
- **Scam page containment:** the forced download is kept in quarantine inside the microVM (name, size and SHA-256 reported) and destroyed with it; the data-theft request is blocked by the network allowlist.
- **Human approval** before any submit. The agent only ever targets our own mock portal and fake scam page, never a real government site.

## Architecture

```
Browser ──HTTPS──> Caddy ──> Control plane (FastAPI, VM 1, Vultr Cloud Compute)
                               │  glm-5.3 via Vultr Serverless Inference
                               │  case store, WebSocket event stream (docs/EVENTS.md)
                               └─VPC─> Runner (FastAPI, VM 2, Vultr VX1)
                                         └─ Microsandbox microVMs: photo · code · report · browser
                                              └─VPC─> mock aid portal and fake scam page (VM 1, private)
```

Diagrams: [design/blueprint.html](design/blueprint.html). Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Decisions: [docs/DECISIONS.md](docs/DECISIONS.md).

## Repository

| Folder | Contents |
|---|---|
| `infra/` | Vultr API scripts: provision, bootstrap, smoke tests, teardown, multi-view room scan |
| `sandboxes/` | Photo, browser and report sandbox images |
| `backend/runner/` | Creates, watches and destroys microVMs; streams events |
| `backend/control/` | Control plane, agent, mission-control pages |
| `frontend/` | React and three.js 3D app |
| `sites/` | Mock aid portal and fake scam page |
| `datasets/` | Real public inputs (FEMA interiors, FloodNet drone frames) |

## Run it

```
cp .env.example .env                 # VULTR_API_KEY, VULTR_INFERENCE_KEY
python infra/provision.py --yes      # VM 1, VM 2, VPC, firewall
python infra/smoke_test.py           # sandbox checks
python infra/teardown.py --yes       # delete everything afterwards
```

## Data and credits

- Room photos: FEMA photo library, US federal government work, public domain.
- Drone frames: FloodNet (Hurricane Harvey), CDLA-Permissive-1.0.
- Multi-view scans at `/scan/<name>` are real captures, each labelled with its source.

`.env` is ignored by git. Keys are never copied into a sandbox, the front end or a log.
