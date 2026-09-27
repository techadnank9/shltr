#!/usr/bin/env bash
# Demo sites server on VM 1: serves /opt/shltr/sites (the mock aid portal and the fake scam site)
# on VM 1's PRIVATE address only, port 8080, so only browser microVMs on VM 2 can reach it.
# Copy the pages first, from the repo root:
#   tar -C sites -cf - . | ssh -F infra/keys/ssh_config vm1 'mkdir -p /opt/shltr/sites && tar -C /opt/shltr/sites -xf -'
#   ssh -F infra/keys/ssh_config vm1 'bash -s' < infra/bootstrap/sites.sh
set -euo pipefail

if [ "$(hostname)" != "shltr-vm1" ]; then
  echo "Refusing to run: this is $(hostname), not shltr-vm1." >&2
  exit 1
fi
VPC_IF=$(ip -4 -o addr show | awk '/ 10\.40\./ {print $2; exit}')
VPC_IP=$(ip -4 -o addr show | awk '/ 10\.40\./ {split($4, a, "/"); print a[1]; exit}')
[ -n "$VPC_IP" ] || { echo "no VPC address found" >&2; exit 1; }
mkdir -p /opt/shltr/sites

# Only the private interface may reach port 8080.
ufw allow in on "$VPC_IF" to any port 8080 proto tcp comment "demo sites, VPC only" >/dev/null

cat > /etc/systemd/system/shltr-sites.service <<UNIT
[Unit]
Description=Shltr demo sites (private network only)
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 -m http.server 8080 --bind $VPC_IP --directory /opt/shltr/sites
DynamicUser=yes
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable -q shltr-sites
systemctl restart shltr-sites
sleep 1
systemctl is-active shltr-sites >/dev/null && echo "demo sites: http://$VPC_IP:8080 (private network only)"
