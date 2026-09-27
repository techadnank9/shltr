#!/usr/bin/env bash
# Build the front end and publish it to VM 1.
#
#   ./infra/deploy_frontend.sh            # build + rsync dist to VM 1
#   ./infra/deploy_frontend.sh --check    # just check what is live
#
# Needs the account's `shltr` SSH private key. Set SHLTR_KEY to its path if it
# is not one ssh already offers, e.g.
#   SHLTR_KEY=~/.ssh/shltr ./infra/deploy_frontend.sh
set -euo pipefail

VM1=${VM1:-45.76.251.95}
URL=${URL:-https://45-76-251-95.sslip.io}
DEST=${DEST:-/opt/shltr/frontend/dist/}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SSH_OPTS=(-o ConnectTimeout=10)
[ -n "${SHLTR_KEY:-}" ] && SSH_OPTS+=(-i "$SHLTR_KEY")

check() {
  echo "live at $URL"
  for p in / /scan-story/ /scan-demo/ /scan-demo/scan.glb /capture /scan; do
    printf '  %-22s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$URL$p")"
  done
}

if [ "${1:-}" = --check ]; then check; exit 0; fi

echo "==> building"
cd "$ROOT/frontend" && npm run build

echo "==> publishing to $VM1:$DEST"
rsync -av --delete -e "ssh ${SSH_OPTS[*]}" "$ROOT/frontend/dist/" "root@$VM1:$DEST"

echo "==> done"
check
