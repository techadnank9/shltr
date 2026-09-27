# Sheltr

**Safe shelter for storm survivors, and for the agent that helps them.**

**The problem.** After a flood, a family has to prove every loss to get aid. In the same week, scammers put up fake relief websites to steal their money and identity. Professionals document damage with 3D digital twins: Matterport reports that ATI Restoration produced claim estimates 400% faster this way, in a year with 23 U.S. climate disasters and $115B of damage (2025) ([source](https://matterport.com/blog/disaster-restoration-mitigation), Feb 27 2026). But that needs a professional LiDAR camera, which a survivor does not have.

**What Sheltr does.** It gives the survivor that evidence from one phone photo. An agent on Vultr rebuilds the room in 3D, finds and prices the damage, writes a PDF evidence report, checks suspicious "aid" links, and fills in the aid application live on screen. Nothing is submitted until the survivor approves it.

**Why it is safe.** Blast Radius Zero: every risky step runs in a throwaway microVM that is destroyed afterwards. Keys never enter a sandbox.

Built during the Vultr Agent Arena Hackathon 2026 (September 26–27), track **Blast Radius Zero: Safe Agent Execution on Vultr**. Everything in this repository was written during the event.

## Try it live

| Link | What it is |
|---|---|
| https://45-76-251-95.sslip.io/story/ | The story site: the problem, the process and the safety model |
| https://45-76-251-95.sslip.io/start | Start a real case: upload a photo of a damaged room |
| https://45-76-251-95.sslip.io/case/c_3a778588 | A finished real case (FEMA photo, Liberty, KY) |

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
- **Human approval before any submit.** The survivor sees every field the agent typed and can correct any of them before approving. "Not yet" keeps the draft and the corrections. The submit itself runs in a fresh browser microVM that types the approved values.
- **Only our own targets.** The agent only ever reaches our mock aid portal and our fake scam page, never a real government site.

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
| `flood-flow/` | Story site, served at `/story/` |
| `backend/control/` | Control plane, agent, mission-control pages |
| `backend/runner/` | Creates, watches and destroys microVMs; streams events |
| `sandboxes/` | Photo, browser and report sandbox images |
| `sites/` | Mock aid portal and fake scam page |
| `frontend/` | React and three.js 3D app |
| `infra/` | Vultr API scripts: provision, bootstrap, smoke tests, teardown, multi-view room scan |
| `datasets/` | Real public inputs (FEMA interiors, FloodNet drone frames) |

## Run it

```
cp .env.example .env                 # VULTR_API_KEY, VULTR_INFERENCE_KEY
python infra/provision.py --yes      # VM 1, VM 2, VPC, firewall
python infra/smoke_test.py           # sandbox checks
python infra/teardown.py --yes       # delete everything afterwards
```

## Honesty notes

- **The 3D room comes from one photo**, through an AI depth model (Depth Anything V2 metric indoor). It is not LiDAR and not a multi-view scan. Measurements and prices are estimates, shown with a ±25% range.
- **Multi-view scanning is not finished.** A script exists (`infra/recon/scan_room.sh`, OpenDroneMap), but it has not produced a published model.
- **The aid portal and the scam site are our own mocks.** The agent never touches a real government site.
- **Case `c_554d2f42` uses an AI-generated image** and is labelled as such in its title. The case linked above uses a real FEMA photo.

## Data and credits

- Room photos: FEMA photo library, US federal government work, public domain.
- Drone frames: FloodNet (Hurricane Harvey), CDLA-Permissive-1.0.
- Industry figures above: Matterport, [Disaster restoration and mitigation](https://matterport.com/blog/disaster-restoration-mitigation), Feb 27 2026.

`.env` is ignored by git. Keys are never copied into a sandbox, the front end or a log.

## Team

Built during the hackathon (September 26–27, 2026) by Rikin ([Rikinshah787](https://github.com/Rikinshah787)) and Adnan ([techadnank9](https://github.com/techadnank9)).
