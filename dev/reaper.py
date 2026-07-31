#!/usr/bin/env python3
"""#203 — reaper for orphaned watch.py guard servers.

THE PROBLEM (from the ledger)
  Four orphaned watch.py servers were found alive in the guard port ranges,
  one up 4.5h serving dev/capture/fixture. A later readiness probe hit the
  port, got a healthy 200 from a stale fixture nobody was reading, and reported
  feature bugs about that fixture. Three consecutive agents believed they had
  cleaned up. Asking for more care does not work; this is the mechanism.

WHY THE justfile RECIPE IS NOT THE LEAK
  `just guards` traps and kills its own server (justfile: `trap 'kill $SRV
  2>/dev/null; rm -rf "$OUT"' EXIT`). Verified. A trap runs on normal exit and
  on SIGTERM, but NOT on SIGKILL — `kill -9 <shell>` leaves the child server
  alive because the trap cannot run. The other source is servers started BY
  HAND (e.g. the deployed dashboard, started by `nohup` with no trap at all).
  So the orphans are hand-started servers and survivors of SIGKILLed lanes;
  "fixing" the recipe's trap changes nothing.

THE TWO RULES, AND THEY ARE NOT EQUAL
  rule2 (dead-lane, MECHANICAL): readlink /proc/<pid>/cwd ends in " (deleted)".
        The kernel emits that suffix when the cwd's dentry is gone, i.e. the
        lane (worktree, /tmp/pi-agent dir, mktemp dir) that started the server
        has been removed. No threshold, no judgement. THIS IS THE ONLY RULE
        THAT MAY KILL, and even then not by default.
  rule1 (stale, HEURISTIC):      elapsed >= --stale-hours. Report only. Needs a
        human to weigh "is 20 hours long", so the reaper never acts on it.

WHY NOT FILTER BY PORT RANGE
  The nominal guard ranges (39880-39899 watch, 39880-39889 hub) are where the
  `guards`/`watch` recipes DEFAULT, but they are not where orphans actually
  live. Several capture guards and all hub guards call listen(0) and take an
  OS-assigned ephemeral port (justfile header documents each); hand-started
  servers use arbitrary ports (#203 evidence: 39951, 35111, 43875); and the
  recommended fix in #203 is --port 0, which by design lands anywhere. A range
  filter gives false safety. The kill rule is port-independent and that is the
  real safety: a deleted cwd is a dead lane regardless of port. --range LO-HI
  is kept for focused INSPECTION only; it never broadens what --kill may touch.

SAFETY (a bug here kills someone else's live server)
  - Dry-run is the default. No --kill  =>  kills nothing.
  - --kill requires a SECOND flag: --pid PID (one target) or --all-dead (every
    dead-lane). There is no bare machine-wide kill to reach for by accident.
  - --kill reaps rule2 ONLY. A live or stale pid is REFUSED, not killed.
  - DREAMWORK_REAP_NEVER_KILL=pid,pid,pid adds to a denylist (configurable; not
    hardcoded to today's pids — a literal tuned to today's machine rots).
  - pid 1, the reaper's own pid, and unreadable processes are never touched.
  - After SIGTERM, the process EXIT is verified (bounded poll), and three
    outcomes render distinctly: REAPED (gone), SIGNALLED (still alive —
    reported, never auto-SIGKILLed), or refused/skipped. os.kill returning
    means delivered, not dead; the report must not outrun the evidence (#136).

VERIFY BEFORE TRUSTING (this repo means it)
  The classifier has unit tests (test_reaper.py). The live proof — start a
  server from a dir you then delete, confirm dry-run spares it and --kill reaps
  it — is pasted into the commit message as real terminal output, because it
  cannot be made deterministic against a drifting process table.
"""

import argparse
import os
import re
import subprocess
import sys
import time

# classifications
DEAD_LANE = "dead-lane"   # rule2; the only class --kill may reap
STALE = "stale"           # rule1; report only
LIVE = "live"

RULE2 = "rule2-cwd-deleted"
RULE1 = "rule1-elapsed-stale"

# After SIGTERM, poll this long for actual exit before reporting SIGNALLED
# rather than REAPED. Bounded: os.kill returning means the signal was DELIVERED,
# not that the process died, and "I sent a signal" must not render as "it is
# gone" (#136). No auto-escalation to SIGKILL — report and let a human decide
# (#288: neither posture nor a timeout confers kill authority).
_VERIFY_TIMEOUT = 3.0
_VERIFY_POLL = 0.05

