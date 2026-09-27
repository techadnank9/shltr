#!/usr/bin/env bash
# Deploy the runner on VM 2. Run from the repo root:
#   tar -C backend -cf - runner | ssh -F infra/keys/ssh_config vm2 'mkdir -p /opt/shltr && tar -C /opt/shltr -xf -'
#   ssh -F infra/keys/ssh_config vm2 'bash -s' < infra/bootstrap/runner.sh
# Safe to re-run. The token is created on the server and never leaves it except to VM 1.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

VPC_IP=$(ip -4 -o addr show | awk '/ 10\.40\./ {split($4, a, "/"); print a[1]; exit}')
[ -n "$VPC_IP" ] || { echo "no VPC address found" >&2; exit 1; }

apt-get install -y -qq python3-venv >/dev/null
python3 -m venv /opt/shltr/venv
/opt/shltr/venv/bin/pip install -q fastapi==0.118.0 uvicorn==0.37.0 python-multipart==0.0.20

mkdir -p /etc/shltr /srv/shltr/jobs
if [ ! -f /etc/shltr/runner.env ]; then
  umask 077
  printf 'RUNNER_TOKEN=%s\nRUNNER_BIND=%s\nRUNNER_PORT=8700\n' "$(openssl rand -hex 32)" "$VPC_IP" > /etc/shltr/runner.env
fi
chmod 600 /etc/shltr/runner.env

cat > /etc/systemd/system/shltr-runner.service <<'UNIT'
[Unit]
Description=Shltr runner (throwaway microVMs for untrusted work)
After=network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=/etc/shltr/runner.env
WorkingDirectory=/opt/shltr/runner
ExecStart=/bin/sh -c 'exec /opt/shltr/venv/bin/uvicorn runner:app --host "$RUNNER_BIND" --port "$RUNNER_PORT" --no-access-log'
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable -q shltr-runner
systemctl restart shltr-runner
sleep 2
systemctl is-active shltr-runner >/dev/null && echo "runner: active on $VPC_IP:8700 (private network only)"
