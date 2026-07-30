"""Tests for `dev/deploy_state.py` — the #425 symlink-safe deploy mechanism.

Why this file exists: `git show HEAD:watch.py` on a symlink returns the link's
TARGET PATH as content (git stores a symlink as a blob whose content is the
target). The old deploy recipe snapshotted those bytes and `ast.parse` accepted
them, because `deprecated/watch.py` parses as `deprecated / watch.py`. Both
halves are reproduced below against a REAL scratch git repo (no fakes), and the
fix — `resolve_blob` (follows the link) and `assert_is_server` (proves the
snapshot IS the server) — is tested in both directions.

Red-first discipline (this repo's rule): every test below calls the REAL
`resolve_blob` / `assert_is_server` against a REAL scratch git repo, so the
production lines are genuinely exercised — no scaffolding stands in front. The
production line whose removal fails each test is named in its docstring. Run
the named-line removal to see the red; a green run after removing one is a
finding about the test, not relief about the code.
"""
import ast
import os
import signal
import socket
import subprocess
import sys
import textwrap
import time as _time
from pathlib import Path

import pytest

import dev.deploy_state as ds

# A minimal module that satisfies `assert_is_server` — it defines both markers
# the real watch.py does (`GENERATION` and `def main`). The resolver is
# content-agnostic; the guard only cares about these two top-level names, so a
# minimal module exercises both without copying 500KB of watch.py.
REAL_MODULE = (
    "import time\n"
    "GENERATION = \"%.6f\" % time.time()\n"
    "def main(argv=None):\n"
    "    return 0\n"
    "if __name__ == \"__main__\":\n"
    "    main()\n"
).encode()


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True)


def _commit(repo):
    _git(repo, "add", "-A")
    # `-A` is safe here: this is a throwaway scratch repo built fresh in
    # tmp_path, not the shared tree, and there is no concurrent agent in it.
    _git(repo, "commit", "-qm", "scratch")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "proj"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    return r


def symlink_repo(repo, *, link="watch.py", target_path="deprecated/watch.py",
                 real_content=REAL_MODULE):
    """A scratch repo in which `link` is a symlink to `target_path`, whose real
    file holds `real_content`. Returns the bytes of the real module."""
    real = Path(target_path)
    (repo / real.parent).mkdir(parents=True, exist_ok=True)
    (repo / real).write_bytes(real_content)
    (repo / link).parent.mkdir(parents=True, exist_ok=True)
    (repo / link).symlink_to(target_path)
    _commit(repo)
    return real_content


# --- the two halves of the blocker, reproduced against a real scratch repo ---


def test_blocker_half1_git_stores_the_target_path_as_content(repo):
    """HALF 1 of the blocker: `git show HEAD:watch.py` on a symlink returns the
    link target string, not the module. If this stops being true the fix below
    is solving a problem that no longer exists, so it is asserted here as a
    precondition rather than assumed."""
    symlink_repo(repo)
    raw = subprocess.run(
        ["git", "-C", str(repo), "show", "HEAD:watch.py"],
        capture_output=True, check=True).stdout
    # the precondition this test depends on: the raw bytes ARE the link string
    # and are NOT the real module.
    assert raw == b"deprecated/watch.py"
    assert raw != REAL_MODULE
    assert subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "HEAD", "--", "watch.py"],
        capture_output=True, text=True, check=True).stdout.startswith("120000 ")


def test_blocker_half2_ast_parse_accepts_the_path_string(repo):
    """HALF 2 of the blocker: the old `ast.parse`-only guard WAVED the link
    string through, because `deprecated / watch.py` is a valid expression. If
    ast.parse ever rejects it, the old guard would have caught the bug and the
    whole #425 narrative changes — so the premise is asserted, not assumed.

    The reason the NEW guard still rejects it (and the old one did not): the
    link string parses to a single expression with NO server markers at module
    top level — no `def main`, no `GENERATION =`."""
    symlink_repo(repo)
    raw = subprocess.run(
        ["git", "-C", str(repo), "show", "HEAD:watch.py"],
        capture_output=True, check=True).stdout
    assert raw != REAL_MODULE                 # the fixture is a real symlink
    tree = ast.parse(raw)                     # MUST NOT raise — this is the bug
    assert not any(isinstance(n, ast.FunctionDef) and n.name == "main"
                  for n in tree.body)
    assert not any(isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "GENERATION"
                           for t in n.targets) for n in tree.body)


# --- item 1 + 3: resolve_blob follows the link ---


def test_resolve_blob_follows_symlink_to_real_module(repo):
    """`resolve_blob` returns the REAL module through a symlink, not the 19-byte
    link string.

    Production line whose removal fails this test: the symlink branch in
    `resolve_blob` — specifically the `if mode != SYMLINK_MODE:` conditional.
    Delete that branch (so the function always returns `cat-file blob` of the
    FIRST sha, which for a symlink is the link's own sha) and this test goes
    red, because the returned bytes are `b'deprecated/watch.py'`, not the
    module."""
    symlink_repo(repo)
    resolved = ds.resolve_blob("HEAD", "watch.py", repo)
    # precondition: the naive bytes differ from the module (else nothing to fix)
    naive = subprocess.run(
        ["git", "-C", str(repo), "show", "HEAD:watch.py"],
        capture_output=True, check=True).stdout
    assert naive != REAL_MODULE
    # the fix:
    assert resolved == REAL_MODULE
    assert resolved != naive


def test_resolve_blob_regular_file_is_unchanged(repo):
    """For a plain file (today's reality) `resolve_blob` equals `git show`. The
    fix must not change the non-symlink path.

    Production line: the same branch resolves to `cat-file blob <sha>` for mode
    != 120000; if that were broken the test fails against the regular file."""
    (repo / "watch.py").write_bytes(REAL_MODULE)
    _commit(repo)
    show = subprocess.run(
        ["git", "-C", str(repo), "show", "HEAD:watch.py"],
        capture_output=True, check=True).stdout
    assert ds.resolve_blob("HEAD", "watch.py", repo) == show == REAL_MODULE


def test_resolve_blob_follows_subdir_relative_target(repo):
    """A symlink's target is stored relative to the LINK's directory; the
    resolver normalises that, so a link inside a subdir with a `../` target
    resolves. (The #368 link is root-relative and resolves in one hop; this
    covers the general case so the resolver is not accidentally root-only.)

    Production line: `posixpath.normpath(posixpath.join(link_dir, target))` in
    `resolve_blob`. Replace it with the raw `target` and a subdir-relative link
    resolves against the wrong path (or none) and this fails."""
    (repo / "real.py").write_bytes(REAL_MODULE)
    (repo / "sub").mkdir()
    # link at sub/link.py -> ../real.py : the target is relative to the LINK's
    # directory (sub/), so it names the root-level real.py. A naive resolver
    # that treated the target as repo-root-relative would look for ../real.py
    # from the root and miss.
    (repo / "sub" / "link.py").symlink_to("../real.py")
    _commit(repo)
    assert ds.resolve_blob("HEAD", "sub/link.py", repo) == REAL_MODULE


def test_resolve_blob_rejects_untracked_path(repo):
    """An absent path raises (RuntimeError), rather than returning empty bytes
    that a downstream comparison would silently treat as 'no match' — the
    exact failure family `deployed.py` was written to prevent."""
    symlink_repo(repo)
    with pytest.raises(RuntimeError):
        ds.resolve_blob("HEAD", "does/not/exist.py", repo)


# --- item 2: assert_is_server — both directions, both markers required ---


def test_assert_is_server_accepts_the_real_module():
    """The guard accepts a module that defines both markers.

    Production line: none to remove for the accept path — this is the control
    for the negative tests below; it proves the guard is not over-widened to
    reject everything."""
    ds.assert_is_server(REAL_MODULE)           # must not raise


def test_assert_is_server_rejects_the_path_string():
    """The guard rejects the exact input that broke the old recipe: a bare link
    target string, which parses but defines nothing.

    Production line whose removal fails this test: the `if missing: raise
    ValueError(...)` block in `assert_is_server` (equivalently, the
    `has_main`/`has_generation` checks that populate `missing`). Remove the
    raise and the guard returns None on the path string — the #425 bug
    restored."""
    with pytest.raises(ValueError):
        ds.assert_is_server(b"deprecated/watch.py")