_DELETED_SUFFIX = " (deleted)"
_SERVER_FLAGS = ("--port", "--target", "--dev", "--autoreload", "--open")


# ---------------------------------------------------------------------------
# pure functions (unit-tested in test_reaper.py)
# ---------------------------------------------------------------------------

def is_dead_lane(cwd):
    return cwd.endswith(_DELETED_SUFFIX)


def classify(rec, stale_hours):
    """rec: {cwd, target, elapsed_secs}. Returns (classification, rule|None).

    rule2 beats rule1 on purpose: a deleted cwd is dead-lane however old the
    process is, so the kill decision never depends on a tunable threshold.
    """
    cwd = rec.get("cwd") or ""
    if is_dead_lane(cwd):
        return (DEAD_LANE, RULE2)
    elapsed_h = (rec.get("elapsed_secs") or 0) / 3600.0
    if elapsed_h >= stale_hours:
        return (STALE, RULE1)
    return (LIVE, None)


def parse_cmdline(args):
    """Extract watch-server facts from an argv list.

    is_watch_server: an arg whose basename ends in 'watch.py' AND a server flag
    is present. The flag gate stops `grep watch.py` / `ps|grep watch.py` false
    positives — same watch.py token, flag presence is the only difference.
    """
    watch_arg = next((a for a in args if os.path.basename(a).endswith("watch.py")), None)
    is_server = watch_arg is not None and any(f in args for f in _SERVER_FLAGS)
    port = None
    port_was_zero = False
    if "--port" in args:
        i = args.index("--port")
        if i + 1 < len(args):
            try:
                port = int(args[i + 1])
                port_was_zero = (port == 0)
            except ValueError:
                pass
    target = None
    if "--target" in args:
        i = args.index("--target")
        if i + 1 < len(args):
            target = args[i + 1]
    return {"is_watch_server": is_server, "port": port,
            "port_was_zero": port_was_zero, "target": target}


def elapsed_from_starttime(starttime_ticks, btime_epoch, now_epoch, clktck):
    return now_epoch - (btime_epoch + starttime_ticks / float(clktck))


def parse_proc_stat(stat_text):
    """Return (comm, starttime_ticks). comm (field 2) may contain spaces and
    parens, so we cut between the FIRST '(' and the LAST ')'. Field 22
    (starttime) is the 20th token after the comm (fields 3..21 precede it)."""
    s = stat_text.strip()
    lparen = s.find("(")
    rparen = s.rfind(")")
    comm = s[lparen + 1:rparen]
    rest = s[rparen + 2:].split()
    starttime_ticks = int(rest[19])  # field 22 - field 3 == index 19
    return comm, starttime_ticks


# ---------------------------------------------------------------------------
# /proc + ss gatherers (not unit-tested; exercised by the live RED proof)
# ---------------------------------------------------------------------------

def _read_cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read()
    except OSError:
        return []
    return [a for a in raw.decode("utf-8", "replace").split("\0") if a]


def _read_cwd(pid):
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return ""


def _boot_time():
    try:
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("btime "):
                    return float(line.split()[1])
    except OSError:
        pass
    return 0.0


def _clktck():
    try:
        return os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    except (OSError, KeyError, ValueError):
        return 100


def _elapsed_secs(pid, btime, clktck):
    try:
        with open(f"/proc/{pid}/stat") as f:
            _, starttime = parse_proc_stat(f.read())
    except (OSError, ValueError, IndexError):
        return None
    return elapsed_from_starttime(starttime, btime, time.time(), clktck)


def _listening_ports_by_pid():
    """One ss -tlnp call -> {pid: [ports]}. ss is referenced by the task and by
    the justfile pre-flight; it attributes listening sockets to pids for
    same-user processes. Returns {} if ss is unavailable."""
    try:
        out = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    by_pid = {}
    # local addr is the token containing ':PORT'; pid appears in users:(...)
    for line in out.splitlines():
        if "pid=" not in line:
            continue
        port = None
        for tok in line.split():
            if tok.startswith("127.0.0.1:") or tok.startswith("0.0.0.0:") \
               or tok.startswith("[::]:") or tok.startswith("[::1]:") \
               or ":" in tok and tok.rsplit(":", 1)[-1].isdigit():
                maybe = tok.rsplit(":", 1)[-1]
                if maybe.isdigit():
                    port = int(maybe)
                    break
        for m in re.finditer(r"pid=(\d+)", line):
            pid = int(m.group(1))
            if port is not None:
                by_pid.setdefault(pid, []).append(port)
    return by_pid


