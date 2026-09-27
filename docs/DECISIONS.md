# Decisions

Choices already made, with the reason. To change one, ask your human first, then update this file in the same PR as the change.

| # | Decision | Why |
|---|---|---|
| D1 | Track: **Blast Radius Zero** (safe agent execution on Vultr) | Best fit for a sandboxed agent; all tracks are judged in one pool |
| D2 | Product: **disaster-aid agent** for storm and flood survivors (photos to 3D evidence to aid claim) | Social cause, strong 3D visuals, uses both of the brief's patterns |
| D3 | Do **both patterns**: A (sandboxed code with a visible retry loop) and B (sandboxed browser with a vision check per screenshot and approval before submit) | The brief rewards both; judges weight technicality at 40% |
| D4 | Containment moment: a **fake aid website** that tries prompt injection, a forced download and data exfiltration | Scam sites really target survivors after disasters. Replaced the earlier "rm -rf hidden in a photo" idea, which felt staged |
| D5 | Backup containment: agent-written code that runs away (huge photo, loop) gets killed by the memory and time limits, then retried | Happens naturally and shows the retry loop |
| D6 | Photo sandbox uses **Microsandbox** microVMs on a **Vultr VX1** | It is the tool in Vultr's own sandboxing guide; microVMs have their own kernel; VX1 exposes KVM |
| D7 | Browser sandbox uses **Playwright in Docker with gVisor** | The brief recommends Playwright in Docker |
| D8 | Model: **glm-5.3**, fallback **qwen3.8-27b** | Both accept images and support tool calling. Kimi-K2.6 (suggested in Vultr's slides) is not in the live model list as of Sept 27 |
| D9 | Two VMs: VM 1 control plane (public), VM 2 sandbox host (no public ports), joined by a Vultr VPC | Matches Vultr's reference architecture: two instances, one boundary |
| D10 | Region: **Atlanta** | The live model list shows the inference models in Atlanta |
| D11 | The browser agent only targets **our own mock aid portal and fake scam page** | Never submit to a real government site or visit real criminal sites |
| D12 | Room geometry comes from the **depth model**; Blender is for polished scene assets only | The 3D room must be real, not modeled by hand |
| D13 | Budget: under **$30** of the $200 credit; delete unused servers | Vultr bills stopped servers |
| D14 | Repo: **techadnank9/shltr** is the main repository | Team decision |
| D15 | Every change goes through a **clean PR** on a `<owner>/<topic>` branch; no direct pushes to `main` | Two agents work on the repo at once |

## Open questions

- Product name spelling: the README and designs say **Sheltr**, the repo is **shltr**. Pick one and update README, CLAUDE.md and the design pages in one PR.
- Is NetBird (bonus challenge) in scope? Default: no, unless time allows.
