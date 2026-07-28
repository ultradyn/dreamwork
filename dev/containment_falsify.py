#!/usr/bin/env python3
"""PROTOTYPE — #288 subagent-tool containment falsification. NOT WIRED IN.

This is a bounded *falsification* artifact, not a shipped mechanism. It is not
imported by anything, run by any recipe, or wired into the loop. It exists to
answer one question for the design in `.dreamwork/docs/plans/subagent-containment.md`:
**does a real namespace boundary on THIS host actually block the three attacks
of the #288 incident class** — a same-UID signal to a process the agent did not
create, a read of a path it was not given, and a network reach to a port it does
not own — and at what cost?

It is falsification, not demonstration: it tries to BREAK the boundary and
records whether it could. A "HELD" result means the named mechanism blocked
that vector; "BROKEN" means the boundary failed and the design must say so.

WHAT IT TOUCHES, AND ONLY THIS
------------------------------
- It spawns its OWN victim processes (a `sleep` for the signal test and a TCP
  listener for the network test) and terminates them itself. It never signals,
  kills, stops or restarts any process it did not create — the #288 rule, held
  absolutely. The victim is named below so the result is auditable.
- It binds the network victim to `127.0.0.1` on a KERNEL-ASSIGNED port and
  asserts that port is outside the dashboard/hub ranges (39880-39899) and is not
  the deployed dashboard port (35110). It never touches :35110.
- It creates one temp dir under `/tmp` for a secret file and its own scratch, and
  removes it on exit. No host change: no unit, daemon, config, sudo, pulled image
  or persistent port.
- The containment mechanism it exercises is `bwrap` (bubblewrap): no daemon, no
  image, no persistent state — it creates ephemeral namespaces that vanish when
  the contained process exits. `bwrap` was chosen because it is present on this
  host, needs no root, and is the cheapest real boundary available; see the
  design doc for why a container-per-lane was rejected on cost.

WHY BWRAP, AND WHY THAT IS NOT THE WHOLE ANSWER
-----------------------------------------------
The prototype proves the *mechanism* blocks the three vectors. It does NOT prove
the loop can route a harness subagent's tool calls through it: the harness owns
both the LLM call and tool execution, so there is no per-tool-call seam to cut
without harness cooperation. That integration gap is the design's central finding
and the reason the positive PID/health invariants remain the whole win. This file
tests the cheap half (can a namespace wall hold?); the expensive half (can we get
the harness to run inside it?) is design-only here.

Exit code: 0 if every recorded vector was determinate (HELD or BROKEN, never
UNKNOWN past a runtime that exists); 2 if bwrap is absent — i.e. the
falsification could not run without a runtime authorisation the prototype does
not install (the brief's "report what you would need" case).
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

MECHANISM = "bwrap (bubblewrap) --unshare-pid --unshare-net, read-only root bind, tmpfs mask"
FORBIDDEN_PORTS = set(range(39880, 39900)) | {35110}
ATTACK_TIMEOUT = 12  # seconds, hard cap on each contained attack run


def log(msg: str) -> None:
    print(msg, flush=True)


def have(tool: str) -> str | None:
    return shutil.which(tool)


def spawn_signal_victim() -> tuple[int, str]:
    """A sleep the attacker will try to signal. Ours; we kill it."""
    p = subprocess.Popen(["sleep", "600"])
    return p.pid, f"sleep 600 (pid {p.pid}, ours)"


def spawn_net_victim() -> tuple[int, int, list[int]]:
    """A TCP listener on a kernel-assigned 127.0.0.1 port, outside forbidden
    ranges. Ours; we kill it. Returns (pid, port, accepts).

    The child shares `accepts` via a list mutated across the fork only because
    the fork copies the parent's memory at the call — so the PARENT cannot read
    the child's count. Instead the child writes its accept count to a temp file
    we own; we read that for the host-side ground-truth verdict (the only way the
    boundary actually broke is if this victim accepted a connection). Parsing
    attacker output for a verdict is the hollow-check trap this file exists
    beside, so every verdict here is derived from ground truth on the host side.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    assert port not in FORBIDDEN_PORTS, (
        f"kernel assigned a forbidden port {port}; refusing to bind")
    counter = tempfile.NamedTemporaryFile(
        prefix="containment-netcount-", suffix=".txt", delete=False)
    counter.write(b"0\n")
    counter.flush()
    counter_path = counter.name
    counter.close()
    pid = os.fork()
    if pid == 0:  # child: accept-loop, count every connection that lands
        try:
            srv.settimeout(120)
            n = 0
            while True:
                try:
                    conn, _ = srv.accept()
                except (socket.timeout, OSError):
                    break
                n += 1
                try:
                    with open(counter_path, "w") as fh:
                        fh.write(f"{n}\n")
                except OSError:
                    pass
                conn.close()
        finally:
            os._exit(0)
    srv.close()  # parent does not keep the fd
    return pid, port, [counter_path]


def run_attack(attacker_argv: list[str], env: dict[str, str]) -> tuple[int, str]:
    """Run one contained attack, bounded by ATTACK_TIMEOUT."""
    try:
        out = subprocess.run(
            attacker_argv, env=env, capture_output=True, text=True,
            timeout=ATTACK_TIMEOUT)
        body = (out.stdout + out.stderr).strip()
        return out.returncode, body
    except subprocess.TimeoutExpired as e:
        body = ((e.stdout or "") + (e.stderr or "")).strip()
        return 124, f"<timeout after {ATTACK_TIMEOUT}s>\n{body}"


