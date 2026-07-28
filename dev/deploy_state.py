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
import ast
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPLOY_DIR = os.path.expanduser("~/.cache/dreamwork/deployed")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- symlink-safe blob resolution (#425) -----------------------------------
#
# Git stores a symlink as a blob whose CONTENT is the target path. So once
# watch.py becomes a symlink (the #368 plan: `watch.py -> deprecated/watch.py`),
# `git show HEAD:watch.py` emits the 19-byte string `deprecated/watch.py`,
# which `ast.parse` accepts (it parses as `deprecated / watch.py`). That is the
# measured blocker: the deploy recipe snapshotted those bytes, its syntax guard
# passed them, pkill took the good server down, and the garbage snapshot died
# on import — leaving his dashboard dark. (Reproduced in the #425 report; the
# 19 bytes and the accepted parse are quoted there.)
#
# The two functions below are the single source of truth for "what are
# watch.py's bytes at a rev, link-resolved" and "is this snapshot the server".
# `deploy` (the justfile recipe) and the HEAD comparison below BOTH call them,
# so the recipe and deploy_state agree by construction — there is no second
# implementation in bash to drift. The resolver is rev-aware (it inspects
# `git ls-tree <rev>`, not the working index) so a deploy of a non-HEAD rev
# still resolves correctly.
SYMLINK_MODE = "120000"


def _ls_tree_entry(repo, rev, path):
    """`(mode, sha)` of `path` at `rev`, or `(None, None)` if it is absent.

    `git ls-tree` is the rev-aware way to read a blob's mode; `git ls-files`
    would read the working index instead and lie about a rev the deploy is
    snapshotting. The format is `<mode> <type> <sha>\t<path>`.
    """
    res = subprocess.run(
        ["git", "ls-tree", rev, "--", path],
        cwd=str(repo), capture_output=True, text=True, check=True)
    line = res.stdout.rstrip("\n")
    if not line:
        return None, None
    meta = line.split("\t", 1)[0]
    mode, _type, sha = meta.split()
    return mode, sha


def resolve_blob(rev="HEAD", path="watch.py", repo=ROOT) -> bytes:
    """The bytes of `path` at `rev`, following in-tree symlinks.

    For a regular file this is identical to `git show <rev>:<path>`. For a
    symlink it is the TARGET'S bytes — the real module — not the 19-byte link
    string. Symlink targets are resolved relative to the link's own directory
    (git stores the raw link text), and a chain is followed up to a cap so a
    cycle aborts instead of hanging. The #368 link (`watch.py ->
    deprecated/watch.py`, root-relative) resolves in one step; the loop is for
    generality and is cheap (one `ls-tree` per hop, and only when there is a
    link to follow).
    """
    seen = set()
    for _ in range(20):                       # cap: a cycle must abort, not hang
        mode, sha = _ls_tree_entry(repo, rev, path)
        if sha is None:
            raise RuntimeError(
                f"{path!r} is not tracked at {rev} in {repo}")
        if mode != SYMLINK_MODE:
            return subprocess.run(
                ["git", "cat-file", "blob", sha],
                cwd=str(repo), capture_output=True, check=True).stdout
        # mode 120000: the blob's content is the link target path string.
        target = subprocess.run(
            ["git", "cat-file", "blob", sha],
            cwd=str(repo), capture_output=True, check=True
        ).stdout.decode("utf-8", "replace").rstrip("\n")
        if not target:
            raise RuntimeError(f"symlink at {path!r} has an empty target")
        link_dir = posixpath.dirname(path)
        path = (posixpath.normpath(posixpath.join(link_dir, target))
                if link_dir else target)
        if path in seen:
            raise RuntimeError(f"symlink cycle detected resolving {path!r}")
        seen.add(path)
    raise RuntimeError(f"symlink chain at {path!r} too deep (>20 hops)")


# The two markers a snapshot must define to BE the server, not merely parse.
# Both are module-level in watch.py and both are load-bearing: `main` is the
# entry point the deploy recipe execs, and `GENERATION` is the /mtime field
# this file probes to tell "the file is right" from "he is seeing the file".
# A path string (`deprecated/watch.py`), an empty file, or a truncated blob
# all parse as Python but define NEITHER — a path string is a single division
# expression with no top-level statements at all — so asserting both present
# rejects exactly the inputs the old `ast.parse`-only guard waved through.
SERVER_TOPLEVEL_MAIN = "main"
SERVER_TOPLEVEL_GENERATION = "GENERATION"


def assert_is_server(src: bytes) -> None:
    """Prove `src` is the watch.py server module.

    Raises `SyntaxError` if it is not valid Python, `ValueError` if it parses
    but does not define both server markers at module top level. Returns None
    on success. This is the guard that replaced `ast.parse(open(snap).read())`
    in the deploy recipe: a syntax check measures the wrong property, because
    the thing that broke deploy (`deprecated/watch.py`) is valid syntax.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        raise SyntaxError(
            f"snapshot does not parse as Python: {exc.msg}") from exc
    has_main = any(isinstance(n, ast.FunctionDef)
                   and n.name == SERVER_TOPLEVEL_MAIN for n in tree.body)
    has_generation = False
    for n in tree.body:
        if isinstance(n, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == SERVER_TOPLEVEL_GENERATION
                   for t in n.targets):
                has_generation = True
        elif isinstance(n, ast.AnnAssign):
            if isinstance(n.target, ast.Name) and n.target.id == SERVER_TOPLEVEL_GENERATION:
                has_generation = True
    missing = [name for name, present in (
        (f"def {SERVER_TOPLEVEL_MAIN}", has_main),
        (f"{SERVER_TOPLEVEL_GENERATION} =", has_generation)) if not present]
    if missing:
        raise ValueError(
            "snapshot parsed but is not the server module — missing top-level "
            + " and ".join(missing)
            + ". A symlink target string, a truncated file, or the wrong blob "
              "all parse; this guard rejects them.")


def head_watch() -> bytes:
    """HEAD's watch.py bytes, link-resolved — the same bytes `just deploy`
    snapshots, so the comparison below is apples to apples once watch.py
    becomes a symlink."""
    return resolve_blob("HEAD", "watch.py", ROOT)


def listening_pid(port: int):
    """The pid actually bound to the port, or None. Never inferred from a file."""
    out = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if f":{port} " in line or line.rstrip().endswith(f":{port}"):
            m = re.search(r"pid=(\d+)", line)
            if m:
                return int(m.group(1))
    return None


def process_argv(pid: int):
    """Argv of `pid` from /proc, or None if the process is gone/unreadable.

    Null-separated, so a decoy shell whose command line merely *mentions* a
    path string is distinguishable from the process whose argv[1] *is* that
    path. This is the discrimination `pkill -f` does not have (#431).
    """
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if not raw:
        return None
    return [a for a in raw.decode("utf-8", "replace").split("\0") if a]


def argv_runs_snap(argv, snap: str) -> bool:
    """True when `argv` is a process whose script path is `snap`.

    Compares realpaths so a relative argv and an absolute snap still match.
    A command line that merely *mentions* the basename (a shell comment, a
    `pgrep` pattern, an agent's own check) does not match — that is the
    whole point of #431.
    """
    if not argv:
        return False
    try:
        snap_real = os.path.realpath(snap)
    except OSError:
        snap_real = os.path.abspath(snap)
    for arg in argv:
        try:
            if os.path.realpath(arg) == snap_real:
                return True
        except OSError:
            if arg == snap:
                return True
    return False


def stop_deployed(port: int, snap: str, *, signal_num: int = 15,
                  wait_s: float = 2.0) -> int:
    """Stop the process listening on `port` if and only if it is serving `snap`.

    Mechanism for #431: identify the target by the listening socket (exact —
    one pid owns a TCP listen), then verify via `/proc/<pid>/cmdline` that the
    process is actually running `snap` before signalling. Never `pkill -f`.

    Exit semantics for `just deploy`:
      0 — nothing listening, or our server was stopped.
      1 — something is listening that is not our snap (refuse to kill), or
          the kill failed. Fail loud: killing nothing and saying so beats
          killing the shell.

    Does not start anything; does not touch any other port.
    """
    pid = listening_pid(port)
    if pid is None:
        print(f"nothing listening on :{port} — nothing to stop")
        return 0
    if pid in (0, 1) or pid == os.getpid():
        print(f"refuse to signal pid {pid} on :{port} — not a deploy target",
              file=sys.stderr)
        return 1

    argv = process_argv(pid)
    if argv is None:
        print(f"pid {pid} on :{port} vanished before inspect — nothing to stop")
        return 0
    if not argv_runs_snap(argv, snap):
        # Something else owns the port. Do not kill it. Say why.
        preview = " ".join(argv)[:160]
        print(
            f"deploy stop refused: :{port} is owned by pid {pid} whose argv is "
            f"not {snap!r} (got: {preview!r}). Not signalling — a pattern match "
            f"would have killed the wrong process (#431).",
            file=sys.stderr)
        return 1

    try:
        os.kill(pid, signal_num)  # SIGTERM first; watch.py exits cleanly
    except ProcessLookupError:
        print(f"pid {pid} already gone — nothing to stop")
        return 0
    except PermissionError as exc:
        print(f"deploy stop failed: cannot signal pid {pid}: {exc}",
              file=sys.stderr)
        return 1

    # Wait for the listen to release so the restart bind does not race.
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if listening_pid(port) != pid:
            print(f"stopped pid {pid} on :{port} (was {snap})")
            return 0
        time.sleep(0.05)

    # Still listening — escalate once, then refuse to claim success.
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        print(f"stopped pid {pid} on :{port} (was {snap})")
        return 0
    except PermissionError as exc:
        print(f"deploy stop failed: pid {pid} ignored SIGTERM and SIGKILL "
              f"refused: {exc}", file=sys.stderr)
        return 1
    time.sleep(0.1)
    if listening_pid(port) == pid:
        print(f"deploy stop failed: pid {pid} still listening on :{port} "
              f"after SIGKILL", file=sys.stderr)
        return 1
    print(f"stopped pid {pid} on :{port} via SIGKILL (was {snap})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Report whether the deployed dashboard is current. Also "
                    "the single source of truth the deploy recipe uses to "
                    "resolve a (possibly symlinked) watch.py and to prove the "
                    "snapshot is the server (#425).")
    ap.add_argument("--json", action="store_true",
                    help="emit the state report as JSON")
    # #425 — the two verbs `just deploy` calls. They share the resolver/guard
    # with the HEAD comparison below, so the recipe and this report can never
    # disagree about what "HEAD's watch.py" means when watch.py is a symlink.
    actions = ap.add_mutually_exclusive_group()
    actions.add_argument(
        "--resolve-snapshot", metavar="REV", default=None,
        help="write watch.py's bytes at REV to stdout, following in-tree "
             "symlinks (the real module, not the link string). Used by "
             "`just deploy` to snapshot the server safely.")
    actions.add_argument(
        "--assert-server", metavar="FILE", default=None,
        help="prove FILE is the watch.py server module (parses AND defines "
             "`main` and `GENERATION`); exit 1 if not. Used by `just deploy` "
             "BEFORE it touches the live process, so a broken snapshot is "
             "rejected with the dashboard still up.")
    actions.add_argument(
        "--stop-deployed", action="store_true",
        help="stop the process listening on --port if and only if its argv "
             "is --snap (the #431 fix: never pkill -f a pattern that can "
             "match the caller). Exit 0 when nothing was listening or the "
             "server was stopped; exit 1 when the port owner is not our snap.")
    ap.add_argument(
        "--port", type=int, default=None,
        help="with --stop-deployed: the deploy port (from .dreamwork/watch-port).")
    ap.add_argument(
        "--snap", default=None,
        help="with --stop-deployed: absolute path of the deployed snapshot.")
    args = ap.parse_args()

    if args.resolve_snapshot is not None:
        # Binary-safe: the module is bytes, and a redirect in the recipe
        # captures them verbatim.
        sys.stdout.buffer.write(
            resolve_blob(args.resolve_snapshot, "watch.py", ROOT))
        return 0
    if args.assert_server is not None:
        try:
            assert_is_server(open(args.assert_server, "rb").read())
        except (ValueError, SyntaxError) as exc:
            print(f"snapshot guard failed: {exc}", file=sys.stderr)
            return 1
        return 0
    if args.stop_deployed:
        if args.port is None or not args.snap:
            print("--stop-deployed requires --port and --snap", file=sys.stderr)
            return 2
        return stop_deployed(args.port, args.snap)

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
