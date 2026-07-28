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
import subprocess
import sys
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
