# Vultr notes

Facts we've confirmed about Vultr, so neither agent has to look them up again. Add to it when you learn something new.

## Serverless Inference pricing

Billed per token only: input and output, **USD per 1 million tokens**. No monthly fee is mentioned in the console note (Sept 27, 2026). Base URL: `https://api.vultrinference.com/v1` (OpenAI-compatible).

| Model id | Input $/1M | Output $/1M | Inputs | Tools | Use in Shltr |
|---|---|---|---|---|---|
| `glm-5.3` | 0.75 | 3.00 | text, image | yes | **Main model**: planner, damage reading, code writing |
| `glm-5.3-flash` | 0.10 | 0.35 | text, image, video | yes | Candidate for cheap, frequent calls: screenshot checks, video walkthroughs |
| `qwen3.8-27b` | 0.15 | 1.00 | text, image, video | yes | Fallback main model |
| `qwen3.8-flash-next` | 0.10 | 0.20 | text, image, video | yes | Cheap fallback |
| `deepseek-v4.1-flash` | 0.15 | 0.60 | text, image | yes | |
| `deepseek-v4-flash-0731` | 0.10 | 0.25 | text, image | yes | |
| `glm-5.2` | 0.75 | 3.00 | text, image | yes | |
| `glm-5` | 0.40 | 1.75 | | | Not in the live `/v1/models` list when checked |
| `minimax-m3` | 0.20 | 0.90 | text, image, video | yes | |
| `mimo-v2.6-pro-rl` | 0.40 | 0.80 | text, image, audio, video | yes | |
| `mimo-v2.6-flash-rl` | 0.10 | 0.25 | text, image, audio, video | yes | |
| `muse-glimmer-30b` | 0.25 | 1.00 | text, image, video | yes | |
| `nemotron-3-nano-omni-30b-a3b-reasoning` | 0.10 | 0.25 | text, image, audio, video | yes | |
| `nemotron-3.5-content-safety` | 0.05 | 0.15 | text, image | no | Optional: screen uploads before dispatch |
| `laguna-s-2.1` | 0.09 | 0.18 | text, image | yes | |
| `mica-v0.1-4b` | 0.05 | 0.00 | text | no | Outputs a decision label |
| `bge-reranker-v2-m3` | 0.05 | 0.00 | text | no | Reranker |
| `qwen3-embedding-4b` | 0.05 | 0.00 | text | no | Embeddings |
| `vultron-retriever-core-qwen3.5-4.5b` | 0.10 | 0.00 | text | no | Reranker |
| `vultron-retriever-flash-qwen3.5-0.8b` | 0.05 | 0.00 | text | no | Reranker |
| `z-image-turbo` | 0.00 | 0.00 | text | no | Text-to-image generator |

The "Inputs" and "Tools" columns come from `GET https://api.vultrinference.com/v1/models` (public, no key needed). Model names in the price list and ids in the API differ slightly; always use the API id.

### What a case costs

A rough full case on `glm-5.3`: about 40,000 input tokens (photos and screenshots are the bulk) and 6,000 output tokens, so about $0.03 + $0.018 = **about $0.05 per case**. A day of testing with 100 cases is about $5. Moving screenshot checks to `glm-5.3-flash` cuts that further.

## Console steps

- **Inference key:** Products → Serverless → Inference (or Quick Deploy → Serverless Inference) → Add Serverless Inference → Label `shltr` → acknowledge the model and charges note → Add. Copy the key from the new entry into `.env` as `VULTR_INFERENCE_KEY`.
- **API key access control:** Account → API (under OTHER) → Access Control → enter the IP → Add. The API returns `401 Unauthorized IP address: <ip>` from any IP not on the list, and `infra/common.py` prints this fix. Add every network you work from (venue, home, hotspot).

## Billing gotchas

- Vultr **keeps billing stopped servers**. Delete servers you don't need.
- The account balance is shown as a negative number when you have credit.

## Sandboxing guide

Vultr's own guide (https://docs.vultr.com/how-to-set-up-agent-sandboxing-on-vultr-cloud-compute) uses **Microsandbox** on a **VX1** instance with Ubuntu 24.04:

```
curl -fsSL https://install.microsandbox.dev | sh
sudo usermod -aG kvm $USER && newgrp kvm
msb doctor
msb create --name sandbox01 --cpus 1 --memory 256M debian
msb exec sandbox01 -- bash -c "command"
msb logs sandbox01 --tail 5
msb copy sandbox01:/path/file ./local
msb stop sandbox01 && msb remove sandbox01
```

Also available as a Python SDK (`pip install microsandbox`) and an MCP server (`npx -y microsandbox-mcp`). Per the guide, each sandbox can reach the public internet but not its siblings, so network access must be turned off for our photo sandbox.
