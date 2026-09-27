# Shltr: guide for coding agents

Two people run coding agents on this repo at the same time: **Rikin** (GitHub `Rikinshah787`) and **Adnan** (GitHub `techadnank9`). Read this file before doing anything, and follow the working rules so the two agents don't overwrite each other.

Main repository: https://github.com/techadnank9/shltr

## What we're building

Shltr helps storm and flood survivors. A survivor uploads photos of a damaged room. An agent on Vultr turns them into a 3D model of the room, finds and prices the damage, and fills in the aid application. Every risky step runs in a throwaway sandbox on Vultr, and nothing is submitted until the survivor approves it. The containment moment is a fake aid website (the kind scammers set up after every disaster) that tries prompt injection, a forced download and data theft, and the sandbox holds.

Hackathon: Vultr Agent Arena 2026, track "Blast Radius Zero". Submissions are due **Sunday September 27, 12:00 PM PT**.

## Read next

| File | What it holds |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | The build split into small parts, each with an owner, a branch and a test |
| [docs/STATUS.md](docs/STATUS.md) | Who is working on what, right now. Update it. |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Choices already made and why. Don't reopen them without asking. |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, flows and sandbox rules |
| [docs/EVENTS.md](docs/EVENTS.md) | The live-event contract between backend and front end |
| [design/blueprint.html](design/blueprint.html) | The same architecture as diagrams (open in a browser) |
| [design/3d-mockup.html](design/3d-mockup.html) | Visual concept for the 3D front end |

## Working rules for both agents

1. **Pull before you start:** `git checkout main && git pull --rebase`.
2. **Claim work in [docs/STATUS.md](docs/STATUS.md) first.** Put your name on a workstream in your first PR. If someone else has claimed it, pick something else or ask your human.
3. **Every change goes through a clean pull request.** No direct pushes to `main`. One branch per topic, named `<owner>/<topic>` (for example `rikin/infra-setup`, `adnan/frontend-scene`). Keep each PR focused on one topic, and write a description the other agent can act on: what changed, why, how to test it, and anything the other side must do. There is no waiting for a human reviewer: after opening a PR, do a real review pass yourself (read the diff, scan for secrets, check the docs still match, confirm the tests actually ran), fix what you find, then merge.
4. **Stay inside your workstream's folder** (see the table below). If you must change a shared file (`docs/EVENTS.md`, `CLAUDE.md`, `README.md`), keep the edit small and call it out in the PR description.
5. **Keep docs and designs current in the same PR.** When you finish something or change a decision, update `docs/STATUS.md`, `docs/DECISIONS.md` and any design page that the change makes outdated.
6. **Never commit secrets.** Keys live in `.env` (ignored by git) on each laptop and on VM 1 only. Never copy keys into a sandbox, the front end or a log.
7. **Build everything inside this repository folder.** No work files in temp or home folders.
8. **Never make the agent submit to a real government website.** The browser agent only targets our own mock aid portal and our own fake scam page.
9. **Delete, don't stop, Vultr servers you no longer need.** Vultr bills stopped servers. Budget: stay under $30 of the $200 credit.

## Folder layout

| Folder | Workstream | Contents |
|---|---|---|
| `infra/` | Infrastructure | Vultr API scripts: create, bootstrap, smoke tests, teardown |
| `sandboxes/` | Sandboxes | Photo sandbox image (depth model, mesh), browser sandbox image |
| `backend/runner/` | Runner (VM 2) | Service that creates, watches and destroys sandboxes |
| `backend/control/` | Control plane (VM 1) | FastAPI, planner agent, case store, WebSocket, mock aid portal, fake scam page |
| `frontend/` | Front end | React + three.js app |
| `blender/` | 3D assets | Blender Python scripts and exported `.glb` assets |
| `design/` | Design | Mockups and diagrams |
| `docs/` | Shared | Status, decisions, architecture, event contract |

Folders are created by whoever starts that workstream.

## Stack in one line each

- Model: `glm-5.3` on Vultr Serverless Inference (`https://api.vultrinference.com/v1`, OpenAI-compatible), fallback `qwen3.8-27b`.
- Control plane: Python, FastAPI, SQLite, WebSocket.
- Photo sandbox: Microsandbox microVM on a Vultr VX1, Depth Anything V2 (metric indoor), trimesh.
- Browser sandbox: Playwright in Docker with the gVisor runtime (`--runtime=runsc`).
- Front end: React, three.js (React Three Fiber), Vite. Blender for polished assets.
