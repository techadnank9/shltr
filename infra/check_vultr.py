"""Part 1: read-only check of the Vultr account. Creates nothing and costs nothing.

Prints the credit balance, confirms the region exists, and lists the plans
available there with prices, so we can pick VM 1 and VM 2 before spending.

    python infra/check_vultr.py            # Atlanta
    python infra/check_vultr.py --region ewr
"""
import argparse

from common import http_json, load_env, require

API = "https://api.vultr.com/v2"
HOURS_PER_MONTH = 730


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="atl", help="Vultr region id (default: atl, Atlanta)")
    parser.add_argument("--max-monthly", type=float, default=200.0, help="hide plans above this monthly price")
    args = parser.parse_args()

    token = require(load_env(), "VULTR_API_KEY")

    account = http_json("GET", f"{API}/account", token).get("account", {})
    # Vultr reports a credit as a negative balance.
    print("Account")
    print(f"  name             {account.get('name', '?')}")
    print(f"  balance          {account.get('balance')}  (negative means credit available)")
    print(f"  pending charges  {account.get('pending_charges')}")
    print()

    regions = http_json("GET", f"{API}/regions?per_page=500", token).get("regions", [])
    region = next((r for r in regions if r.get("id") == args.region), None)
    if not region:
        ids = ", ".join(sorted(r["id"] for r in regions))
        raise SystemExit(f"Region '{args.region}' not found. Available: {ids}")
    print(f"Region {region['id']}: {region.get('city')}, {region.get('country')}")
    print(f"  options: {', '.join(region.get('options', [])) or 'none listed'}")
    print()

    plans = http_json("GET", f"{API}/plans?per_page=500", token).get("plans", [])
    here = [p for p in plans if args.region in p.get("locations", []) and p.get("monthly_cost", 0) <= args.max_monthly]
    here.sort(key=lambda p: (p.get("type", ""), p.get("monthly_cost", 0)))

    print(f"Plans in {args.region} up to ${args.max_monthly:.0f}/month ({len(here)} found)")
    print(f"  {'type':<8} {'plan id':<30} {'vCPU':>4} {'RAM GB':>7} {'disk GB':>8} {'$/hour':>8} {'$/month':>8}")
    for p in here:
        hourly = p.get("hourly_cost") or p.get("monthly_cost", 0) / HOURS_PER_MONTH
        print(
            f"  {p.get('type', '?'):<8} {p['id']:<30} {p.get('vcpu_count', 0):>4} "
            f"{p.get('ram', 0) / 1024:>7.1f} {p.get('disk', 0):>8} {hourly:>8.3f} {p.get('monthly_cost', 0):>8.2f}"
        )
    print()
    print("Nothing was created. Pick VM 1 (about 2 vCPU / 4 GB) and VM 2 (a VX1 plan, 4 vCPU / 8-16 GB) from this list.")


if __name__ == "__main__":
    main()
