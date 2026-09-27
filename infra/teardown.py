"""Part 3: delete everything provision.py created. Dry run by default; pass --yes to delete.

Vultr keeps billing stopped servers, so we delete instead of stopping.
Only resources named shltr-* (and the ssh key 'shltr') are touched.

    python infra/teardown.py          # list what would be deleted
    python infra/teardown.py --yes    # delete it
"""
import argparse
import time

from common import REPO_ROOT, http_json, load_env, require

API = "https://api.vultr.com/v2"
STATE_PATH = REPO_ROOT / "infra" / "state.json"


def find(token: str) -> dict:
    get = lambda path, key: http_json("GET", f"{API}/{path}?per_page=500", token).get(key, [])  # noqa: E731
    return {
        "servers": [(s["id"], s["label"]) for s in get("instances", "instances") if s.get("label", "").startswith("shltr-")],
        "firewalls": [(g["id"], g["description"]) for g in get("firewalls", "firewall_groups") if g.get("description", "").startswith("shltr-")],
        "vpcs": [(v["id"], v["description"]) for v in get("vpcs", "vpcs") if v.get("description", "").startswith("shltr-")],
        "ssh_keys": [(k["id"], k["name"]) for k in get("ssh-keys", "ssh_keys") if k.get("name") == "shltr"],
    }


def delete(token: str, path: str, attempts: int = 12) -> None:
    """Firewalls and VPCs can't be deleted until their servers are fully gone, so retry."""
    for i in range(attempts):
        try:
            http_json("DELETE", f"{API}/{path}", token)
            return
        except SystemExit as err:
            if i == attempts - 1:
                raise
            print(f"    not yet deletable, retrying in 15 s ({str(err)[:90]})")
            time.sleep(15)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="actually delete")
    args = parser.parse_args()
    token = require(load_env(), "VULTR_API_KEY")

    found = find(token)
    total = sum(len(v) for v in found.values())
    print(f"{'Deleting' if args.yes else 'Would delete (dry run)'}: {total} resources")
    for kind, items in found.items():
        for rid, name in items:
            print(f"  {kind:<10} {name:<12} {rid}")
    if not total:
        print("Nothing to delete.")
        return
    if not args.yes:
        print("\nRun again with --yes to delete these.")
        return

    # Order matters: servers first, then what they were attached to.
    for rid, name in found["servers"]:
        delete(token, f"instances/{rid}")
        print(f"  deleted server {name}")
    for rid, name in found["firewalls"]:
        delete(token, f"firewalls/{rid}")
        print(f"  deleted firewall {name}")
    for rid, name in found["vpcs"]:
        delete(token, f"vpcs/{rid}")
        print(f"  deleted VPC {name}")
    for rid, name in found["ssh_keys"]:
        delete(token, f"ssh-keys/{rid}")
        print(f"  deleted ssh key {name}")
    # Forget the old servers locally too. A rebuilt server can get the same IP with a new
    # host key, and a stale known_hosts entry would then block SSH with a spoofing warning.
    # The SSH key pair itself is kept so the next provision.py run can reuse it.
    keys_dir = REPO_ROOT / "infra" / "keys"
    for path in (STATE_PATH, keys_dir / "known_hosts", keys_dir / "known_hosts.old", keys_dir / "ssh_config"):
        if path.exists():
            path.unlink()
    print("\nDone. Billing stops for deleted servers. Check the dashboard to confirm nothing is left.")


if __name__ == "__main__":
    main()
