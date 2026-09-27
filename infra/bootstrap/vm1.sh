#!/usr/bin/env bash
# VM 1, the control plane. Run from the repo root:  ssh -F infra/keys/ssh_config vm1 'bash -s' < infra/bootstrap/vm1.sh
# Safe to re-run.
set -euo pipefail

if [ "$(hostname)" != "shltr-vm1" ]; then
  echo "Refusing to run: this is $(hostname), not shltr-vm1." >&2
  exit 1
fi

# Host firewall: SSH (Vultr's firewall group already limits it to the admin IP) plus web.
# Ubuntu's default ufw only allowed 22, so the app would be unreachable without this.
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp comment "web" >/dev/null
ufw allow 443/tcp comment "web" >/dev/null
ufw --force enable >/dev/null
echo "firewall: 22, 80, 443 open on VM 1"

# Tools the control plane will need (Part 6): Python venv support and Caddy for HTTPS come later.
command -v python3 >/dev/null && echo "python: $(python3 --version)"
