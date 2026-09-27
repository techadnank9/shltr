# infra: Vultr servers for Shltr

Everything needed to create, check and delete Shltr's Vultr setup. All scripts use Python's standard library and read keys from the repo-root `.env`.

## What exists

```
            internet
               │  80, 443 from anywhere · 22 from the admin IP only
               ▼
   shltr-vm1 · control plane · vc2-2c-4gb · Ubuntu 24.04
               │  private network shltr-vpc 10.40.0.0/24 (never touches the internet)
               ▼
   shltr-vm2 · sandbox host · vx1-g-4c-16g-240s (KVM) · Ubuntu 24.04
               no inbound ports on the internet · runs Microsandbox microVMs
```

Cost: about $0.18 per hour for both servers (about $4.30 per day).

## Commands, in order

```
python infra/check_vultr.py                 # account, credit, plans and prices (read-only)
python infra/check_inference.py             # model tests T1-T3
python infra/provision.py                   # dry run: shows what would be created and the cost
python infra/provision.py --yes             # create it; writes infra/state.json and infra/keys/ssh_config
ssh -F infra/keys/ssh_config vm1 'bash -s' < infra/bootstrap/vm1.sh
ssh -F infra/keys/ssh_config vm2 'bash -s' < infra/bootstrap/vm2.sh
python infra/smoke_test.py                  # T4, T5, T7: must print 8/8 checks passed
python infra/teardown.py                    # dry run: lists what would be deleted
python infra/teardown.py --yes              # delete everything (Vultr bills stopped servers)
```

Log in with `ssh -F infra/keys/ssh_config vm1`, or `... vm2`, which hops through VM 1 over the private network.

## Files

| File | What it does |
|---|---|
| `common.py` | Loads `.env`, makes JSON API calls, explains common API errors |
| `check_vultr.py`, `check_inference.py` | Part 1 checks |
| `provision.py` | Creates the SSH key, VPC, two firewall groups and two servers. Reuses anything that already exists |
| `bootstrap/vm1.sh` | VM 1 host firewall: 22, 80, 443 |
| `bootstrap/vm2.sh` | VM 2 host firewall: private network only; installs Microsandbox and runs `msb doctor` |
| `smoke_test.py` | T4 (own kernel, CPU limit), T5 (network blocked, runaway loop killed, nothing left), T7 (VM 2 closed to the internet, VM 1 → VM 2 private) |
| `teardown.py` | Deletes every `shltr-*` resource, servers first |

Git ignores `infra/keys/` (the SSH private key, `ssh_config`, `known_hosts`) and `infra/state.json` (IDs and IPs).

## Why VM 2 has a host firewall

The first smoke test showed VM 2's SSH port answering from the internet even though its Vultr firewall group had no rules. Ubuntu's default `ufw` allowed SSH from anywhere, and the Vultr firewall group did not filter this VX1 server. So `bootstrap/vm2.sh` enforces the rule on the server itself: only the private network interface accepts inbound traffic. That gives two layers, and the smoke test checks the result from outside.

## Microsandbox flags we rely on

| Flag | Used for |
|---|---|
| `--no-net` | Photo sandbox: no network at all |
| `--net-rule allow@<target>` | Browser sandbox (later): block everything except our aid portal and demo scam page |
| `--max-duration 120s` | Time limit; the sandbox is killed when it runs out |
| `--cpus`, `--memory` | Resource limits |

Measured on VM 2: a new alpine microVM starts in under a second; its kernel is 6.12.109 while the host runs 6.8.0-139-generic.

## Other people using these scripts

The Vultr API key only works from IPs on its Access Control list, and SSH to VM 1 is only open to the IP that ran `provision.py`. To work from another network, add that IP to the API key's Access Control list and to the `shltr-vm1` firewall group (port 22) in the Vultr dashboard. Re-running `provision.py` reuses the existing firewall groups and does not change their rules. The SSH private key is not in git, so share it privately if another person needs server access.
