"""Part 3: create Shltr's Vultr servers. Dry run by default; pass --yes to create.

What it builds (all named shltr-*, all in one region):
  ssh key      shltr            public half of infra/keys/shltr_ed25519 (generated if missing)
  VPC          shltr-vpc        private network 10.40.0.0/24 between the two servers
  firewall     shltr-vm1        22 from your IP, 80 and 443 from anywhere
  firewall     shltr-vm2        no inbound ports at all; reached only from VM 1 over the VPC
  server       shltr-vm1        control plane, Ubuntu 24.04
  server       shltr-vm2        sandbox host, VX1 (exposes KVM for microVMs), Ubuntu 24.04

Safe to re-run: anything that already exists is reused, never duplicated.
IDs and IPs are saved to infra/state.json (git-ignored) for the next steps and teardown.

    python infra/provision.py                 # show the plan and the cost, create nothing
    python infra/provision.py --yes           # create it
"""
import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from common import REPO_ROOT, http_json, load_env, require

API = "https://api.vultr.com/v2"
KEY_PATH = REPO_ROOT / "infra" / "keys" / "shltr_ed25519"
STATE_PATH = REPO_ROOT / "infra" / "state.json"
UBUNTU_2404 = 2284
VPC_SUBNET = "10.40.0.0"

SERVERS = {
    "shltr-vm1": {"plan": "vc2-2c-4gb", "role": "control plane", "firewall": "shltr-vm1"},
    "shltr-vm2": {"plan": "vx1-g-4c-16g-240s", "role": "sandbox host", "firewall": "shltr-vm2"},
}


def my_public_ip() -> str:
    with urllib.request.urlopen("https://api.ipify.org", timeout=15) as resp:
        return resp.read().decode().strip()


def firewall_rules(name: str, admin_ip: str) -> list[dict]:
    """VM 1 is the only public door. VM 2 gets no inbound rules at all: it is reached
    only from VM 1 over the VPC (SSH uses VM 1 as a jump host, see infra/keys/ssh_config)."""
    if name != "shltr-vm1":
        return []
    ssh = {"ip_type": "v4", "protocol": "tcp", "subnet": admin_ip, "subnet_size": 32, "port": "22", "notes": "ssh from admin"}
    web = [{"ip_type": "v4", "protocol": "tcp", "subnet": "0.0.0.0", "subnet_size": 0, "port": p, "notes": f"web {p}"} for p in ("80", "443")]
    return [ssh, *web]


def write_ssh_config(servers: dict) -> Path:
    """`ssh -F infra/keys/ssh_config vm1` or `... vm2` (vm2 hops through vm1 over the VPC)."""
    key = KEY_PATH.as_posix()
    known = (KEY_PATH.parent / "known_hosts").as_posix()
    common = f"  User root\n  IdentityFile {key}\n  UserKnownHostsFile {known}\n  StrictHostKeyChecking accept-new\n  ConnectTimeout 20\n"
    text = (f"Host vm1\n  HostName {servers['shltr-vm1']['main_ip']}\n{common}\n"
            f"Host vm2\n  HostName {servers['shltr-vm2']['vpc_ip']}\n  ProxyJump vm1\n{common}")
    path = KEY_PATH.parent / "ssh_config"
    path.write_text(text)
    return path


def ensure_ssh_key(token: str, create: bool) -> str | None:
    if not KEY_PATH.exists():
        if not create:
            print(f"  would generate  {KEY_PATH.relative_to(REPO_ROOT)} (ed25519)")
            return None
        KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-f", str(KEY_PATH), "-N", "", "-C", "shltr"], check=True, capture_output=True)
        print(f"  generated       {KEY_PATH.relative_to(REPO_ROOT)}")
    public = KEY_PATH.with_suffix(".pub").read_text().strip()
    for k in http_json("GET", f"{API}/ssh-keys?per_page=500", token).get("ssh_keys", []):
        if k["name"] == "shltr":
            print(f"  reuse ssh key   shltr ({k['id']})")
            return k["id"]
    if not create:
        print("  would upload    ssh key 'shltr' (public half only)")
        return None
    k = http_json("POST", f"{API}/ssh-keys", token, {"name": "shltr", "ssh_key": public})["ssh_key"]
    print(f"  uploaded        ssh key shltr ({k['id']})")
    return k["id"]


def ensure_vpc(token: str, region: str, create: bool) -> str | None:
    for v in http_json("GET", f"{API}/vpcs?per_page=500", token).get("vpcs", []):
        if v.get("description") == "shltr-vpc" and v.get("region") == region:
            print(f"  reuse VPC       shltr-vpc {v['v4_subnet']}/{v['v4_subnet_mask']} ({v['id']})")
            return v["id"]
    if not create:
        print(f"  would create    VPC shltr-vpc {VPC_SUBNET}/24 in {region}")
        return None
    v = http_json("POST", f"{API}/vpcs", token, {"region": region, "description": "shltr-vpc", "v4_subnet": VPC_SUBNET, "v4_subnet_mask": 24})["vpc"]
    print(f"  created         VPC shltr-vpc {VPC_SUBNET}/24 ({v['id']})")
    return v["id"]


