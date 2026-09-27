"""Allow SSH to VM 1 from the network you are on now (after switching Wi-Fi, hotspot, home...).

    python infra/allow_my_ip.py            # add this machine's public IPv4 to the shltr-vm1 SSH rule
    python infra/allow_my_ip.py --prune    # also remove SSH rules for every other IP

VM 2 is never opened: it is reached through VM 1 over the private network.
The Vultr API key itself must also accept your IP (Account > API > Access Control).
"""
import argparse
import json
import urllib.request

from common import REPO_ROOT, http_json, load_env, require

API = "https://api.vultr.com/v2"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prune", action="store_true", help="remove SSH rules for other IPs")
    args = parser.parse_args()
    token = require(load_env(), "VULTR_API_KEY")
    state = json.loads((REPO_ROOT / "infra" / "state.json").read_text())
    fid = state["firewalls"]["shltr-vm1"]
    ip = urllib.request.urlopen("https://api.ipify.org", timeout=15).read().decode().strip()

    rules = http_json("GET", f"{API}/firewalls/{fid}/rules", token)["firewall_rules"]
    ssh = [r for r in rules if r["port"] == "22"]
    if any(r["subnet"] == ip for r in ssh):
        print(f"SSH already allowed from {ip}")
    else:
        http_json("POST", f"{API}/firewalls/{fid}/rules", token, {
            "ip_type": "v4", "protocol": "tcp", "subnet": ip, "subnet_size": 32, "port": "22", "notes": "ssh from admin"})
        print(f"SSH now allowed from {ip}")
    if args.prune:
        for r in ssh:
            if r["subnet"] != ip:
                http_json("DELETE", f"{API}/firewalls/{fid}/rules/{r['id']}", token)
                print(f"removed old SSH rule for {r['subnet']}")


if __name__ == "__main__":
    main()