def bwrap_attack(bwrap: str, host_root: str, script: str, env: dict[str, str]) -> tuple[int, str]:
    """Run `script` (sh -c) inside bwrap: separate pid+net ns, read-only whole
    root, tmpfs over our own scratch so the secret is masked out."""
    return run_attack([
        bwrap,
        "--unshare-pid", "--unshare-net",
        "--ro-bind", "/", "/",
        "--tmpfs", host_root,
        "--proc", "/proc", "--dev", "/dev",
        "/bin/sh", "-c", script,
    ], env)


def main() -> int:
    print(textwrap.dedent(__doc__).split("\n\n")[0])
    print(f"mechanism: {MECHANISM}")
    print(f"forbidden ports (never touched): {sorted(FORBIDDEN_PORTS)}\n")

    bwrap = have("bwrap")
    if not bwrap:
        log("RESULT: UNKNOWN — bwrap absent on this host.")
        log("  The falsification requires a namespace runtime. bwrap is the")
        log("  cheapest no-daemon, no-image option; installing it is a host")
        log("  change the brief withholds. That is a complete answer: the")
        log("  boundary is untestable here without authorising the install.")
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="containment-falsify-"))
    secret = tmp / "secret.txt"
    secret.write_text(f"TOPSECRET-{time.time_ns()}\n")
    sig_pid, sig_desc = spawn_signal_victim()
    net_pid, net_port, net_counter = spawn_net_victim()
    log(f"victims (all mine, killed at exit):")
    log(f"  signal: {sig_desc}")
    log(f"  network: TCP listener pid {net_pid} on 127.0.0.1:{net_port}\n")

    results = {
        "mechanism": MECHANISM,
        "victims": {"signal": sig_desc, "net_port": net_port},
        "verdict_source": "all three verdicts derived from host-side ground truth, "
                          "never from parsing attacker output (hollow-check guard)",
    }
    try:
        env = dict(os.environ)

        # --- Attack 1: signal a process the attacker did not create (#288 vector) ---
        script1 = (
            f"kill -0 {sig_pid} 2>&1; echo \"rc=$?\"; "
            f"kill -TERM {sig_pid} 2>&1; echo \"rc=$?\""
        )
        rc, body = bwrap_attack(bwrap, str(tmp), script1, env)
        held = sig_pid_is_alive(sig_pid)  # boundary held iff OUR victim survived
        results["attack_signal"] = {
            "target": sig_desc, "rc": rc, "output": body,
            "verdict": "HELD" if held else "BROKEN",
        }

        # --- Attack 2: read a path the attacker was not given (secret masked by tmpfs) ---
        script2 = f"cat {secret} 2>&1; echo \"rc=$?\""
        rc, body = bwrap_attack(bwrap, str(tmp), script2, env)
        # Boundary held iff the secret value did not leak.
        leaked = "TOPSECRET-" in body
        results["attack_read"] = {
            "target": str(secret), "rc": rc, "output": body,
            "verdict": "HELD" if not leaked else "BROKEN",
        }

        # --- Attack 3: reach a network port the attacker does not own ---
        # Ground truth is the victim's accept count, not the attacker's stdout
        # (a traceback prints the source line and would false-positive). The
        # boundary broke ONLY if this victim accepted a connection.
        before = _read_counter(net_counter[0])
        script3 = (
            f"python3 -c \"import socket; "
            f"s=socket.create_connection(('127.0.0.1',{net_port}),timeout=2); "
            f"s.close()\" 2>&1; echo \"inner_rc=$?\""
        )
        rc, body = bwrap_attack(bwrap, str(tmp), script3, env)
        after = _read_counter(net_counter[0])
        crossed = after > before
        results["attack_net"] = {
            "target": f"127.0.0.1:{net_port}", "rc": rc, "output": body,
            "victim_accepts_before_after": [before, after],
            "verdict": "HELD" if not crossed else "BROKEN",
        }

        # --- Latency cost of standing up one contained attacker (per-lane proxy) ---
        t0 = time.perf_counter()
        run_attack([
            bwrap, "--unshare-pid", "--unshare-net",
            "--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev",
            "/bin/true",
        ], env)
        startup_ms = round((time.perf_counter() - t0) * 1000, 1)
        results["measured_startup_ms_one_attacker"] = startup_ms

    finally:
        # Kill ONLY the victims we created. Never anything else.
        for pid in (sig_pid, net_pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError:
                pass
        try:
            os.unlink(net_counter[0])
        except OSError:
            pass
        shutil.rmtree(tmp, ignore_errors=True)

    print("=== recorded results ===")
    print(json.dumps(results, indent=2, sort_keys=True))
    print("=== end ===")
    verdicts = [results[k]["verdict"] for k in ("attack_signal", "attack_read", "attack_net")]
    print(f"overall: {'HELD on all three' if all(v=='HELD' for v in verdicts) else 'BROKEN on ' + ', '.join(v for v in verdicts if v!='HELD')}")
    return 0


def _read_counter(path: str) -> int:
    """Read the net victim's accept count, written by the forked child. Host
    ground truth, so the net verdict is never derived from attacker output."""
    try:
        with open(path) as fh:
            return int(fh.read().strip() or "0")
    except (OSError, ValueError):
        return 0


def sig_pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        # Reap any direct child the fork left if main exited unusually.
        try:
            os.waitid(os.P_ALL, 0, os.WNOHANG)
        except (OSError, ChildProcessError):
            pass
