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


# --- sibling modules: the snapshot is one file, the server is not (#480) ----
#
# `just deploy` snapshots ONE file and boots it with `python3 <snap>`. Python
# puts the SNAPSHOT'S DIRECTORY on sys.path[0], not the repo — so watch.py's
# repo-local imports (`from user_events.sqlite import ...`, `from
# ledger_parse import ...` at HEAD) cannot resolve from the deployed dir, the
# new server ImportErrors on boot, and because the stop already happened his
# dashboard is dark while the curl check reports failure. `--assert-server`
# could never catch this: it proves the snapshot IS the server module, not
# that the server's imports resolve.
#
# The fix is to SHIP THE SIBLINGS: derive watch.py's repo-local imports from
# the resolved snapshot's own AST (never a hardcoded list, so the next
# sibling import is covered on arrival), copy each tracked-at-rev module and
# package beside the snapshot link-resolved, and then PROVE the staged
# snapshot imports in exactly the environment it will boot in — both before
# the live process is touched, so a snapshot that cannot boot is refused
# with the dashboard still up (the #425 contract, extended from "is the
# server" to "its imports resolve").


def dashboard_identity(head_src: bytes) -> list:
    """Every repo-relative path whose bytes decide what the browser sees.

    watch.py plus its declared `DATA_SIBLINGS`, at the revision `head_src`
    comes from. Before #397 this was watch.py alone and correctly so — the
    css and js lived in its string literals. After it, watch.py is 5,181
    lines of Python beside 10,500 lines of client, and the ORDINARY ui commit
    touches only the client.
    """
    return ["watch.py"] + data_sibling_paths(head_src)


def stale_identity_paths(deployed: bytes, head_src: bytes, dest,
                         repo=ROOT) -> list:
    """Which parts of the deployed dashboard do not match HEAD — [] if none.

    Comparing watch.py alone would answer `current` for a deploy whose
    stylesheet is a week old, because a client-only commit leaves watch.py
    byte-identical. That is a stale deploy reporting itself fresh, which is
    worse than not checking: #140's whole apparatus exists so a stale view
    ANNOUNCES itself.

    A sibling that is missing from `dest`, or unreadable at HEAD, counts as
    stale rather than as matching — this file's standing rule is that a
    comparison which could not run must never look like one that ran and
    agreed.
    """
    stale = [] if deployed == head_src else ["watch.py"]
    for rel in data_sibling_paths(head_src):
        try:
            with open(os.path.join(dest, rel), "rb") as f:
                have = f.read()
        except OSError:
            stale.append(rel)               # never shipped, or shipped away
            continue
        try:
            if have != resolve_blob("HEAD", rel, repo):
                stale.append(rel)
        except Exception:                                       # noqa: BLE001
            stale.append(rel)
    return stale


def import_roots(src: bytes) -> list:
    """Every absolute module root `src` imports, at ANY depth, sorted.

    Full-tree walk, not module scope: watch.py's `import lint` lives INSIDE
    `_posture_vocab()`, and the deployed snapshot still dies on it — at page
    build during boot — when lint.py is not beside it (measured by the #480
    scratch boot: top-level import clean, first page build ImportError). The
    lazy stdlib roots this picks up (e.g. `ctypes`) cost nothing: the git
    tree filter in `tracked_sibling_paths` discards whatever the repo does
    not track. Relative imports (`from . import x`) are meaningless in a
    flat snapshot and excluded.
    """
    tree = ast.parse(src)
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".", 1)[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".", 1)[0])
    return sorted(roots)


def data_sibling_paths(src) -> list:
    """Repo-relative data files a module declares it loads beside itself.

    Imports are not the whole sibling set: watch.py vendors morphdom and
    reads it with ``open()`` next to ``__file__`` (#505), a dependency the
    import walk cannot see. A module declares such files in a module-level
    ``DATA_SIBLINGS = (...)`` tuple of plain string literals; absent (or
    anything not a literal string tuple) means none. The caller tree-filters
    at the rev, so a stale entry is discarded, never shipped blind.
    """
    tree = ast.parse(src)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "DATA_SIBLINGS"
                   for t in node.targets):
            continue
        try:
            val = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return []
        if isinstance(val, (tuple, list)):
            return sorted(p for p in val if isinstance(p, str))
        return []
    return []