def ensure_firewall(token: str, name: str, admin_ip: str, create: bool) -> str | None:
    rules = firewall_rules(name, admin_ip)
    summary = ", ".join(f"{r['port']} from {r['subnet']}/{r['subnet_size']}" for r in rules) or "no inbound ports (private network only)"
    for g in http_json("GET", f"{API}/firewalls?per_page=500", token).get("firewall_groups", []):
        if g.get("description") == name:
            print(f"  reuse firewall  {name} ({g['id']})")
            return g["id"]
    if not create:
        print(f"  would create    firewall {name}: {summary}")
        return None
    g = http_json("POST", f"{API}/firewalls", token, {"description": name})["firewall_group"]
    for rule in rules:
        http_json("POST", f"{API}/firewalls/{g['id']}/rules", token, rule)
    print(f"  created         firewall {name}: {summary}")
    return g["id"]


def ensure_server(token: str, label: str, spec: dict, region: str, ssh_id, vpc_id, fw_id, create: bool) -> str | None:
    for s in http_json("GET", f"{API}/instances?per_page=500", token).get("instances", []):
        if s.get("label") == label:
            print(f"  reuse server    {label} {s['plan']} ({s['id']})")
            return s["id"]
    if not create:
        print(f"  would create    server {label} ({spec['role']}): {spec['plan']}, Ubuntu 24.04, in the VPC")
        return None
    body = {
        "region": region, "plan": spec["plan"], "os_id": UBUNTU_2404,
        "label": label, "hostname": label, "tags": ["shltr"],
        "sshkey_id": [ssh_id], "firewall_group_id": fw_id, "attach_vpc": [vpc_id],
        "backups": "disabled", "enable_ipv6": False,
    }
    s = http_json("POST", f"{API}/instances", token, body)["instance"]
    print(f"  created         server {label} {spec['plan']} ({s['id']})")
    return s["id"]


def wait_until_ready(token: str, ids: dict) -> dict:
    """Poll until each server is running and has its public and private IPs."""
    info = {}
    deadline = time.time() + 900
    while time.time() < deadline:
        pending = []
        for label, sid in ids.items():
            s = http_json("GET", f"{API}/instances/{sid}", token)["instance"]
            vpcs = http_json("GET", f"{API}/instances/{sid}/vpcs", token).get("vpcs", [])
            vpc_ip = vpcs[0].get("ip_address") if vpcs else None
            ready = s["status"] == "active" and s["power_status"] == "running" and s["main_ip"] != "0.0.0.0" and vpc_ip
            info[label] = {"id": sid, "plan": s["plan"], "main_ip": s["main_ip"], "vpc_ip": vpc_ip, "status": f"{s['status']}/{s['power_status']}/{s['server_status']}"}
            if not ready:
                pending.append(f"{label}: {info[label]['status']}")
        if not pending:
            return info
        print("  waiting         " + "; ".join(pending))
        time.sleep(20)
    raise SystemExit("Servers did not become ready within 15 minutes. Check the Vultr dashboard.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="actually create the resources")
    parser.add_argument("--region", default="atl")
    parser.add_argument("--admin-ip", help="IP allowed to SSH in (default: this machine's public IP)")
    args = parser.parse_args()

    token = require(load_env(), "VULTR_API_KEY")
    admin_ip = args.admin_ip or my_public_ip()
    create = args.yes

    plans = {p["id"]: p for p in http_json("GET", f"{API}/plans?per_page=500", token)["plans"]}
    hourly = 0.0
    print(f"{'Creating' if create else 'Plan (dry run, nothing is created)'} in region {args.region}; SSH allowed from {admin_ip}\n")
    for label, spec in SERVERS.items():
        p = plans[spec["plan"]]
        if args.region not in p["locations"]:
            raise SystemExit(f"Plan {spec['plan']} is not offered in {args.region}.")
        cost = p.get("hourly_cost") or p["monthly_cost"] / 730
        hourly += cost
        print(f"  {label}  {spec['role']:<14} {spec['plan']:<20} {p['vcpu_count']} vCPU {p['ram'] / 1024:.0f} GB  ${cost:.3f}/hour")
    print(f"  total                                          ${hourly:.3f}/hour, about ${hourly * 24:.2f}/day\n")

    ssh_id = ensure_ssh_key(token, create)
    vpc_id = ensure_vpc(token, args.region, create)
    fw_ids = {name: ensure_firewall(token, name, admin_ip, create) for name in ("shltr-vm1", "shltr-vm2")}
    server_ids = {
        label: ensure_server(token, label, spec, args.region, ssh_id, vpc_id, fw_ids[spec["firewall"]], create)
        for label, spec in SERVERS.items()
    }

    if not create:
        print("\nNothing was created. Run again with --yes to create these resources.")
        return

    print("\nWaiting for both servers to boot (usually 2 to 5 minutes)...")
    servers = wait_until_ready(token, server_ids)
    state = {"region": args.region, "admin_ip": admin_ip, "ssh_key_id": ssh_id, "vpc_id": vpc_id,
             "firewalls": fw_ids, "servers": servers, "ssh_key_path": str(KEY_PATH.relative_to(REPO_ROOT))}
    STATE_PATH.write_text(json.dumps(state, indent=2))
    config = write_ssh_config(servers)
    print(f"\nReady. Saved {STATE_PATH.relative_to(REPO_ROOT)} and {config.relative_to(REPO_ROOT)}")
    for label, s in servers.items():
        print(f"  {label}  public {s['main_ip']:<16} private {s['vpc_ip']:<12} {s['plan']}")
    print("\nNext: run infra/bootstrap/vm1.sh and vm2.sh on the servers (see infra/README.md), then python infra/smoke_test.py")
    print("SSH: ssh -F infra/keys/ssh_config vm1   (vm2 goes through vm1: ssh -F infra/keys/ssh_config vm2)")


if __name__ == "__main__":
    main()
