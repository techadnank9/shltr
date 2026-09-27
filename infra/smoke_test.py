"""Part 3: the essential smoke tests on the live servers. Prints PASS or FAIL per check.

T4  a microVM on VM 2 runs its own kernel, with the CPU limit applied
T5  inside a microVM with --no-net the internet is unreachable, and an endless loop
    is killed by --max-duration; nothing is left running afterwards
T7  from this machine VM 2 has no open public ports, VM 1 answers SSH,
    and VM 2 is reachable from VM 1 over the private network

    python infra/smoke_test.py
Needs infra/state.json and infra/keys/ssh_config from provision.py.
"""
import json
import re
import socket
import subprocess
import sys
import time

from common import REPO_ROOT

# Forward slashes: ProxyJump re-invokes ssh with this path, and backslashes get eaten on Windows.
SSH = ["ssh", "-F", (REPO_ROOT / "infra" / "keys" / "ssh_config").as_posix(), "-o", "BatchMode=yes"]
MSB = "export PATH=/root/.local/bin:$PATH; "
results: dict[str, bool] = {}


def on(host: str, cmd: str, timeout: int = 180) -> str:
    """Run a command on vm1 or vm2. A connection failure (ssh exit 255) stops the whole test,
    so an unreachable server can never be reported as a pass."""
    out = subprocess.run([*SSH, host, cmd], capture_output=True, text=True, timeout=timeout)
    text = (out.stdout + out.stderr).strip()
    if out.returncode == 255:
        sys.exit(f"Could not reach {host} over SSH: {text.splitlines()[-1] if text else 'no output'}")
    return text


def check(name: str, ok: bool, detail: str) -> None:
    results[name] = results.get(name, True) and ok
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<28} {detail}")


def port_open(ip: str, port: int) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=6):
            return True
    except OSError:
        return False


def main() -> None:
    state = json.loads((REPO_ROOT / "infra" / "state.json").read_text())
    vm1, vm2 = state["servers"]["shltr-vm1"], state["servers"]["shltr-vm2"]

    print("T4 · microVM has its own kernel")
    host_kernel = on("vm2", "uname -r")
    on("vm2", MSB + "msb remove -f smoke 2>/dev/null; msb create --name smoke --cpus 1 --memory 256M --no-net --max-duration 120s alpine")
    guest_kernel = on("vm2", MSB + "msb exec smoke -- uname -r").splitlines()[-1]
    guest_cpus = on("vm2", MSB + "msb exec smoke -- nproc").splitlines()[-1]
    looks_like_kernel = bool(re.fullmatch(r"\d+\.\d+\S*", guest_kernel))
    check("T4 separate kernel", looks_like_kernel and guest_kernel != host_kernel, f"host {host_kernel}, sandbox {guest_kernel}")
    check("T4 cpu limit", guest_cpus == "1", f"sandbox sees {guest_cpus} CPU")

    print("T5 · containment")
    net = on("vm2", MSB + "msb exec smoke -- sh -c 'wget -q -T 5 -O- http://example.com >/dev/null 2>&1 && echo REACHED || echo BLOCKED'").splitlines()[-1]
    check("T5 network blocked", net == "BLOCKED", f"outbound request: {net}")
    on("vm2", MSB + "msb stop smoke; msb remove smoke")
    on("vm2", MSB + "msb remove -f loop 2>/dev/null; msb create --name loop --cpus 1 --memory 256M --no-net --max-duration 15s alpine")
    start = time.time()
    on("vm2", MSB + "msb exec loop -- sh -c 'while :; do :; done'", timeout=120)
    took = time.time() - start
    # It must actually run until the limit: stopping at 0 s would mean it never started.
    check("T5 runaway code killed", 10 <= took < 30, f"endless loop stopped after {took:.0f} s (limit 15 s)")
    on("vm2", MSB + "msb stop loop; msb remove loop")
    left = on("vm2", MSB + "msb list")
    check("T5 nothing left running", "No sandboxes" in left, left.splitlines()[-1] if left else "")

    print("T7 · network isolation")
    for port in (22, 80, 443):
        is_open = port_open(vm2["main_ip"], port)
        check("T7 VM 2 closed to internet", not is_open, f"{vm2['main_ip']}:{port} {'OPEN' if is_open else 'closed'}")
    check("T7 VM 1 SSH reachable", port_open(vm1["main_ip"], 22), f"{vm1['main_ip']}:22")
    via = on("vm1", f"timeout 5 bash -c '</dev/tcp/{vm2['vpc_ip']}/22' && echo OPEN || echo CLOSED")
    check("T7 VM 1 -> VM 2 private", via.endswith("OPEN"), f"{vm2['vpc_ip']}:22 from VM 1: {via}")

    failed = [k for k, v in results.items() if not v]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
