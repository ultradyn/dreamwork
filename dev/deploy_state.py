#!/usr/bin/env python3
"""Report whether the dashboard the human watches is running current code.

    python3 dev/deploy_state.py [--json]

Exit 0 when the deployed snapshot matches `HEAD:watch.py`, 1 when it is behind,
2 when nothing is deployed or the state cannot be determined.

WHY THIS EXISTS
---------------
`status.json` carried the sentence *"deploy = current — deployed.py reports
current (0d1e337), reviewed watch.py serving 127.0.0.1:35110 at PID 62810.
Independently verified by this coordinator at 16:05, not taken on report."*

Every clause of that was true when written. By 18:05 all of it was false: the
serving pid was 175896, the snapshot on disk was from 15:49, and `#218` had
landed at 16:44 — so the median line the loop had recorded as delivered was not
on the page he was looking at, while he used that page to decide the `#263`
gate. Nothing anywhere said so.

The defect is not that the sentence was wrong. It is that **a claim about a
running process was stored as prose with no expiry and nothing that could
contradict it.** A verification timestamped 16:05 cannot cover 18:05, and the
words "independently verified" made it read more durable, not less.

So the claim becomes a measurement: compare the bytes actually deployed against
the bytes at `HEAD`, and report the pid actually listening. Both are cheap, both
are exact, and neither can be stale — it is computed at the moment it is read.

TWO QUESTIONS, NOT ONE — AND THE SECOND ONE CAUGHT ME
----------------------------------------------------
The first version of this file compared the snapshot's bytes to `HEAD:watch.py`
and stopped there. Its own docstring noted the gap it was leaving: *"a running
process could still be serving from memory after its file changed underneath
it."* Two minutes later that gap bit, in this file's own red-proof — overwriting
the snapshot made `--autoreload` re-exec the server into old code, and after the
snapshot was restored this script reported **current** while the served page was
provably pre-`#218` (no `bdmed`, panel back to 158px).

So a file hash cannot answer the question the human actually has. There are two:

  1. is the deployed SNAPSHOT the same code as HEAD?      -> compare bytes
  2. is the RUNNING PROCESS serving that snapshot?         -> compare GENERATION

`GENERATION` is `"%.6f" % time.time()` evaluated at module import and served as
the first field of `/mtime`. It is recomputed on every import, so unlike a pid or
a process start time it **survives `os.exec` re-entry** — a re-exec gets a fresh
GENERATION while keeping its pid. If GENERATION predates the snapshot's mtime,
the process is running code older than the file on disk, whatever the file says.

Both must pass. Either alone reads as reassurance and answers half.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPLOY_DIR = os.path.expanduser("~/.cache/dreamwork/deployed")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def head_watch() -> bytes:
    return subprocess.run(["git", "show", "HEAD:watch.py"], cwd=ROOT,
                          capture_output=True, check=True).stdout


def listening_pid(port: int):
    """The pid actually bound to the port, or None. Never inferred from a file."""
    out = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if f":{port} " in line or line.rstrip().endswith(f":{port}"):
            m = re.search(r"pid=(\d+)", line)
            if m:
                return int(m.group(1))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    st = {"current": False}
    portfile = os.path.join(ROOT, ".dreamwork", "watch-port")
    if not os.path.exists(portfile):
        st["error"] = "no .dreamwork/watch-port — nothing has been deployed"
        print(json.dumps(st) if args.json else st["error"])
        return 2
    st["port"] = port = int(open(portfile).read().strip())

    snap = os.path.join(DEPLOY_DIR, os.path.basename(ROOT) + "-watch.py")
    if not os.path.exists(snap):
        st["error"] = f"no deployed snapshot at {snap}"
        print(json.dumps(st) if args.json else st["error"])
        return 2

    deployed = open(snap, "rb").read()
    head = head_watch()
    st["deployed_sha"] = sha(deployed)[:12]
    st["head_sha"] = sha(head)[:12]
    st["snapshot_matches_head"] = st["deployed_sha"] == st["head_sha"]
    st["pid"] = listening_pid(port)
    st["head_rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                    cwd=ROOT, capture_output=True,
                                    text=True).stdout.strip()

    # QUESTION 2: is the live process running that snapshot? GENERATION is set at
    # module import and re-set on every re-exec, so it is the only signal here
    # that distinguishes "the file is right" from "he is seeing the file".
    snap_mtime = os.path.getmtime(snap)
    st["snapshot_mtime"] = snap_mtime
    st["generation"] = None
    st["process_has_snapshot"] = None
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/mtime", timeout=3) as r:
            gen = float(r.read().decode().split()[0])
        st["generation"] = gen
        # Allow a small slack: the snapshot is written, then the process starts,
        # so GENERATION is normally a beat LATER than the mtime. Only a process
        # whose import predates the file is stale.
        st["process_has_snapshot"] = gen >= snap_mtime - 1.0
        st["process_age_vs_snapshot_s"] = round(gen - snap_mtime, 1)
    except Exception as e:                                  # noqa: BLE001
        st["error_probe"] = f"could not read /mtime: {e}"

    st["current"] = bool(st["snapshot_matches_head"] and st["process_has_snapshot"])

    if not st["current"]:
        # Name what he cannot see, not just that something differs -- "behind" is
        # not actionable and "the median line is missing" is.
        behind = subprocess.run(
            ["git", "log", "--oneline", "--", "watch.py"], cwd=ROOT,
            capture_output=True, text=True).stdout.splitlines()
        st["watch_py_commits_at_head"] = behind[:1]

    if args.json:
        print(json.dumps(st, indent=2))
    else:
        if st["current"]:
            print(f"current — snapshot matches HEAD ({st['head_rev']}) AND the live "
                  f"process is running it (generation "
                  f"{st['process_age_vs_snapshot_s']:+}s vs snapshot); "
                  f"serving :{port} at pid {st['pid']}")
        elif not st["snapshot_matches_head"]:
            print(f"STALE SNAPSHOT — the deployed file does NOT match HEAD "
                  f"({st['head_rev']}); serving :{port} at pid {st['pid']}. "
                  f"He is looking at older code. Run `just deploy`.")
        elif st["process_has_snapshot"] is False:
            print(f"STALE PROCESS — the deployed file matches HEAD ({st['head_rev']}) "
                  f"but the live process imported "
                  f"{abs(st['process_age_vs_snapshot_s'])}s BEFORE it was written, so "
                  f"it is serving older code than the file says. This is the failure "
                  f"a file hash alone reports as fine. Run `just deploy`.")
        else:
            print(f"UNKNOWN — snapshot matches HEAD ({st['head_rev']}) but the live "
                  f"process could not be probed: {st.get('error_probe')}")
    return 0 if st["current"] else 1


if __name__ == "__main__":
    sys.exit(main())
