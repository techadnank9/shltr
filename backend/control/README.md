# Control plane (VM 1)

The brain. It is the only public part of Shltr: it serves the 3D front end, takes the survivor's upload, plans the case, sends every risky step to the runner on VM 2, uses `glm-5.3` on Vultr Serverless Inference to read the damage and to write the measuring code, and streams every step to the browser.

**Live:** https://45-76-251-95.sslip.io · upload page `/start` · a case opens at `/?source=ws&case=<id>`

```
browser ──HTTPS (Caddy)──► control plane 127.0.0.1:8000 (VM 1)
                             │ 1 upload stored, never opened
                             │ 2 runner /jobs/reconstruct ──► microVM: photo/video → room.glb + sanitized photo.jpg
                             │ 3 glm-5.3 vision on photo.jpg → damage items (category, box, point)
                             │ 4 glm-5.3 writes Python ──► runner /jobs/code ──► microVM runs it
                             │      error? the output goes back to glm-5.3, up to 3 attempts (code.attempt events)
                             │ 5 damage.found (3D position, price) + estimate.total
                             ▼
                          WebSocket /ws/cases/{id}  (docs/EVENTS.md v1, replayed from seq 1 on connect)
```

## Files

| File | What it does |
|---|---|
| `app.py` | FastAPI app: upload, WebSocket, event log per case (`/srv/shltr/cases/<id>/events.jsonl`), file proxy to the runner, the case pipeline |
| `agent.py` | Model calls: the plan, price table, vision prompt, code-writing prompt and retry prompt, result checks |
| `static/start.html` | Upload page |
| `test_case.py` | End-to-end test through the public URL (checks E1–E7) |
| `../runner/geom.py` | Helper the model's code imports inside the sandbox: `point_at` (ray onto the 3D mesh), `area_in_box` (m² of surface), `height_of` |

## API

| Call | Purpose |
|---|---|
| `POST /api/cases` | Multipart `file` (photo or video, up to 100 MB) and `title`. Returns `{case_id, url}` |
| `WS /ws/cases/{id}` | Live events; sends `approve` / `decline` back |
| `GET /api/cases/{id}/events` | All events as JSON |
| `GET /api/cases/{id}/photo` | The sanitized photo; waits up to 90 s for the sandbox to produce it |
| `GET /api/cases/{id}/files/{path}` | `room.glb`, `depth.png`, `photo.jpg`, `stats.json`, `frames/frame_NN.jpg`, proxied from the runner |
| `GET /api/health` | Control plane and runner status |

## Security choices

- The upload is written to disk and forwarded to the runner **without being opened**. Decoding happens only in the no-network microVM, which also produces the re-encoded `photo.jpg` that the model and the browser see.
- The browser never talks to VM 2. Every asset is proxied through VM 1 with an allowlisted path pattern and `X-Content-Type-Options: nosniff`.
- Model-written code only ever runs in a fresh microVM (no network, 2 CPUs, 1 GB, 60 s) with the room and `geom.py` copied in read-only. Its output is validated (`agent.check_result`) before anything reaches the survivor.
- Secrets: `/etc/shltr/control.env` (inference key) and `/etc/shltr/runner.env` (runner token), mode 600, VM 1 only.
- The service listens on `127.0.0.1`; only Caddy (80/443) is public.

## Deploy

From the repo root, with the runner already deployed on VM 2:

```
ssh -F infra/keys/ssh_config vm2 'cat /etc/shltr/runner.env' | ssh -F infra/keys/ssh_config vm1 'mkdir -p /etc/shltr && umask 077 && cat > /etc/shltr/runner.env'
grep -E "^(VULTR_INFERENCE_KEY|VULTR_MODEL)=" .env | ssh -F infra/keys/ssh_config vm1 'umask 077 && cat > /etc/shltr/control.env'
(cd frontend && npm run build) && tar -C frontend -cf - dist | ssh -F infra/keys/ssh_config vm1 'mkdir -p /opt/shltr/frontend && rm -rf /opt/shltr/frontend/dist && tar -C /opt/shltr/frontend -xf -'
tar -C backend -cf - control | ssh -F infra/keys/ssh_config vm1 'mkdir -p /opt/shltr && tar -C /opt/shltr -xf -'
ssh -F infra/keys/ssh_config vm1 'bash -s' < infra/bootstrap/control.sh
python backend/control/test_case.py test-photos/flooded-room.png
```

## Not in this part

Checking suspicious links and filling in the aid form (the browser sandbox, approval before submit) come in Part 7. The WebSocket already accepts `approve` / `decline` and answers with `approval.result`.
