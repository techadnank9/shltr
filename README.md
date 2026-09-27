# Sheltr

**Safe shelter for storm survivors, and for the agent that helps them.**

After a flood or hurricane, families have to prove their losses to get aid, while scammers target them with fake relief websites. Sheltr turns a survivor's phone photos into a 3D model of the damaged room, finds and prices the damage, and fills in the aid application for them. Every risky step runs inside a throwaway sandbox on Vultr, and nothing is submitted until the survivor approves it.

Built for the Vultr Agent Arena Hackathon 2026, track **Blast Radius Zero: Safe Agent Execution on Vultr**.

## How it works

- **VM 1, control plane (Vultr Cloud Compute):** plans each case with a model on Vultr Serverless Inference, keeps the case record, and holds every API key.
- **VM 2, sandbox host (Vultr VX1):** runs each task in a sandbox that is destroyed afterwards.
  - Photo sandbox (Microsandbox microVM): depth model, 3D reconstruction, and agent-written measuring code with a visible retry loop.
  - Browser sandbox (Playwright in a gVisor container): fills in the aid form, with a vision check on every screenshot and an approval step before submit.
- **Containment:** a fake aid website tries prompt injection, a forced download and data theft. The sandbox holds, and the survivor is warned.

Full diagrams: [design/blueprint.html](design/blueprint.html). Visual concept: [design/3d-mockup.html](design/3d-mockup.html).

## Status

Work in progress during the hackathon (September 26–27, 2026). Everything in this repository was written during the event.

## Secrets

Copy `.env.example` to `.env` and fill in your keys. `.env` is ignored by git. Keys are never copied into a sandbox.
