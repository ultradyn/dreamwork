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
    for rel in ("ledger_parse.py", "lint.py", "watch.py",
                "user_events/__init__.py", "user_events/sqlite.py"):
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