def test_assert_is_server_rejects_empty_and_garbage():
    """Empty bytes and bytes that are not Python at all are rejected (the
    SyntaxError path, distinct from the missing-marker path)."""
    for bad in [b"", b"\x00\x01\x02 not python ((((", b"def"]:
        with pytest.raises((ValueError, SyntaxError)):
            ds.assert_is_server(bad)


def test_assert_is_server_rejects_truncated_module():
    """A truncated real module is rejected. Truncation can break syntax OR drop
    a marker; both are caught (SyntaxError or ValueError)."""
    truncated = REAL_MODULE[: -len(b"main()\n") - 2]   # cut into the def body
    with pytest.raises((ValueError, SyntaxError)):
        ds.assert_is_server(truncated)


def test_assert_is_server_requires_both_markers():
    """A guard widened to a single marker would accept the wrong thing, so each
    marker is tested alone: a module with only `main` and a module with only
    `GENERATION` are BOTH rejected. This is the negative direction the brief
    names — a guard that 'accepts everything' has removed a check.

    Production line: the two membership checks `has_main` and `has_generation`.
    Drop either from the `missing` tuple and one of these two cases wrongly
    passes."""
    only_main = b"def main():\n    pass\n"
    only_generation = b"GENERATION = '1'\n"
    with pytest.raises(ValueError):
        ds.assert_is_server(only_main)
    with pytest.raises(ValueError):
        ds.assert_is_server(only_generation)


# --- item 3: deploy_state's HEAD comparison agrees with deploy through a link ---


def test_head_watch_resolves_the_link(monkeypatch, repo):
    """`head_watch()` uses the resolver, so deploy_state's HEAD bytes equal what
    `just deploy` snapshots (the resolved module), even through a symlink. This
    is the 'so the two agree' requirement: before #425, deploy_state compared
    the resolved snapshot against the raw link string and read STALE by
    construction.

    Production line: `head_watch` returns `resolve_blob("HEAD", "watch.py",
    ROOT)`. Revert it to `git show HEAD:watch.py` and this test fails — the
    HEAD bytes become the 19-byte link string and no longer equal REAL_MODULE."""
    symlink_repo(repo)
    monkeypatch.setattr(ds, "ROOT", str(repo))
    assert ds.head_watch() == REAL_MODULE


def test_resolve_snapshot_and_assert_server_cli_wire(monkeypatch, tmp_path, repo):
    """The two CLI verbs `just deploy` calls are thin, correct wrappers:
    `--resolve-snapshot` emits `resolve_blob` bytes to stdout, and
    `--assert-server` exits 0 on the real module and 1 on a path string. Runs
    against a real symlink fixture by pointing ROOT at it via the environment
    is not possible (ROOT is computed from __file__), so the verbs are driven
    as a subprocess against THIS repo (non-symlink, no port, no server) while
    the symlink logic itself is covered by the resolve_blob tests above.

    Production line: the `if args.resolve_snapshot is not None` /
    `if args.assert_server is not None` branches in main()."""
    root = Path(__file__).resolve().parent
    real = subprocess.run(
        [sys.executable, "dev/deploy_state.py", "--resolve-snapshot", "HEAD"],
        cwd=str(root), capture_output=True, check=True).stdout
    show = subprocess.run(
        ["git", "-C", str(root), "show", "HEAD:watch.py"],
        capture_output=True, check=True).stdout
    assert real == show                          # today this repo has no symlink

    snap = tmp_path / "snap.py"
    snap.write_bytes(real)
    r0 = subprocess.run(
        [sys.executable, "dev/deploy_state.py", "--assert-server", str(snap)],
        cwd=str(root), capture_output=True)
    assert r0.returncode == 0, r0.stderr

    bad = tmp_path / "bad.py"
    bad.write_bytes(b"deprecated/watch.py")
    r1 = subprocess.run(
        [sys.executable, "dev/deploy_state.py", "--assert-server", str(bad)],
        cwd=str(root), capture_output=True)
    assert r1.returncode == 1
    assert b"not the server module" in r1.stderr


# --- #431: stop the process that owns the deploy port, never pkill -f -------
#
# The defect: `just deploy` did `pkill -f "$(basename "$snap")"`, and pkill -f
# matches ANY process whose command line merely *mentions* the pattern — the
# deploy shell, a pgrep check, a comment. Four times on 2026-07-28, including
# a coordinator shell with exit 144.
#
# The production line whose removal fails the fix tests is
# `stop_deployed` in dev/deploy_state.py (and the justfile call to
# `--stop-deployed`). The production line whose REINSTATEMENT fails the
# justfile pin is `pkill -f "$(basename "$snap")"` in the deploy recipe.
#
# Unique pattern per run so these tests can never touch the live dashboard
# on :35110 (basename `ud-dreamwork-watch.py`).


def _unique_snap_name():
    """A basename no live process on this machine will match by accident."""
    return f"deploykill431-{os.getpid()}-{os.urandom(3).hex()}-watch.py"


def _start_decoy(pattern: str):
    """A process whose command line merely MENTIONS `pattern`, but is not
    running a file by that name. The #431 victim class (coordinator shell,
    pgrep check, a comment — anything pkill -f would hit).

    `python3 -c '… # pattern'` keeps the pattern in argv for the process's
    whole life. Measured dead ends that look simpler and are not:
    - bash -c with a comment then sleep: bash optimises the final sleep into
      an exec and the pattern vanishes from cmdline.
    - sleep with a trailing arg: GNU sleep sums its args as intervals and
      rejects a non-number with exit 1.
    """
    return subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep(120)  # {pattern}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)


def _alive(pid: int) -> bool:
    """True if `pid` is a running (non-zombie) process.

    A zombie still answers `os.kill(pid, 0)` and still has a /proc entry, so
    kill-success alone is not enough — after SIGTERM a reaped-but-unwaited
    child looks "alive" forever and the red-proof assertion would lie.
    """
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("State:"):
                    # e.g. "State:\tZ (zombie)" — not running.
                    state = line.split()[1]
                    return state != "Z"
    except FileNotFoundError:
        return False
    except PermissionError:
        return True
    return False


def _pgrep_f(pattern: str):
    """Pids whose command line matches `pattern` (same instrument as the bug)."""
    r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
    if r.returncode not in (0, 1):
        r.check_returncode()
    return [int(x) for x in r.stdout.split() if x]