def tracked_sibling_paths(rev, roots, repo=ROOT) -> list:
    """Repo-relative paths at `rev` that provide the given import roots.

    A root is a SIBLING when `<root>.py` is a tracked blob or `<root>` is a
    tracked tree (a package — every file under it ships, recursively, so
    `__init__.py` and intra-package imports come along). A root with nothing
    tracked at `rev` is an environment module (stdlib, site-packages) and is
    left to the interpreter — this is also what keeps the derivation generic:
    the sibling set is whatever the git tree says, not a list maintained by
    hand.
    """
    paths = set()
    for root in roots:
        mode, _sha = _ls_tree_entry(repo, rev, f"{root}.py")
        if mode is not None:
            paths.add(f"{root}.py")
            continue
        mode, _sha = _ls_tree_entry(repo, rev, root)
        if mode is None or mode == SYMLINK_MODE:
            # absent: an environment module. A symlinked DIRECTORY root is
            # out of scope (none exists; resolve_blob resolves file links).
            continue
        res = subprocess.run(
            ["git", "ls-tree", "-r", "--format=%(path)", rev, "--", root],
            cwd=str(repo), capture_output=True, text=True, check=True)
        paths.update(p for p in res.stdout.splitlines() if p)
    return sorted(paths)


def sibling_closure(rev, repo=ROOT, seed="watch.py") -> list:
    """Every repo-local module watch.py at `rev` needs beside its snapshot,
    TRANSITIVELY, seed included.

    One level is not enough: lint.py (which watch.py imports lazily at page
    build) does a top-level `import watch`, so the closure ships watch.py
    itself under its real name — the deployed snapshot is
    `<target>-watch.py`, and `import watch` cannot resolve to it otherwise.
    Cycles (watch -> lint -> watch, and lint is exactly that) terminate on
    the seen set. Every file's imports are read through the #425 resolver,
    so a symlinked module's real bytes are what get walked.
    """
    paths = set()
    queue = [seed]
    while queue:
        rel = queue.pop()
        if rel in paths:
            continue
        paths.add(rel)
        src = resolve_blob(rev, rel, repo)
        queue.extend(tracked_sibling_paths(rev, import_roots(src), repo))
        # data siblings (#505): declared beside the module, not imported —
        # tree-filtered here so an untracked entry is discarded like an
        # environment module is.
        for p in data_sibling_paths(src):
            mode, _sha = _ls_tree_entry(repo, rev, p)
            if mode is not None:   # a symlinked data file ships resolved bytes
                paths.add(p)
    return sorted(paths)


def ship_siblings(rev, dest, repo=ROOT) -> list:
    """Write every sibling module of watch.py at `rev` into `dest`.

    The sibling set is the transitive closure of the RESOLVED snapshot's own
    imports (the same #425 resolver the recipe snapshots through), and every
    file's bytes come from `resolve_blob` too, so a symlinked sibling ships
    its target's real content. Each file is written to a temp name and
    renamed, so a process that re-imports mid-deploy never reads a partial
    module. Returns the repo-relative paths written. Stale siblings from
    earlier deploys are left in place: a module nothing imports is inert,
    and deleting files a RUNNING older snapshot might still re-import is the
    dangerous direction.
    """
    paths = sibling_closure(rev, repo)
    written = []
    for rel in paths:
        if rel == "client/style.css":
            continue
        data = resolve_blob(rev, rel, repo)
        out = os.path.join(dest, rel)
        parent = os.path.dirname(out)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = out + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, out)
        written.append(rel)
    return written


# SourceFileLoader explicitly, not spec_from_file_location: the recipe stages
# the snapshot as `$snap.tmp`, and spec_from_file_location keys the loader off
# the file SUFFIX — a `.tmp` name gets a None spec and the guard would refuse
# every deploy for a reason that has nothing to do with imports.
_IMPORT_HARNESS = (
    "import importlib.util, importlib.machinery, os, sys;"
    "p = os.path.abspath(sys.argv[1]);"
    "sys.path.insert(0, os.path.dirname(p));"
    "loader = importlib.machinery.SourceFileLoader('__snap__', p);"
    "spec = importlib.util.spec_from_loader('__snap__', loader);"
    "m = importlib.util.module_from_spec(spec);"
    "loader.exec_module(m)"
)


