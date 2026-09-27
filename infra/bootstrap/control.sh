#!/usr/bin/env bash
# Deploy the control plane on VM 1. Run from the repo root (see backend/control/README.md):
#   tar -C backend -cf - control | ssh -F infra/keys/ssh_config vm1 'mkdir -p /opt/shltr && tar -C /opt/shltr -xf -'
#   ssh -F infra/keys/ssh_config vm1 'bash -s' < infra/bootstrap/control.sh
# Needs /etc/shltr/runner.env (from VM 2) and /etc/shltr/control.env (VULTR_INFERENCE_KEY) on VM 1.
# Safe to re-run.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

for f in /etc/shltr/runner.env /etc/shltr/control.env; do
  [ -f "$f" ] || { echo "missing $f" >&2; exit 1; }
  chmod 600 "$f"
done

apt-get install -y -qq python3-venv caddy >/dev/null
python3 -m venv /opt/shltr/venv
/opt/shltr/venv/bin/pip install -q fastapi==0.118.0 "uvicorn[standard]==0.37.0" python-multipart==0.0.20 httpx==0.28.1
mkdir -p /srv/shltr/cases

cat > /etc/systemd/system/shltr-control.service <<'UNIT'
[Unit]
Description=Shltr control plane
After=network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=/etc/shltr/runner.env
EnvironmentFile=/etc/shltr/control.env
Environment=FRONTEND_DIST=/opt/shltr/frontend/dist
WorkingDirectory=/opt/shltr/control
ExecStart=/opt/shltr/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000 --no-access-log
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT

# Public HTTPS with an automatic certificate. sslip.io turns the IP into a hostname.
PUBLIC_IP=$(curl -s https://api.ipify.org)
HOST="${PUBLIC_IP//./-}.sslip.io"
cat > /etc/caddy/Caddyfile <<CADDY
$HOST {
    encode gzip
    request_body {
        max_size 110MB
    }
    reverse_proxy 127.0.0.1:8000
}
CADDY

systemctl daemon-reload
systemctl enable -q shltr-control caddy
systemctl restart shltr-control caddy
sleep 3
systemctl is-active shltr-control >/dev/null && echo "control plane: active on 127.0.0.1:8000"
systemctl is-active caddy >/dev/null && echo "public URL: https://$HOST  (upload page: https://$HOST/start)"