def _gather_one(pid, stale_hours, btime, clktck, ports_by_pid):
    args = _read_cmdline(pid)
    info = parse_cmdline(args)
    if not info["is_watch_server"]:
        return None
    cwd = _read_cwd(pid)
    target = info["target"]
    ports = ports_by_pid.get(pid, [])
    # cmdline port is the REQUESTED port; ss gives the REAL listening port.
    # For --port 0 the real port is only knowable from ss.
    if ports:
        port = ports[0]
    elif info["port"] is not None:
        port = info["port"]
    else:
        port = None
    elapsed = _elapsed_secs(pid, btime, clktck)
    rec = {
        "pid": pid,
        "cwd": cwd,
        "target": target if target is not None else "(default cwd)",
        "port": port,
        "port_requested_zero": info["port_was_zero"],
        "elapsed_secs": elapsed if elapsed is not None else 0,
        "elapsed_unknown": elapsed is None,
        "cmd": " ".join(args),
        "is_deployed": "/deployed/" in " ".join(args) and "watch.py" in " ".join(args),
    }
    cls, rule = classify({"cwd": cwd, "target": rec["target"],
                          "elapsed_secs": rec["elapsed_secs"]}, stale_hours)
    rec["classification"] = cls
    rec["rule"] = rule
    return rec


def gather(stale_hours):
    btime = _boot_time()
    clktck = _clktck()
    ports_by_pid = _listening_ports_by_pid()
    records = []
    for entry in sorted(os.listdir("/proc"), key=lambda s: int(s) if s.isdigit() else 10 ** 12):
        if not entry.isdigit():
            continue
        try:
            rec = _gather_one(int(entry), stale_hours, btime, clktck, ports_by_pid)
        except OSError:
            continue  # process exited between listing and reading
        if rec is not None:
            records.append(rec)
    return records


# ---------------------------------------------------------------------------
# reporting / killing
# ---------------------------------------------------------------------------

def _humanize(secs):
    if secs is None:
        return "?"
    s = int(secs)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    if d:
        return f"{d}d{h}h{m}m"
    if h:
        return f"{h}h{m}m"
    return f"{m}m"


def _never_kill():
    raw = os.environ.get("DREAMWORK_REAP_NEVER_KILL", "")
    out = set()
    for tok in raw.replace(";", ",").split(","):
        tok = tok.strip()
        if tok.isdigit():
            out.add(int(tok))
    return out


def _in_range(port, lo, hi):
    return port is not None and lo <= port <= hi


def _print_record(rec, would_kill=False):
    cls = rec["classification"]
    rule = rec["rule"] or "-"
    elapsed = "?" if rec["elapsed_unknown"] else _humanize(rec["elapsed_secs"])
    port = rec["port"] if rec["port"] is not None else "?"
    pzero = " (requested 0)" if rec.get("port_requested_zero") else ""
    deployed = "  note=deployed-dashboard" if rec.get("is_deployed") else ""
    verb = "WOULD-KILL" if would_kill else "report  "
    print(f"  [{cls:<8} {rule:<20}] {verb} pid={rec['pid']} port={port}{pzero} "
          f"elapsed={elapsed} target={rec['target']}{deployed}")
    print(f"        cwd={rec['cwd']}")
    print(f"        cmd={rec['cmd']}")