def test_pkill_f_kills_decoy_that_merely_mentions_pattern():
    """RED proof of the #431 defect: `pkill -f <pattern>` kills a decoy whose
    command line only *mentions* the pattern in a comment.

    This test documents the bug and does not call production code. It is the
    red half the brief requires: reinstate the old form and watch the
    self-match. Precondition asserted: the decoy is alive AND pgrep -f finds
    it (matched the pattern) before pkill runs — a check with no decoy
    passes forever.
    """
    pattern = _unique_snap_name()
    decoy = _start_decoy(pattern)
    try:
        # Precondition the check depends on: decoy alive AND pattern-matched.
        assert _alive(decoy.pid), "decoy failed to start"
        matched = _pgrep_f(pattern)
        assert decoy.pid in matched, (
            f"precondition failed: decoy {decoy.pid} is alive but pgrep -f "
            f"{pattern!r} did not match it (got {matched}) — without a real "
            f"match this test cannot prove pkill -f over-kills")
        # The old production line:
        subprocess.run(["pkill", "-f", pattern], check=False)
        # Reap so a zombie does not look alive to /proc.
        try:
            decoy.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        assert not _alive(decoy.pid), (
            f"pkill -f {pattern!r} did not kill decoy {decoy.pid} — the "
            f"documented defect did not reproduce; the rest of the suite "
            f"cannot claim to fix it")
        assert decoy.returncode is not None and decoy.returncode != 0
    finally:
        try:
            os.kill(decoy.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        decoy.wait(timeout=2)


def test_stop_deployed_spares_decoy_that_merely_mentions_pattern(tmp_path):
    """The fix: `stop_deployed` does not kill a process that merely mentions
    the snap basename. Only the owner of `--port` whose argv is `--snap`.

    Production line whose removal fails this test: `stop_deployed`'s
    `argv_runs_snap` gate (or replacing the whole function with
    `pkill -f basename(snap)`). Precondition: decoy alive and pattern-matched
    *before* the stop step.
    """
    pattern = _unique_snap_name()
    snap = tmp_path / pattern
    snap.write_text("# not a real server\n")
    decoy = _start_decoy(pattern)
    try:
        assert _alive(decoy.pid), "decoy failed to start"
        matched = _pgrep_f(pattern)
        assert decoy.pid in matched, (
            f"precondition failed: decoy {decoy.pid} alive but not matched by "
            f"pgrep -f {pattern!r} (got {matched})")
        # No server on this port — stop should be a quiet no-op, exit 0.
        # Pick an ephemeral free port so we never touch :35110 or guard ranges.
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        rc = ds.stop_deployed(free_port, str(snap))
        assert rc == 0
        assert _alive(decoy.pid), (
            f"stop_deployed killed decoy {decoy.pid} whose cmdline only "
            f"mentioned {pattern!r} — the #431 fix is not in place")
    finally:
        try:
            os.kill(decoy.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        decoy.wait(timeout=2)


def test_stop_deployed_kills_only_the_listener_running_the_snap(tmp_path):
    """Positive half: a process listening on an ephemeral port whose argv is
    the snap path IS stopped; a sibling decoy that merely mentions the
    basename is not.

    Production line: `stop_deployed` → `listening_pid` + `argv_runs_snap` +
    `os.kill`. Replacing any of those with `pkill -f` makes the decoy die
    (caught by the assertion below) or fails to free the port.
    """
    pattern = _unique_snap_name()
    snap = tmp_path / pattern
    # Minimal listener: bind the given port and sleep. argv[0]=python, argv[1]=snap.
    snap.write_text(textwrap.dedent("""\
        import socket, sys, time
        port = int(sys.argv[1])
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.listen(1)
        while True:
            time.sleep(1)
    """))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    # Guard ranges are 39880-39899 / 39880-39889; ephemeral is fine and
    # must never be :35110 (the live human dashboard — never touch it).
    assert port != 35110
    assert not (39880 <= port <= 39899)

    server = subprocess.Popen(
        [sys.executable, str(snap), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    decoy = _start_decoy(pattern)
    try:
        # Wait until the port is actually held by our server.
        deadline = _time.time() + 3
        owner = None
        while _time.time() < deadline:
            owner = ds.listening_pid(port)
            if owner == server.pid:
                break
            _time.sleep(0.05)
        assert owner == server.pid, (
            f"precondition failed: expected server pid {server.pid} on "
            f":{port}, got {owner} — stop would have nothing real to kill")
        assert _alive(decoy.pid)
        matched = _pgrep_f(pattern)
        assert decoy.pid in matched, (
            f"precondition failed: decoy {decoy.pid} not matched by "
            f"pgrep -f before stop (got {matched})")
        assert ds.argv_runs_snap(ds.process_argv(server.pid), str(snap)), (
            "server must be identifiable as running the snap before stop")

        rc = ds.stop_deployed(port, str(snap), wait_s=3.0)
        assert rc == 0, "stop_deployed should succeed on our own listener"
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        assert not _alive(server.pid), f"server {server.pid} still alive"
        assert ds.listening_pid(port) is None
        assert _alive(decoy.pid), (
            f"decoy {decoy.pid} was killed — stop was not pid-exact")
    finally:
        for p in (server, decoy):
            try:
                os.kill(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait(timeout=2)


def test_stop_deployed_refuses_foreign_listener(tmp_path):
    """Fail loud: a listener on the port whose argv is NOT the snap is not
    signalled. Killing nothing and saying so beats killing the shell.

    Production line: the `if not argv_runs_snap` refuse branch in
    `stop_deployed`. Delete it (fall through to kill) and this fails.
    """
    pattern = _unique_snap_name()
    our_snap = tmp_path / pattern
    our_snap.write_text("# unused\n")
    foreign = tmp_path / f"foreign-{os.getpid()}.py"
    foreign.write_text(textwrap.dedent("""\
        import socket, sys, time
        port = int(sys.argv[1])
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.listen(1)
        while True:
            time.sleep(1)
    """))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert port != 35110
    proc = subprocess.Popen(
        [sys.executable, str(foreign), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    try:
        deadline = _time.time() + 3
        while _time.time() < deadline and ds.listening_pid(port) != proc.pid:
            _time.sleep(0.05)
        assert ds.listening_pid(port) == proc.pid
        rc = ds.stop_deployed(port, str(our_snap))
        assert rc == 1, "must refuse a foreign listener"
        assert _alive(proc.pid), "foreign listener must not be signalled"
    finally:
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=2)


def test_justfile_deploy_does_not_use_pkill_f():
    """Pin the production recipe: `just deploy` must not *run* `pkill -f`.

    Production line: the deploy recipe body in justfile. Reinstate
    `pkill -f "$(basename "$snap")"` as a command and this goes red — that
    is the named-line red-run for the wiring half of #431. Comments that
    *mention* the forbidden form are fine (and expected).
    """
    import re
    root = Path(__file__).resolve().parent
    text = (root / "justfile").read_text()
    # Isolate the deploy recipe (from `deploy rev=` to the next top-level recipe).
    start = text.index("\ndeploy rev=")
    rest = text[start + 1:]
    end = len(rest)
    for i, line in enumerate(rest.splitlines()[1:], start=1):
        if line and not line[0].isspace() and not line.startswith("#") and ":" in line:
            offset = 0
            for j, l in enumerate(rest.splitlines()):
                if j == i:
                    end = offset
                    break
                offset += len(l) + 1
            break
    recipe = rest[:end]
    # Only non-comment command lines count — a doc comment saying "Never
    # `pkill -f`" is not the defect.
    cmd_lines = []
    for line in recipe.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        cmd_lines.append(stripped)
    joined = "\n".join(cmd_lines)
    assert not re.search(r"\bpkill\s+-f\b", joined), (
        "deploy recipe still runs pkill -f — that is the #431 defect:\n"
        + joined)
    assert "--stop-deployed" in joined
    assert "dev/deploy_state.py" in joined


def test_stop_deployed_cli_wire(tmp_path):
    """CLI verb the justfile calls: --stop-deployed --port N --snap PATH.

    Production line: the `if args.stop_deployed` branch in main().
    """
    root = Path(__file__).resolve().parent
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    snap = tmp_path / _unique_snap_name()
    snap.write_text("# none\n")
    r = subprocess.run(
        [sys.executable, "dev/deploy_state.py",
         "--stop-deployed", "--port", str(port), "--snap", str(snap)],
        cwd=str(root), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "nothing to stop" in r.stdout


# --- #480: the snapshot is one file, but the server imports sibling modules --
#
# The defect: `just deploy` snapshots ONE file and boots it with
# `python3 <snap>`. Python puts the SNAPSHOT'S DIRECTORY on sys.path[0], not
# the repo, so watch.py's repo-local imports (`user_events`, `ledger_parse`
# at HEAD) cannot resolve from the deployed dir: --assert-server passes (the
# snapshot IS the server), the old server stops, the new one ImportErrors on
# boot, and his dashboard is dark. The fix ships every tracked-at-rev sibling
# beside the snapshot and proves the staged snapshot IMPORTS from that
# directory — both before the live process is touched.

SIBLING_SERVER = (
    "import time\n"
    "from pkg.core import answer\n"
    "import helper\n"
    "GENERATION = \"%.6f\" % time.time()\n"
    "def main(argv=None):\n"
    "    return 0\n"
    "if __name__ == \"__main__\":\n"
    "    main()\n"
).encode()


def sibling_repo(repo):
    """A scratch repo whose watch.py imports a package AND a flat module."""
    (repo / "watch.py").write_bytes(SIBLING_SERVER)
    (repo / "helper.py").write_text("VALUE = 7\n")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "core.py").write_text("answer = 42\n")
    _commit(repo)
    return repo


def test_import_roots_full_tree_absolute_only():
    """`import_roots` derives the sibling candidates from the module's own
    AST: absolute imports at ANY depth. Function-scope imports MUST be
    included — watch.py's `import lint` lives inside `_posture_vocab()` and
    the deployed snapshot died on it at page build during the #480 scratch
    boot (top-level import was clean). Lazy stdlib roots (ctypes) are
    harmless: the git-tree filter drops what the repo does not track.

    Production line whose removal fails this test: `ast.walk(tree)` in
    `import_roots` — revert to `tree.body` and `lazy_mod` vanishes."""
    src = (
        b"import os\n"
        b"import ledger_parse\n"
        b"from user_events.sqlite import Envelope\n"
        b"def f():\n"
        b"    import lazy_mod\n"          # lazy, but repo-local => must ship
        b"if True:\n"
        b"    pass\n"
    )
    roots = ds.import_roots(src)
    assert roots == ["lazy_mod", "ledger_parse", "os", "user_events"]


def test_tracked_sibling_paths_maps_roots_via_git_tree(repo):
    """The sibling set is whatever the git tree at REV says: a tracked
    `<root>.py` ships as one file, a tracked `<root>/` ships recursively,
    and an untracked root (stdlib, site-packages) is left to the interpreter.

    Production line: the two `_ls_tree_entry` lookups and the recursive
    `ls-tree -r` in `tracked_sibling_paths`. Drop the `<root>.py` probe and
    `helper` is missed; drop the recursion and `pkg/core.py` is missed."""
    sibling_repo(repo)
    paths = ds.tracked_sibling_paths(
        "HEAD", ["helper", "pkg", "os", "not_tracked_anywhere"], repo)
    # precondition the check depends on, derived at runtime: the roots cover
    # one of each class — flat module, package, stdlib, absent.
    assert paths == ["helper.py", "pkg/__init__.py", "pkg/core.py"]


def test_ship_siblings_writes_link_resolved_bytes(repo):
    """Shipped siblings are the rev's REAL bytes, through the #425 resolver:
    a sibling that is itself a symlink ships its target's content, not the
    link string.

    Production line: the `resolve_blob(rev, rel, repo)` call in
    `ship_siblings`. Replace it with `git show rev:rel` and the symlinked
    sibling ships its 19-byte link string — caught below."""
    sibling_repo(repo)
    real = repo / "real" / "helper_impl.py"
    real.parent.mkdir()
    real.write_text("VALUE = 99\n")
    (repo / "helper.py").unlink()
    (repo / "helper.py").symlink_to("real/helper_impl.py")
    _commit(repo)
    # precondition: the fixture really is a symlink in git.
    assert subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "HEAD", "--", "helper.py"],
        capture_output=True, text=True, check=True).stdout.startswith("120000 ")

    dest = repo / "dest"
    dest.mkdir()
    written = ds.ship_siblings("HEAD", str(dest), repo)
    # the closure includes the seed: lint.py's `import watch` taught us the
    # snapshot's own module must ship under its real name too.
    assert set(written) == {"watch.py", "helper.py",
                            "pkg/__init__.py", "pkg/core.py"}
    assert (dest / "helper.py").read_text() == "VALUE = 99\n"
    assert not (dest / "helper.py").is_symlink()
    assert (dest / "pkg" / "core.py").read_text() == "answer = 42\n"
    assert (dest / "pkg" / "__init__.py").exists()


def test_sibling_closure_is_transitive_and_terminates_cycles(repo):
    """The closure follows siblings-of-siblings and survives cycles: watch.py
    imports lint lazily, lint.py does a top-level `import watch` — a cycle
    the derivation must not hang on, and the reason watch.py itself ships.

    Production line: the queue loop in `sibling_closure`. Ship one level
    only and `deep_mod.py` is missing; drop the seen set and this test hangs
    instead of passing."""
    sibling_repo(repo)
    (repo / "helper.py").write_text("import deep_mod\nVALUE = 7\n")
    (repo / "deep_mod.py").write_text("import helper\n")  # a cycle, like lint<->watch
    _commit(repo)
    # precondition: the fixture really is cyclic and transitive.
    assert "deep_mod" in ds.import_roots((repo / "helper.py").read_bytes())
    assert "helper" in ds.import_roots((repo / "deep_mod.py").read_bytes())
    paths = ds.sibling_closure("HEAD", repo)
    assert paths == ["deep_mod.py", "helper.py", "pkg/__init__.py",
                     "pkg/core.py", "watch.py"]


def test_ship_siblings_makes_snapshot_importable_red_then_green(repo, tmp_path):
    """The whole mechanism in both directions against a real scratch repo:
    WITHOUT shipped siblings the resolved snapshot does NOT import from the
    deploy dir (the #480 defect, reproduced), WITH them it does.

    Production line whose removal fails the green half: `ship_siblings`
    itself (the justfile call is pinned separately). The red half is the
    precondition, derived at runtime — a green red-run here would mean the
    check cannot see the defect it names."""
    sibling_repo(repo)
    dest = tmp_path / "deployed"
    dest.mkdir()
    snap = dest / "snap-watch.py"
    snap.write_bytes(ds.resolve_blob("HEAD", "watch.py", repo))

    # RED half (precondition): the snapshot IS the server yet cannot boot.
    ds.assert_is_server(snap.read_bytes())          # the old guard passes...
    with pytest.raises(RuntimeError, match="does not import"):
        ds.assert_importable(str(snap))             # ...and the boot fails.

    # the fix:
    ds.ship_siblings("HEAD", str(dest), repo)
    ds.assert_importable(str(snap))                 # must not raise


def test_assert_importable_runs_toplevel_but_never_main(tmp_path):
    """The import proof executes module top level (where the sibling imports
    live) but NOT main() — a server must not boot inside the guard.

    Production line: `_IMPORT_HARNESS` uses spec_from_file_location +
    exec_module with __name__ != '__main__'. Run the file instead and both
    marker assertions below fail; skip exec_module and the top-level one
    fails."""
    marker_top = tmp_path / "toplevel-ran"
    marker_main = tmp_path / "main-ran"
    mod = tmp_path / "mod.py"
    mod.write_text(
        "import pathlib\n"
        f"pathlib.Path({str(marker_top)!r}).write_text('x')\n"
        "if __name__ == '__main__':\n"
        f"    pathlib.Path({str(marker_main)!r}).write_text('x')\n"
    )
    ds.assert_importable(str(mod))
    assert marker_top.exists(), "top level did not execute — the guard is hollow"
    assert not marker_main.exists(), "assert_importable ran main() — it must not"


def test_assert_importable_accepts_a_tmp_suffixed_snapshot(tmp_path):
    """The recipe stages the snapshot as `$snap.tmp` and guards THAT name.
    spec_from_file_location keys the loader off the suffix and returns None
    for `.tmp` — a guard built on it refuses every deploy, good snapshot or
    not (measured: 'NoneType' object has no attribute loader').

    Production line: `SourceFileLoader` + `spec_from_loader` in
    `_IMPORT_HARNESS`. Revert to spec_from_file_location and this fails."""
    mod = tmp_path / "snap-watch.py.tmp"          # exactly the recipe's name
    mod.write_text("VALUE = 1\n")
    ds.assert_importable(str(mod))                 # must not raise


def test_assert_importable_times_out_a_hanging_module(tmp_path):
    """A module whose import hangs must fail the guard, not hang the deploy.

    Production line: `timeout=timeout` on the subprocess run in
    `assert_importable`. Remove it and this test hangs instead of failing."""
    mod = tmp_path / "hang.py"
    mod.write_text("import time\ntime.sleep(60)\n")
    with pytest.raises(subprocess.TimeoutExpired):
        ds.assert_importable(str(mod), timeout=1.0)


def test_ship_siblings_and_assert_importable_cli_against_real_head(tmp_path):
    """End-to-end against the REAL watch.py at HEAD of THIS repo: staging the
    snapshot alone fails the import guard (the live defect), shipping the
    siblings fixes it, and the shipped set is derived — not hardcoded.

    This is the named red-run for the defect at HEAD: the first
    --assert-importable MUST exit 1. If it ever exits 0 with an empty dest,
    the defect this task fixes no longer reproduces and the fixture is lying.
    """
    root = Path(__file__).resolve().parent
    dest = tmp_path / "deployed"
    dest.mkdir()
    snap = dest / "snap-watch.py.tmp"   # the recipe guards the STAGED name
    snap.write_bytes(subprocess.run(
        [sys.executable, "dev/deploy_state.py", "--resolve-snapshot", "HEAD"],
        cwd=str(root), capture_output=True, check=True).stdout)

    # RED at real HEAD: the snapshot is the server but cannot boot alone.
    r_bad = subprocess.run(
        [sys.executable, "dev/deploy_state.py", "--assert-importable", str(snap)],
        cwd=str(root), capture_output=True, text=True)
    assert r_bad.returncode == 1, (
        f"the #480 defect did not reproduce: a lone HEAD snapshot imported "
        f"from an empty dir (stdout={r_bad.stdout!r} stderr={r_bad.stderr!r})")
    assert "import guard failed" in r_bad.stderr

    # the fix, via the CLI the recipe calls:
    r_ship = subprocess.run(
        [sys.executable, "dev/deploy_state.py", "--ship-siblings", "HEAD",
         "--dest", str(dest)],
        cwd=str(root), capture_output=True, text=True)
    assert r_ship.returncode == 0, r_ship.stderr

    shipped = set()
    for line in r_ship.stdout.splitlines():
        if line.startswith("shipped "):
            shipped.add(line[len("shipped "):])
    # the known-at-HEAD closure, asserted explicitly (a list DERIVED from
    # the production function would agree with it by construction and prove
    # nothing). If watch.py's imports change, update this list — the boot
    # proof below is what makes a stale list fail loud, not silently pass.
    # The vendor pair arrives via DATA_SIBLINGS (#505), not the import walk.
    for rel in ("ledger_parse.py", "lint.py", "watch.py",
                "user_events/__init__.py", "user_events/sqlite.py",
                "vendor/morphdom.min.js", "vendor/LICENSE.morphdom"):
        assert rel in shipped, f"{rel} missing from {sorted(shipped)}"
    for rel in shipped:
        assert (dest / rel).exists(), f"sibling {rel} was not shipped"
    # `import watch` (from lint.py) must resolve to the SAME bytes deployed.
    assert (dest / "watch.py").read_bytes() == ds.resolve_blob(
        "HEAD", "watch.py", ds.ROOT)

    # GREEN: the staged snapshot now boots its imports from the deploy dir.
    r_ok = subprocess.run(
        [sys.executable, "dev/deploy_state.py", "--assert-importable", str(snap)],
        cwd=str(root), capture_output=True, text=True)
    assert r_ok.returncode == 0, r_ok.stderr

    # GREEN, verified not asserted: BOOT the staged snapshot exactly as the
    # recipe does and GET the page. Import-clean alone proved insufficient
    # once already — `import lint` fires at page build, not at import — so
    # the artifact is verified, not the intention.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert port != 35110                    # the live dashboard: never
    assert not (39880 <= port <= 39899)     # the browser-guard ranges
    staged = dest / "staged-watch.py"
    staged.write_bytes(snap.read_bytes())
    server = subprocess.Popen(
        [sys.executable, str(staged), "--target", str(root),
         "--port", str(port), "--dev"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    try:
        import urllib.request
        code = None
        deadline = _time.time() + 15
        while _time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/", timeout=2) as resp:
                    code = resp.getcode()
                    break
            except Exception:                            # noqa: BLE001
                if server.poll() is not None:
                    break
                _time.sleep(0.25)
        assert code == 200, (
            f"staged snapshot did not serve a 200 (got {code}, "
            f"poll={server.poll()}) — the deploy would leave his dashboard "
            f"dark; this is the check that caught the lazy `import lint`")
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/mtime", timeout=2) as resp:
            assert float(resp.read().decode().split()[0]) > 0
    finally:
        try:
            os.kill(server.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        server.wait(timeout=3)
    assert ds.listening_pid(port) is None


def test_justfile_deploy_ships_siblings_and_guards_imports_before_stopping():
    """Pin the recipe wiring: `just deploy` must ship the siblings and prove
    the snapshot importable BEFORE it stops the live server — the #425
    refuse-with-dashboard-up contract, extended to the boot failure #480
    names. Order is the assertion: a guard after --stop-deployed guards
    nothing.

    Production line: the deploy recipe body in justfile. Delete the
    --ship-siblings or --assert-importable lines (or move them after
    --stop-deployed) and this goes red."""
    root = Path(__file__).resolve().parent
    text = (root / "justfile").read_text()
    start = text.index("\ndeploy rev=")
    rest = text[start + 1:]
    end = len(rest)
    for i, line in enumerate(rest.splitlines()[1:], start=1):
        if line and not line[0].isspace() and not line.startswith("#") and ":" in line:
            offset = 0
            for j, l in enumerate(rest.splitlines()):
                if j == i:
                    end = offset
                    break
                offset += len(l) + 1
            break
    recipe = rest[:end]
    cmd_lines = []
    for line in recipe.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        cmd_lines.append(stripped)
    joined = "\n".join(cmd_lines)
    assert "--ship-siblings" in joined, (
        "deploy recipe does not ship watch.py's sibling modules beside the "
        "snapshot — the #480 defect: the snapshot is one file and cannot "
        "import user_events/ or ledger_parse.py from the deploy dir")
    assert "--assert-importable" in joined, (
        "deploy recipe does not prove the snapshot imports from the deploy "
        "dir before touching the live server")
    i_ship = joined.index("--ship-siblings")
    i_import = joined.index("--assert-importable")
    i_stop = joined.index("--stop-deployed")
    assert i_ship < i_stop and i_import < i_stop, (
        "the sibling/import guards must run BEFORE --stop-deployed — a "
        "guard after the stop leaves his dashboard dark on a bad snapshot")


# --- #508: deploy success must be IDENTITY, not a curl-200 liveness ----------
#
# The defect: `just deploy` printed `deployed <rev> on :<port>` while the port
# was served by the OLD process. Mechanism (reproduced in a fixture, evidence
# in the #508 commit): the deployed server ran with --dev (=> autoreload); the
# recipe's `mv` overwrote the snapshot it watches, so autoreload os.execv'd the
# OLD process IN PLACE (same pid, port flickered free via close-on-exec then
# rebind); stop_deployed could grade that flicker as 'free' and succeed while
# the old process rebind; the new server then died on bind (invisible under
# `nohup … &`); and the curl-liveness readiness printed 'deployed' against the
# old process. The fix: `verify_deployed` returns 0 only when the listener IS
# the pid the recipe spawned — identity, not liveness. Autoreload's in-place
# re-exec keeps the old argv identical to the new snap, so the PID is the
# load-bearing signal (proven by test_verify_deployed_pid_check_load_bearing).
#
# Production line whose removal fails the fix tests: `verify_deployed` (and the
# justfile's `--verify-deployed --expect-pid` call). Every fixture binds a
# PRIVATE ephemeral port (127.0.0.1:0), never :35110 or the 39880-39899 guard
# range, and never signals any process outside its own fixture.

LISTENER_SRC = textwrap.dedent("""\
    import socket, sys, time
    port = int(sys.argv[1])
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen(8)
    while True:
        time.sleep(1)
""")


def _ephemeral_port():
    """A free port on 127.0.0.1, never the live dashboard or a guard range."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
    assert p != 35110 and not (39880 <= p <= 39899)
    return p


def _wait_listening(port, pid, timeout=15.0):
    """Block until `pid` owns the listen on `port`, or timeout. Precondition
    helper: the tests below assert the fixture server really bound before they
    exercise the production line, so a green run cannot pass over a server that
    never started. The timeout is generous (15s) because this host is a shared
    workstation whose load sits near 30 on 16 cores — a fixture listener's bind
    is instant once the interpreter starts, but interpreter STARTUP under load
    is the slow part, and a 5s timeout flakes on it."""
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        if ds.listening_pid(port) == pid:
            return True
        _time.sleep(0.05)
    return False


def test_deploy_cycle_verify_identity_after_stop_and_start(tmp_path):
    """The full cycle the recipe runs: stop the old listener, start a new one,
    and verify the listener AFTER is the process the recipe spawned (a DIFFERENT
    pid from before) whose argv is the new snapshot. This is the brief's first
    acceptance test.

    Production line whose removal fails this test: `verify_deployed`'s success
    return (the `holder == expect_pid` + argv check + `return 0`). Make
    verify_deployed return 1 unconditionally and this goes red.
    """
    pattern = _unique_snap_name()
    snap = tmp_path / pattern
    snap.write_text(LISTENER_SRC)
    port = _ephemeral_port()

    old = subprocess.Popen([sys.executable, str(snap), str(port)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           start_new_session=True)
    new = None
    try:
        # PRECONDITION (asserted at runtime, not assumed): the old server really
        # holds the port before the cycle begins.
        assert _wait_listening(port, old.pid), "old fixture server never bound"
        before_pid = ds.listening_pid(port)
        assert before_pid == old.pid

        # stop the old listener (the recipe's --stop-deployed half).
        assert ds.stop_deployed(port, str(snap), wait_s=3.0) == 0
        # PRECONDITION: the port really is free now (stop worked) — else the
        # new server cannot bind and the verify step would test nothing.
        deadline = _time.time() + 3
        while _time.time() < deadline and ds.listening_pid(port) is not None:
            _time.sleep(0.05)
        assert ds.listening_pid(port) is None, "old listener never released :%s" % port

        # start the NEW server only AFTER the old one released the port (the
        # recipe's nohup half) — starting it earlier would make it die on bind.
        new = subprocess.Popen([sys.executable, str(snap), str(port)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
        # PRECONDITION: the new server has now taken the port.
        assert _wait_listening(port, new.pid), "new fixture server never bound"

        rc = ds.verify_deployed(port, str(snap), new.pid)
        assert rc == 0, "verify must succeed when the spawned process holds the port"
        after_pid = ds.listening_pid(port)
        # AFTER: a DIFFERENT pid from BEFORE, and its argv is the new snapshot.
        assert after_pid == new.pid
        assert after_pid != before_pid, (
            "the listener after deploy is the SAME pid as before — the cycle "
            "did not replace the process (the #508 defect)")
        assert ds.argv_runs_snap(ds.process_argv(after_pid), str(snap))
    finally:
        for p in (old, new):
            if p is None:
                continue
            try:
                os.kill(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait(timeout=3)


def test_verify_deployed_refuses_foreign_holder(tmp_path):
    """The failure mode the brief names: the old process still holds the port
    (it respawned / re-exec'd in place and survived the stop's timing window),
    so the new server dies on bind. verify_deployed must REFUSE — never print
    success — because the listener is NOT the spawned process.

    Asserts the MESSAGE names the foreign holder, not merely rc==1: with a dead
    spawned pid, disabling the pid-check branch alone still returns 1 via the
    argv check on the dead pid — so a bare rc assertion would stay green under
    that sabotage (a hollow red-run). The message flips when the pid-check
    branch is removed, which is what makes this a real named-line red-proof.

    Production line whose removal fails this test: the `if holder !=
    expect_pid: return 1` branch (specifically its 'NOT the new server'
    message). Disable the branch and verify returns 1 via the argv path with a
    different message — the 'NOT the new server' assertion fails.
    """
    pattern = _unique_snap_name()
    snap = tmp_path / pattern
    snap.write_text(LISTENER_SRC)
    port = _ephemeral_port()
    # OLD holds the port — the residual state after an autoreload in-place
    # re-exec that survived the stop window.
    old = subprocess.Popen([sys.executable, str(snap), str(port)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           start_new_session=True)
    new = None
    try:
        # OLD must bind FIRST — then NEW is guaranteed to die on bind. Starting
        # them back-to-back races the bind (under load NEW can win, leaving OLD
        # dead and this test waiting for a pid that will never listen).
        assert _wait_listening(port, old.pid), "old never bound"
        # NEW tries the same port and dies on bind (EADDRINUSE), invisibly.
        new = subprocess.Popen([sys.executable, str(snap), str(port)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
        # PRECONDITION: the new server really did die on bind (the defect's
        # invisible half) — without this, verify might be refusing for the
        # wrong reason. Poll until it exits on EADDRINUSE.
        deadline = _time.time() + 5
        while _time.time() < deadline and _alive(new.pid):
            _time.sleep(0.02)
        assert not _alive(new.pid), (
            "precondition failed: new server did not die on bind, so this "
            "test cannot prove verify refuses a foreign holder")
        assert ds.listening_pid(port) == old.pid

        import io, contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = ds.verify_deployed(port, str(snap), new.pid, wait_s=2.0)
        assert rc == 1, (
            "verify reported success while a FOREIGN pid (the old process) "
            "holds the port and the spawned process is dead — that is the "
            "#508 false-success, not fixed")
        assert "NOT the new server" in err.getvalue(), (
            "verify refused but did not name the foreign holder — the "
            "pid-check branch (whose message says 'NOT the new server') is "
            "not the path taken; a dead spawned pid with a foreign holder "
            "must trip that branch:\n" + err.getvalue())
    finally:
        for p in (old, new):
            if p is None:
                continue
            try:
                os.kill(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait(timeout=3)


def test_verify_deployed_refuses_when_new_server_died(tmp_path):
    """The new server died and nothing holds the port. verify must refuse (the
    spawned pid is gone), not wait out the whole window silently.

    Production line whose removal fails this test: the `if not
    _pid_alive(expect_pid): return 1` branch in verify_deployed. Sabotage by
    making _pid_alive always True and verify spins to the deadline; the message
    changes from 'exited without taking' to 'nothing came up', failing the
    assertion on the message.
    """
    snap = tmp_path / _unique_snap_name()
    snap.write_text("# none\n")
    port = _ephemeral_port()
    # a process that already exited — the spawned server that died on boot.
    dead = subprocess.Popen([sys.executable, "-c", "pass"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dead.wait(timeout=3)
    assert not _alive(dead.pid), "precondition: the spawned pid really is dead"

    import io, contextlib
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = ds.verify_deployed(port, str(snap), dead.pid, wait_s=1.5)
    assert rc == 1, "verify must refuse when the spawned process is dead"
    assert "exited without taking" in err.getvalue(), (
        "verify refused via the wrong branch — the dead-pid check that names "
        "'exited without taking' is not the path taken:\n" + err.getvalue())


def test_verify_deployed_pid_check_load_bearing_over_argv(tmp_path):
    """WHY the PID is the load-bearing signal, not argv: autoreload's in-place
    os.execv keeps the OLD process's argv IDENTICAL to the new snapshot (it
    re-execs `python3 $snap …`), so an argv-only check would accept the old
    process as 'deployed'. This fixture is the exact shape that defeats an
    argv-only check: the port is held by the OLD process (argv runs the snap),
    AND the spawned process (expect_pid) is ALSO alive running the snap — but
    on a DIFFERENT port. Both argvs run the snap; only the PID distinguishes
    the listener from the spawned process. verify MUST refuse on the pid
    mismatch alone.

    Production line whose removal fails this test: the `if holder !=
    expect_pid` pid-equality check. Replace the identity check with an
    argv-only check on expect_pid (drop the pid compare) and this test goes
    RED — because expect_pid's argv runs the snap, an argv-only verify returns
    0 (false success) while the OLD process still serves the deploy port.
    """
    pattern = _unique_snap_name()
    snap = tmp_path / pattern
    snap.write_text(LISTENER_SRC)
    port = _ephemeral_port()
    other_port = _ephemeral_port()
    assert port != other_port
    # The OLD process holds the deploy port; argv runs the snap (exactly what
    # an autoreload in-place re-exec leaves behind).
    old = subprocess.Popen([sys.executable, str(snap), str(port)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           start_new_session=True)
    # The spawned process is alive and ALSO runs the snap — but on a different
    # port, so it is NOT the listener on the deploy port. This is the shape
    # that makes an argv-only check accept it: both argvs match the snap.
    spawned = subprocess.Popen([sys.executable, str(snap), str(other_port)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    try:
        assert _wait_listening(port, old.pid)
        assert _wait_listening(other_port, spawned.pid)
        # PRECONDITION (the whole point): BOTH processes' argv run the snap, so
        # an argv-only identity check cannot tell them apart — only the pid can.
        assert ds.argv_runs_snap(ds.process_argv(old.pid), str(snap)), (
            "precondition: the old holder's argv runs the snap")
        assert ds.argv_runs_snap(ds.process_argv(spawned.pid), str(snap)), (
            "precondition: the spawned process's argv ALSO runs the snap — "
            "without both matching, an argv-only check could not be proven "
            "insufficient here")
        assert old.pid != spawned.pid

        rc = ds.verify_deployed(port, str(snap), spawned.pid, wait_s=2.0)
        assert rc == 1, (
            "verify accepted a deploy port held by a process whose pid is NOT "
            "the spawned one, even though both argvs run the snap — an "
            "argv-only check is insufficient (autoreload re-exec makes the old "
            "argv match the new snap); the PID is load-bearing and this must "
            "refuse")
    finally:
        for p in (old, spawned):
            try:
                os.kill(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait(timeout=3)


def test_wait_port_free_returns_zero_when_free_and_one_when_held(tmp_path):
    """wait_port_free: 0 when the port is (and stays) free; 1 when held at the
    deadline. Both halves against real listeners on a private port.

    Production line whose removal fails this test: the `return 1` refuse path
    in wait_port_free (the held case). Make it always return 0 and the held
    assertion fails.
    """
    port_free = _ephemeral_port()
    assert ds.wait_port_free(port_free, wait_s=0.6, settle=0.2) == 0, (
        "a free port must read free")

    snap = tmp_path / _unique_snap_name()
    snap.write_text(LISTENER_SRC)
    port_held = _ephemeral_port()
    holder = subprocess.Popen([sys.executable, str(snap), str(port_held)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              start_new_session=True)
    try:
        assert _wait_listening(port_held, holder.pid)
        assert ds.wait_port_free(port_held, wait_s=0.8, settle=0.2) == 1, (
            "a port held for the whole window must be refused — starting the "
            "new server against it would die on bind, invisibly")
    finally:
        try:
            os.kill(holder.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        holder.wait(timeout=3)


def test_wait_port_free_settle_rejects_the_execv_flicker(monkeypatch, tmp_path):
    """The SETTLE is load-bearing: the autoreload os.execv flicker frees the
    close-on-exec socket for milliseconds before the new image rebinds, so a
    single `listening_pid is None` sample is not proof the port is free. This
    feeds wait_port_free a FLICKERING listener (None briefly, then held again)
    and asserts it does NOT declare free until the port STAYS none.

    Production line whose removal fails this test: the inner settle loop in
    wait_port_free (the `while time.time() < quiet_to` confirm). Remove it —
    return 0 on the first None sample — and this test goes red, because the
    flicker's brief None windows now read as 'free'.

    The flicker is driven by a controlled `listening_pid` sequence rather than
    a real rebinding process, because a sub-ms real flicker cannot be sampled
    deterministically; the production settle LOOP runs for real against that
    sequence (the sequence is the environment, not a rebuild of the unit).
    """
    held_pid = 999999  # a foreign pid that is not the recipe's spawned one
    # A flicker: a short free window, then held again, then stays held — the
    # shape of the os.execv close-on-exec gap. settle (0.3s, expressed below
    # via time as 2 None samples before the rebind) exceeds the free window,
    # so a correct settle never declares free.
    seq = [None, None, held_pid, held_pid, held_pid, held_pid, held_pid]
    state = {"i": 0}

    def fake_listening_pid(port):
        if state["i"] < len(seq):
            v = seq[state["i"]]
            state["i"] += 1
            return v
        return held_pid

    monkeypatch.setattr(ds, "listening_pid", fake_listening_pid)
    monkeypatch.setattr(_time, "sleep", lambda *_a: None)  # keep the loop snappy
    rc = ds.wait_port_free(0, wait_s=0.5, settle=0.3)
    assert rc == 1, (
        "wait_port_free declared the port free during an execv-style flicker "
        "(a brief None window that did not STAY none) — the settle that guards "
        "the autoreload rebind gap is not in place")


def test_verify_deployed_cli_wire(tmp_path):
    """CLI verb the recipe calls: --verify-deployed --port --snap --expect-pid.

    Production line: the `if args.verify_deployed` branch in main().
    """
    root = Path(__file__).resolve().parent
    snap = tmp_path / _unique_snap_name()
    snap.write_text(LISTENER_SRC)
    port = _ephemeral_port()
    server = subprocess.Popen([sys.executable, str(snap), str(port)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              start_new_session=True)
    try:
        assert _wait_listening(port, server.pid)
        r = subprocess.run(
            [sys.executable, "dev/deploy_state.py", "--verify-deployed",
             "--port", str(port), "--snap", str(snap),
             "--expect-pid", str(server.pid)],
            cwd=str(root), capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "deploy verified" in r.stdout
        assert str(server.pid) in r.stdout
    finally:
        try:
            os.kill(server.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        server.wait(timeout=3)


def test_justfile_deploy_verifies_identity_and_drops_dev_and_curl():
    """Pin the recipe wiring for #508:
      - it calls `--verify-deployed ... --expect-pid "$newpid"` (identity, not
        a curl liveness), and only echoes success AFTER it;
      - the success line is no longer a bare `curl -sf && echo deployed`;
      - the deployed server is no longer started with `--dev` (autoreload was
        the re-exec enabler — see the recipe comment);
      - it waits for the port to be free before starting.

    Production line: the deploy recipe body in justfile. Remove --verify-deployed
    (or move the echo before it, or re-add --dev / the curl readiness) and the
    relevant assertion goes red.
    """
    import re
    root = Path(__file__).resolve().parent
    text = (root / "justfile").read_text()
    start = text.index("\ndeploy rev=")
    rest = text[start + 1:]
    end = len(rest)
    for i, line in enumerate(rest.splitlines()[1:], start=1):
        if line and not line[0].isspace() and not line.startswith("#") and ":" in line:
            offset = 0
            for j, l in enumerate(rest.splitlines()):
                if j == i:
                    end = offset
                    break
                offset += len(l) + 1
            break
    recipe = rest[:end]
    cmd_lines = []
    for line in recipe.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        cmd_lines.append(stripped)
    joined = "\n".join(cmd_lines)

    assert "--verify-deployed" in joined, (
        "deploy recipe does not verify the listener's identity — the #508 "
        "fix: success must be the spawned pid running the snap, not a curl 200")
    assert "--expect-pid" in joined and '"$newpid"' in joined, (
        "deploy recipe does not pass the spawned pid to --verify-deployed")
    # the echo (success) must come AFTER the verify call.
    i_verify = joined.index("--verify-deployed")
    i_echo = joined.index('echo "deployed')
    assert i_verify < i_echo, (
        "the success echo must come AFTER --verify-deployed — echoing before "
        "the identity check restores the false-success defect")
    # the old curl-liveness readiness is gone from the command lines.
    assert not re.search(r"curl\s+-sf", joined), (
        "deploy recipe still uses curl -sf liveness as its readiness check — "
        "that is the #508 defect (it grades whatever answers, not identity)")
    # the deployed server is no longer started with --dev (autoreload enabler).
    for line in cmd_lines:
        if line.startswith("nohup python3"):
            assert "--dev" not in line, (
                "deploy recipe still starts the deployed server with --dev — "
                "autoreload (implied by --dev) re-execs the old process in "
                "place on this recipe's own `mv`, the race's enabler:\n" + line)
    assert "--wait-port-free" in joined, (
        "deploy recipe does not wait for the port to free before starting — "
        "the stop/autoreload race can leave the old process holding the port")


# --- #520: stop the old server BEFORE shipping the snapshot (the mv) --------
#
# The defect: `just deploy` ran `mv $snap.tmp $snap` (shipping the snapshot to
# its final path) BEFORE --stop-deployed. Against an autoreloading occupant
# the mv overwrote the file it watched, so autoreload os.execv'd the old
# process IN PLACE (same pid, port flickered free via close-on-exec then
# rebound) — arming the race the #508 identity checks then had to catch. The
# fix is ordering: stop FIRST, then ship the snapshot to a path no live process
# watches. The #480 boot-proofs (ship-siblings + assert-importable) stay
# BEFORE the stop — only the race-arming `mv` moved.
#
# Production line whose removal fails the order test: the `mv "$snap.tmp"`
# line's position in the deploy recipe. Move the mv back before --stop-deployed
# (the pre-#520 order) and stop no longer precedes ship.


def test_justfile_deploy_stops_before_ship_before_start_before_verify():
    """#520 — the deploy recipe's order is stop → ship → start → verify.

    The four anchors are DERIVED from the recipe text at runtime (a literal
    line-number assertion is a check with an expiry date):
      stop  — the `--stop-deployed` verb
      ship  — the shell `mv` that ships the snapshot to its final path (the
              only `mv` in the recipe; ship-siblings is a Python verb, not a
              shell mv, and writes different files than $snap so it does not
              arm the race)
      start — the `nohup` start of the new server
      verify— the `--verify-deployed` identity check

    Production line whose removal fails this test: the `mv "$snap.tmp"` line's
    position in the deploy recipe. Move the mv back before --stop-deployed (the
    pre-#520 order) and `i_stop < i_ship` is violated.
    """
    root = Path(__file__).resolve().parent
    text = (root / "justfile").read_text()
    start = text.index("\ndeploy rev=")
    rest = text[start + 1:]
    end = len(rest)
    for i, line in enumerate(rest.splitlines()[1:], start=1):
        if line and not line[0].isspace() and not line.startswith("#") and ":" in line:
            offset = 0
            for j, l in enumerate(rest.splitlines()):
                if j == i:
                    end = offset
                    break
                offset += len(l) + 1
            break
    recipe = rest[:end]
    cmd_lines = []
    for line in recipe.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        cmd_lines.append(stripped)
    joined = "\n".join(cmd_lines)

    i_stop = joined.index("--stop-deployed")
    i_wait = joined.index("--wait-port-free")
    # the ship step: the shell `mv` that ships the snapshot. Anchoring on a
    # command line starting with `mv ` is specific to the ship step — it is
    # the only shell mv in the recipe (ship-siblings is a Python verb).
    i_ship = None
    for line in cmd_lines:
        if line.startswith("mv "):
            i_ship = joined.index(line)
            break
    assert i_ship is not None, (
        "deploy recipe has no `mv` ship step — the snapshot is never shipped "
        "to its final path")
    i_start = joined.index("nohup")
    i_verify = joined.index("--verify-deployed")

    assert i_stop < i_ship, (
        "the deploy recipe ships the snapshot (mv) BEFORE --stop-deployed — "
        "the #520 defect: against an autoreloading occupant the mv arms the "
        "execv race the #508 checks then have to catch. Stop must come first.")
    assert i_stop < i_wait < i_ship, (
        "the deploy recipe ships the snapshot (mv) before the port is "
        "confirmed free — the coordinator's green red-run at the #520 gate "
        "(mv injected between stop and wait) PASSED the original stop<ship "
        "anchor, pinning only half the order. The settle must complete "
        "before the mv overwrites the watched path, or the SIGTERM-release "
        "window re-arms the flicker the wait exists to outlast.")
    assert i_ship < i_start, (
        "the deploy recipe starts the new server before shipping the snapshot "
        "(mv) — the new server would boot the OLD content at $snap")
    assert i_start < i_verify, (
        "the deploy recipe verifies before starting — identity of what?")


# An autoreloading standin: binds a port, watches its OWN source file for mtime
# changes, and os.execv's itself in place on change (same pid, fresh
# GENERATION, close-on-exec socket flickers free then rebinds). This is the
# exact shape of the old --dev deployed server: the recipe's `mv` overwrote the
# file it watched, triggering the in-place re-exec that armed the #508 race.
AUTORELOAD_STANDIN = textwrap.dedent("""\
    import os, sys, time, socket, threading
    GENERATION = "%.6f" % time.time()
    PORT = int(sys.argv[1])
    MARKER = sys.argv[2]
    _tmp = MARKER + ".tmp"
    with open(_tmp, "w") as _f:
        _f.write(GENERATION)
    os.replace(_tmp, MARKER)
    _s = socket.socket()
    _s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _s.bind(("127.0.0.1", PORT))
    _s.listen(8)
    _src = os.path.abspath(__file__)
    _my_mtime = os.path.getmtime(_src)

    def _watch():
        while True:
            time.sleep(0.05)
            try:
                if os.path.getmtime(_src) != _my_mtime:
                    os.execv(sys.executable,
                             [sys.executable, _src, str(PORT), MARKER])
            except OSError:
                pass

    threading.Thread(target=_watch, daemon=True).start()
    while True:
        time.sleep(1)
""")


def test_deploy_new_ordering_completes_against_autoreload_standin(tmp_path):
    """#520 — the reordered sequence (stop → wait-free → ship → start → verify)
    completes with identity verified against an autoreloading occupant, with no
    manual step. The old order (ship before stop) armed the race by overwriting
    the file the autoreloader watched; the new order ships to a dead path.

    PRECONDITION (asserted at runtime, not assumed): the standin really IS
    autoreloading — overwriting its file triggers an in-place os.execv (same
    pid, fresh GENERATION). Without this the test is vacuous: a non-autoreloading
    occupant cannot arm the race regardless of order, so a green against one
    proves nothing about the ordering.

    Production line whose removal fails the precondition: the `os.execv(...)`
    call inside AUTORELOAD_STANDIN's `_watch` (remove it and the standin never
    re-execs, so the precondition's reexeced assertion fails). Production line
    whose removal fails the main sequence: `pid = listening_pid(port)` in
    stop_deployed (sabotage to `pid = None` and stop returns 0 without killing
    — the old process survives the stop, holds the port, and the
    `not _alive(old.pid)` assertion fails).
    """
    snap = tmp_path / _unique_snap_name()
    snap.write_text(AUTORELOAD_STANDIN)
    marker = tmp_path / "gen.txt"
    port = _ephemeral_port()

    old = subprocess.Popen(
        [sys.executable, str(snap), str(port), str(marker)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    new = None
    try:
        assert _wait_listening(port, old.pid), "standin never bound"
        gen_before = marker.read_text()
        assert gen_before, "standin never wrote its generation marker"

        # PRECONDITION: prove the standin re-execs on file change (the race's
        # enabler). Overwrite the file; the watch thread sees the mtime change
        # and os.execv's in place (same pid, fresh GENERATION, port rebinds).
        _time.sleep(0.3)   # let the watch thread record its baseline mtime
        snap.write_text(AUTORELOAD_STANDIN)   # same content, new mtime -> re-exec
        deadline = _time.time() + 8
        reexeced = False
        while _time.time() < deadline:
            try:
                gen_now = marker.read_text()
            except OSError:
                gen_now = gen_before
            holder = ds.listening_pid(port)
            if gen_now != gen_before and holder == old.pid:
                reexeced = True
                break
            _time.sleep(0.05)
        assert reexeced, (
            "precondition failed: the standin did not re-exec on file change "
            "(generation marker unchanged) — it is not autoreloading, so this "
            "test cannot prove the ordering disarms the race")

        # === THE NEW ORDERING (stop → wait-free → ship → start → verify) ===

        # 1. STOP the old server BEFORE shipping (the #520 fix). The old
        #    process is still running $snap, so argv_runs_snap matches by path.
        assert ds.stop_deployed(port, str(snap), wait_s=3.0) == 0, (
            "stop failed — the old autoreloading server could not be stopped")
        assert not _alive(old.pid), (
            "stop returned success but the old process is still alive — "
            "the race is live: shipping now would trigger a re-exec")
        # 2. WAIT for the port to be really free.
        assert ds.wait_port_free(port, wait_s=3.0) == 0, (
            "port never freed after stop — the old process respawned/rebound")
        # 3. SHIP the snapshot now that no live process watches it. This
        #    overwrite would have armed the race in the old order; now it is
        #    inert. LISTENER_SRC is the "new server" content.
        snap.write_text(LISTENER_SRC)
        # 4. START the new server.
        new = subprocess.Popen(
            [sys.executable, str(snap), str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        # 5. VERIFY identity.
        assert _wait_listening(port, new.pid), "new server never bound"
        rc = ds.verify_deployed(port, str(snap), new.pid)
        assert rc == 0, (
            "verify failed against an autoreloading occupant under the new "
            "ordering — the deploy did not complete cleanly")
        after_pid = ds.listening_pid(port)
        assert after_pid == new.pid
        assert after_pid != old.pid, (
            "the listener after deploy is the old process — the new ordering "
            "did not replace it")
    finally:
        for p in (old, new):
            if p is None:
                continue
            try:
                os.kill(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait(timeout=3)
