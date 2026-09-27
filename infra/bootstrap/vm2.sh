#!/usr/bin/env bash
# VM 2, the sandbox host. Run from the repo root:  ssh -F infra/keys/ssh_config vm2 'bash -s' < infra/bootstrap/vm2.sh
# Safe to re-run.
set -euo pipefail

# 1. Host firewall: accept traffic only from the private network (VPC).
#    Vultr's firewall group did not filter this VX1 server, and Ubuntu's default ufw
#    allowed SSH from anywhere, so the host itself must enforce "no public ports".
VPC_IF=$(ip -4 -o addr show | awk '/ 10\.40\./ {print $2; exit}')
if [ -z "$VPC_IF" ]; then echo "No VPC interface (10.40.x.x) found; refusing to lock the firewall." >&2; exit 1; fi
ufw allow in on "$VPC_IF" comment "VPC from VM 1" >/dev/null   # add this first so our SSH session survives
ufw --force delete allow 22/tcp >/dev/null 2>&1 || true
ufw --force delete allow OpenSSH >/dev/null 2>&1 || true
ufw default deny incoming >/dev/null
ufw --force enable >/dev/null
echo "firewall: only $VPC_IF (VPC) accepts inbound traffic"

# 2. Microsandbox (per Vultr's sandboxing guide): microVMs with their own kernel via KVM.
export PATH="/root/.local/bin:$PATH"
if ! command -v msb >/dev/null; then
  curl -fsSL https://install.microsandbox.dev | sh >/root/msb-install.log 2>&1
fi
echo "microsandbox: $(msb --version)"
msb doctor 2>&1 | grep -E "KVM|CPU virt|ready" || true