def _process_state(pid):
    """One-character state from /proc/<pid>/stat, or None if unreadable.
    'Z' is a zombie: terminated, holding no resources, waiting for its parent
    to read its exit status. For the reaper's purposes a zombie is GONE."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            s = f.read()
        rparen = s.rfind(")")
        rest = s[rparen + 2:].split()
        return rest[0]  # field 3, the state char
    except (OSError, IndexError):
        return None


def _wait_for_exit(pid, timeout=_VERIFY_TIMEOUT, poll=_VERIFY_POLL):
    """Poll until the process is gone or the timeout elapses.

    "Gone" is: the pid has vanished (ProcessLookupError on os.kill(pid, 0))
    OR the process is a zombie ('Z' state) — terminated, holding no resources,
    just waiting for its parent to read its exit status. Both mean the signal
    landed and the process will never run again.

    os.kill(pid, 0) succeeding alone does NOT establish this: a zombie passes
    that probe (#730). Returns True if gone, False if still alive at timeout.
    PermissionError (exists, not ours) reads as alive: the report stays honest.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        if _process_state(pid) == "Z":
            return True
        time.sleep(poll)
    return False


def do_kill(records, pid_targets, all_dead, never_kill,
            verify_timeout=_VERIFY_TIMEOUT):
    """Reap dead-lane records only. Returns (killed, signalled, refused, skipped).

    Three outcomes after SIGTERM, distinctly rendered by the caller:
      killed     — SIGTERM delivered AND the process is confirmed gone (#671:
                   a completed action that was verified, not just attempted).
      signalled  — SIGTERM delivered, but the process is still alive after a
                   bounded wait. Reported, never auto-escalated to SIGKILL
                   (#288: the design earns trust by being narrow).
      refused/skipped — unchanged.
    """
    self_pid = os.getpid()
    killed, signalled, refused, skipped = [], [], [], []
    if all_dead:
        targets = [r for r in records if r["classification"] == DEAD_LANE]
    else:
        by_pid = {r["pid"]: r for r in records}
        targets = [by_pid[p] for p in pid_targets if p in by_pid]
        # pids we were asked for but that aren't watch servers at all
        for p in pid_targets:
            if p not in by_pid:
                refused.append((p, "not a watch.py server (or already gone)"))
    for rec in targets:
        pid = rec["pid"]
        if pid in never_kill:
            skipped.append((pid, "in DREAMWORK_REAP_NEVER_KILL"))
            continue
        if pid <= 1 or pid == self_pid:
            skipped.append((pid, "protected (init/self)"))
            continue
        # The instance the human READS is never sweepable, and the dead-lane
        # rule does not exempt it: `just deploy` starts the snapshot from the
        # current directory, so deploying from a worktree and later removing
        # that worktree leaves the deployed dashboard with a `(deleted)` cwd and
        # classifies it exactly like an orphan. `is_deployed` was already
        # computed for the display note; consulting it here is what makes the
        # note load-bearing. No flag overrides this — an operator who really
        # means to stop the deployed instance has `just deploy` and a plain
        # `kill`, neither of which can be reached by a sweep.
        if rec.get("is_deployed"):
            skipped.append((pid, "the DEPLOYED dashboard — never reaped by this tool"))
            continue
        if rec["classification"] != DEAD_LANE:
            # --all-dead can't reach here; only --pid of a non-dead server can
            refused.append((pid, f"{rec['classification']} (not dead-lane); "
                                 f"--kill reaps rule2 ONLY"))
            continue
        try:
            os.kill(pid, 15)  # SIGTERM first; watch.py exits cleanly
        except ProcessLookupError:
            skipped.append((pid, "already gone"))
            continue
        except PermissionError:
            skipped.append((pid, "permission denied"))
            continue
        # os.kill returned: the signal was DELIVERED, not that the process
        # died. Poll for actual exit before claiming it is gone (#136/#671).
        if _wait_for_exit(pid, timeout=verify_timeout):
            killed.append(rec)
        else:
            signalled.append(rec)
    return killed, signalled, refused, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="reaper.py",
        description="Find and (with explicit flags) reap orphaned watch.py "
                    "guard servers. DRY-RUN BY DEFAULT.",
    )
    ap.add_argument("--stale-hours", type=float, default=2.0,
                    help="rule1 threshold (heuristic, report-only). default 2")
    ap.add_argument("--range", dest="port_range", metavar="LO-HI",
                    help="inspect only ports in this range (e.g. 39880-39899). "
                         "Never broadens what --kill may touch.")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--kill", action="store_true",
                    help="enable killing (still needs --pid or --all-dead)")
    ap.add_argument("--pid", action="append", type=int, metavar="PID",
                    help="reap this one pid (repeatable). Must be dead-lane.")
    ap.add_argument("--all-dead", action="store_true",
                    help="reap every dead-lane (rule2) server. REQUIRES --yes: "
                         "a machine-wide sweep is a drift-driven footgun (a pid "
                         "that was report-only at dispatch can become dead-lane "
                         "by the time the reaper runs), so --all-dead without "
                         "--yes only LISTS what it would reap. "
                         "Respects DREAMWORK_REAP_NEVER_KILL.")
    ap.add_argument("--yes", action="store_true",
                    help="confirm a --kill --all-dead sweep. Without it, "
                         "--all-dead refuses and prints the target list + the "
                         "never-kill env to set. Deliberate friction.")
    args = ap.parse_args(argv)

    lo = hi = None
    if args.port_range:
        m = re.match(r"^(\d+)-(\d+)$", args.port_range.strip())
        if not m:
            print("reaper: --range expects LO-HI (e.g. 39880-39899)", file=sys.stderr)
            return 2
        lo, hi = int(m.group(1)), int(m.group(2))

    records = gather(args.stale_hours)
    if lo is not None:
        records = [r for r in records if _in_range(r["port"], lo, hi)
                   or r["port"] is None]  # keep port-unknown so they're visible

    never_kill = _never_kill()

    if args.json:
        import json
        print(json.dumps({"records": records,
                          "never_kill": sorted(never_kill)}, indent=2, default=str))
        return 0

    n = len(records)
    by_cls = {DEAD_LANE: 0, STALE: 0, LIVE: 0}
    for r in records:
        by_cls[r["classification"]] += 1

    if not args.kill:
        mode = f"dry-run (kills nothing). {n} watch.py server(s)"
        if lo is not None:
            mode += f" in [{lo},{hi}]"
        print(f"reaper: {mode}")
        for r in sorted(records, key=lambda r: (r["classification"] != DEAD_LANE,
                                                r["classification"],
                                                r["pid"])):
            _print_record(r, would_kill=False)
        print(f"reaper: {by_cls[DEAD_LANE]} dead-lane (killable via --kill --pid/--all-dead), "
              f"{by_cls[STALE]} stale (report only), {by_cls[LIVE]} live.")
        if by_cls[DEAD_LANE] and not args.kill:
            pids = ",".join(str(r["pid"]) for r in records
                            if r["classification"] == DEAD_LANE)
            print(f"reaper: to reap dead-lane only: python3 dev/reaper.py --kill --all-dead")
            print(f"        (or --pid N). never-kill env: DREAMWORK_REAP_NEVER_KILL={pids}")
        return 0

    # --kill path: require a second flag
    if not args.pid and not args.all_dead:
        print("reaper: --kill needs a target: --pid PID or --all-dead "
              "(no bare machine-wide kill).", file=sys.stderr)
        return 2

    # --all-dead is a machine-wide sweep and a drift-driven footgun: a pid that
    # was report-only at dispatch can become dead-lane (cwd deleted) by the time
    # the reaper runs, and a bare sweep would reap it. So --all-dead without
    # --yes only LISTS the targets and the never-kill env to set. This gate
    # exists because the author reaped two pids he was told to spare by running
    # an ungated --all-dead during this very task; do not remove it without
    # replacing it with something at least as deliberate.
    if args.all_dead and not args.yes:
        dead = [r for r in records if r["classification"] == DEAD_LANE]
        print(f"reaper: --all-dead REFUSED without --yes. {len(dead)} dead-lane "
              f"server(s) would be reaped:", file=sys.stderr)
        for r in dead:
            _print_record(r, would_kill=True)
        if dead:
            pids = ",".join(str(r["pid"]) for r in dead)
            print(f"reaper: to spare any of these, run again after setting "
                  f"DREAMWORK_REAP_NEVER_KILL={pids}", file=sys.stderr)
        print("reaper: to proceed with the sweep: add --yes.", file=sys.stderr)
        return 2

    killed, signalled, refused, skipped = do_kill(
        records, args.pid or [], args.all_dead, never_kill)

    for rec in killed:
        elapsed = _humanize(rec["elapsed_secs"])
        print(f"reaper: REAPED pid={rec['pid']} port={rec['port']} "
              f"elapsed={elapsed} target={rec['target']} rule={rec['rule']}")
        print(f"        cmd={rec['cmd']}")
    for rec in signalled:
        elapsed = _humanize(rec["elapsed_secs"])
        print(f"reaper: SIGNALLED pid={rec['pid']} port={rec['port']} "
              f"elapsed={elapsed} target={rec['target']} rule={rec['rule']}")
        print(f"        SIGTERM delivered but the process is still alive after "
              f"{_VERIFY_TIMEOUT:.0f}s — NOT confirmed gone.")
        print(f"        No auto-SIGKILL (by design). To finish: kill -9 {rec['pid']} "
              f"(a human decision, not this tool's).")
        print(f"        cmd={rec['cmd']}")
    for pid, why in refused:
        print(f"reaper: REFUSED pid={pid}: {why}", file=sys.stderr)
    for pid, why in skipped:
        print(f"reaper: skipped pid={pid}: {why}")
    if not killed and not signalled and not refused and not skipped:
        print("reaper: nothing to reap (no matching dead-lane servers).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