def assert_importable(path, timeout=30.0) -> None:
    """Prove the module at `path` IMPORTS with its own directory as
    sys.path[0] — exactly the environment `python3 <path>` boots in.

    Runs in a subprocess: importing in-process would mutate THIS interpreter
    (and a module that hangs would hang the deploy), so the proof is a child
    with a timeout. Module top level executes (that is the point — the
    sibling imports live there); `main()` does not run. Raises RuntimeError
    with the child's stderr tail on failure, TimeoutExpired on a hang.

    `-I` (isolated) is load-bearing, not hygiene: plain `python3 -c` puts
    the caller's CWD on sys.path and honours PYTHONPATH, and the recipe runs
    this guard FROM THE REPO ROOT — so without `-I` the guard resolves
    `user_events` from the repo it is about to deploy away from, passes, and
    the boot still fails. That was caught red-handed by
    test_ship_siblings_and_assert_importable_cli_against_real_head: the red
    half came back GREEN from an empty dest. `-I` makes the proof mean "the
    deploy dir alone provides the local imports".
    """
    try:
        res = subprocess.run(
            [sys.executable, "-I", "-c", _IMPORT_HARNESS, path],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise
    if res.returncode != 0:
        tail = "\n".join(res.stderr.splitlines()[-8:])
        raise RuntimeError(
            f"{path} does not import from its own directory — the deploy "
            f"would boot-fail the way #480 describes. Import error:\n{tail}")


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


# --- #508: the deployed server must BE the process the recipe spawned -------
#
# The defect `just deploy` had: it reported `deployed <rev> on :<port>` while
# the process serving that port was the OLD one. Mechanism (reproduced in a
# fixture, evidence in the commit message and the #508 brief):
#   1. The deployed server ran with `--dev`, which implies autoreload
#      (watch.py: `if args.autoreload or args.dev:` -> `_watch_source_and_restart`).
#   2. The recipe's `mv $snap.tmp $snap` OVERWRITES the snapshot the old server
#      is running, so the autoreload thread sees the mtime change and
#      `os.execv`s the OLD process IN PLACE — same pid, fresh GENERATION,
#      rebinding the port (the listening socket is close-on-exec, so it
#      flickers free during the exec then rebinds).
#   3. `--stop-deployed` can grade that flicker as "port free" and return
#      success while the old process rebinds; or the old process simply
#      survives the stop's timing window.
#   4. The replacement `nohup python3 "$snap" … &` then dies on bind
#      (EADDRINUSE), invisibly — nothing checks the spawned pid stayed up.
#   5. The readiness loop (`curl -sf … && echo "deployed …"`) passes against
#      whatever IS listening — the old, re-exec'd process. Success is printed
#      and it is a lie.
#
# The structural root cause: success was reported on LIVENESS (a curl 200),
# not IDENTITY (the listener is the process the recipe spawned). A curl 200
# grades whatever answers, and autoreload's in-place re-exec makes the old
# process's argv match the new snapshot, so even an argv check alone is not
# proof — the PID is the load-bearing signal. The fix below makes success
# TRUE BY CONSTRUCTION: `verify_deployed` returns 0 only when
# `listening_pid(port) == expect_pid` AND that pid's argv runs the snap.


def _pid_alive(pid):
    """True if `pid` is a running (non-zombie) process. `os.kill(pid, 0)`
    returns 0 for a zombie and for a not-yet-reaped child, so /proc/status is
    read directly — the verify step's 'new server died' branch would lie
    otherwise (a dead-but-unreaped new pid would read alive)."""
    if pid is None:
        return False
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("State:"):
                    return line.split()[1] != "Z"
    except (FileNotFoundError, PermissionError):
        return False
    return False


def wait_port_free(port, wait_s=10.0, settle=0.4):
    """Bounded wait for :port to have NO listener, confirmed to STAY none.

    Used between `--stop-deployed` and the new-server start. A single
    `listening_pid is None` sample is NOT proof: the autoreload `os.execv`
    flicker frees the close-on-exec socket for milliseconds before the new
    image rebinds, and `stop_deployed`'s 50ms poll can land in that window and
    return success. So a free sample must be confirmed by staying free for
    `settle` seconds. Returns 0 once it stays free, 1 if still held at the
    deadline — the recipe refuses to start the new server (which would die on
    bind, invisibly) and leaves the dashboard running.
    """
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if listening_pid(port) is None:
            quiet_to = time.time() + settle
            stayed_free = True
            while time.time() < quiet_to:
                if listening_pid(port) is not None:
                    stayed_free = False
                    break
                time.sleep(0.05)
            if stayed_free:
                print(f":{port} is free (held free for {settle}s)")
                return 0
        time.sleep(0.1)
    print(f"deploy refused: :{port} never freed within {wait_s}s — the old "
          f"process re-exec'd/respawned and is still holding it. The new "
          f"server was NOT started; his dashboard was left running.",
          file=sys.stderr)
    return 1


def verify_deployed(port, snap, expect_pid, *, wait_s=15.0):
    """Prove the listener on :port IS the process the recipe spawned.

    Returns 0 ONLY when `listening_pid(port) == expect_pid` AND that pid's
    argv runs `snap`. Returns 1 (fail loud) when:
      - `expect_pid` is no longer alive — the new server died (on bind because
        the old process still held the port, on boot, any reason). `nohup … &`
        hides this from the recipe; without this check a curl against the old
        process would print a false success.
      - a DIFFERENT pid holds :port — the old process never freed it / re-exec'd
        in place and rebound. Autoreload's in-place re-exec keeps the SAME pid
        as before AND its argv matches the new snap, so neither a curl 200 nor
        an argv check alone can tell it from the real new server; the PID is
        the load-bearing signal, and a foreign pid is a hard refuse.
      - nothing comes up on :port within `wait_s`.

    This is the #508 acceptance bar: success is identity, not liveness.
    """
    deadline = time.time() + wait_s
    while time.time() < deadline:
        holder = listening_pid(port)
        if holder is None:
            # Port not up yet — but if the spawned process already exited, the
            # bind failed (or it crashed on boot). Fail now rather than wait
            # the full window: nothing is coming.
            if not _pid_alive(expect_pid):
                print(f"deploy verify failed: the new server (pid {expect_pid}) "
                      f"exited without taking :{port} — it most likely died on "
                      f"bind because the old process still held the port, or "
                      f"crashed on boot. See serve.log. Refusing to report "
                      f"deployed.", file=sys.stderr)
                return 1
            time.sleep(0.1)
            continue
        if holder != expect_pid:
            argv = process_argv(holder)
            preview = " ".join(argv)[:160] if argv else "<unreadable>"
            print(f"deploy verify failed: :{port} is held by pid {holder}, NOT "
                  f"the new server (pid {expect_pid}). The old process never "
                  f"freed the port — an autoreload in-place re-exec keeps its "
                  f"argv identical to the new snap ({preview!r}), so a curl 200 "
                  f"against it is the false success #508 names. The PID is the "
                  f"proof and it is a foreign pid. Refusing to report deployed.",
                  file=sys.stderr)
            return 1
        # holder == expect_pid: the listener is the process we spawned.
        # Confirm its argv is the snap (defense in depth — a pid collision with
        # a foreign process is astronomically unlikely, but the argv check is
        # cheap and closes it).
        if not argv_runs_snap(process_argv(expect_pid), snap):
            print(f"deploy verify failed: :{port} is held by pid {expect_pid} "
                  f"but its argv does not run {snap!r}. Refusing to report "
                  f"deployed.", file=sys.stderr)
            return 1
        print(f"deploy verified: :{port} held by pid {expect_pid} running "
              f"{snap} — the process the recipe spawned (identity, not a "
              f"curl 200).")
        return 0
    print(f"deploy verify failed: nothing came up on :{port} within {wait_s}s "
          f"(new server pid {expect_pid} alive={_pid_alive(expect_pid)}). "
          f"Refusing to report deployed.", file=sys.stderr)
    return 1


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
    # #480 — the two verbs that extend the #425 guard chain from "the
    # snapshot IS the server" to "the server BOOTS from the deploy dir".
    # Both run BEFORE --stop-deployed in the recipe, so a snapshot whose
    # imports cannot resolve is refused with the dashboard still up.
    actions.add_argument(
        "--ship-siblings", metavar="REV", default=None,
        help="write every repo-local module watch.py imports at REV "
             "(derived transitively from the resolved snapshot's own "
             "imports, lazy ones included, never hardcoded) into --dest, "
             "link-resolved, so the deployed snapshot's directory provides "
             "them at boot.")
    actions.add_argument(
        "--assert-importable", metavar="FILE", default=None,
        help="prove FILE imports with its own directory as sys.path[0] — "
             "the exact environment `python3 FILE` boots in; exit 1 if its "
             "imports do not resolve. The boot guard #480 adds: a snapshot "
             "that cannot import is refused BEFORE the live server stops.")
    actions.add_argument(
        "--stop-deployed", action="store_true",
        help="stop the process listening on --port if and only if its argv "
             "is --snap (the #431 fix: never pkill -f a pattern that can "
             "match the caller). Exit 0 when nothing was listening or the "
             "server was stopped; exit 1 when the port owner is not our snap.")
    # #508 — the two verbs that make the deploy success line TRUE BY
    # CONSTRUCTION. Both run AFTER --stop-deployed (and the new server has
    # been started for --verify-deployed). A curl 200 is liveness; these are
    # identity, so a respawned/old process or a new server that died on bind
    # fails LOUDLY instead of printing a false 'deployed'.
    actions.add_argument(
        "--wait-port-free", action="store_true",
        help="with --port: bounded wait for the port to have NO listener and "
             "stay none (the autoreload os.execv flicker frees the socket "
             "briefly before a rebind — a single free sample is not proof). "
             "Exit 0 once it stays free, 1 if still held at the deadline. Run "
             "between --stop-deployed and the new-server start.")
    actions.add_argument(
        "--verify-deployed", action="store_true",
        help="with --port, --snap, --expect-pid: prove the listener on --port "
             "IS --expect-pid (the process the recipe just spawned) and its "
             "argv runs --snap. Exit 0 only on that identity match; 1 when a "
             "foreign/respawned pid holds the port or --expect-pid died (the "
             "new server died on bind). Replaces the curl-liveness readiness "
             "that printed 'deployed' against the old process.")
    ap.add_argument(
        "--dest", default=None,
        help="with --ship-siblings: directory the sibling modules are "
             "written into (default: the deployed dir, beside the snapshot).")
    ap.add_argument(
        "--port", type=int, default=None,
        help="with --stop-deployed/--wait-port-free/--verify-deployed: the "
             "deploy port (from .dreamwork/watch-port).")
    ap.add_argument(
        "--snap", default=None,
        help="with --stop-deployed/--verify-deployed: absolute path of the "
             "deployed snapshot.")
    ap.add_argument(
        "--expect-pid", type=int, default=None,
        help="with --verify-deployed: the pid of the new server the recipe "
             "just spawned ($! after the nohup start). The listener must BE "
             "this pid for success.")
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
    if args.ship_siblings is not None:
        dest = args.dest or DEPLOY_DIR
        os.makedirs(dest, exist_ok=True)
        try:
            written = ship_siblings(args.ship_siblings, dest, ROOT)
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"sibling staging failed: {exc}", file=sys.stderr)
            return 1
        for rel in written:
            print(f"shipped {rel}")
        if not written:
            print("watch.py has no repo-local sibling imports — nothing to ship")
        return 0
    if args.assert_importable is not None:
        try:
            assert_importable(args.assert_importable)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"import guard failed: {exc}", file=sys.stderr)
            return 1
        return 0
    if args.stop_deployed:
        if args.port is None or not args.snap:
            print("--stop-deployed requires --port and --snap", file=sys.stderr)
            return 2
        return stop_deployed(args.port, args.snap)
    if args.wait_port_free:
        if args.port is None:
            print("--wait-port-free requires --port", file=sys.stderr)
            return 2
        return wait_port_free(args.port)
    if args.verify_deployed:
        if args.port is None or not args.snap or args.expect_pid is None:
            print("--verify-deployed requires --port, --snap and --expect-pid",
                  file=sys.stderr)
            return 2
        return verify_deployed(args.port, args.snap, args.expect_pid)

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

    st["identity_paths"] = dashboard_identity(head)
    st["stale_paths"] = stale_identity_paths(deployed, head, DEPLOY_DIR)
    st["snapshot_matches_head"] = not st["stale_paths"]
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
            ["git", "log", "--oneline", "--", *st["identity_paths"]], cwd=ROOT,
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
            # Name the files. "the deployed file" was unambiguous when the
            # dashboard WAS one file; now the stale part is usually the
            # client, and "watch.py is fine" is the wrong thing to conclude.
            print(f"STALE SNAPSHOT — the deployed dashboard does NOT match "
                  f"HEAD ({st['head_rev']}): "
                  f"{', '.join(st['stale_paths'])}; serving :{port} at pid "
                  f"{st['pid']}. He is looking at older code. "
                  f"Run `just deploy`.")
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
