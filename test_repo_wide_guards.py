"""Contract tests for dev/repo_wide_guards.py (#778).

Two merge-then-revert cycles in one hour shared one cause: a lane obeyed the
"run a targeted subset" rule, but a REPO-WIDE guard governs a population the
lane's diff cannot enumerate, so the targeted subset never reached it. This
suite pins the three things that make the always-run set trustworthy:

1. every registry member resolves to a real collected test right now — a
   registry that resolves to nothing must not read as "all guards passed"
   (#671);
2. the detector's signal is narrow enough to stay silent on ordinary module
   tests that happen to enumerate a directory (#707/#755) — flagging
   test_lint.py wholesale would reproduce the trap, not avoid it;
3. the detector DOES fire on the whole-repo-enumeration form, so a new
   repo-wide guard cannot join the tree unregistered in silence.

SYNTHETIC STRINGS ARE BUILT FROM PARTS (``_LS``) so this file's own source
never contains the bare ``ls-files`` token the detector matches — otherwise the
suite would be its own false candidate. A self-check asserts that invariant.
"""
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
TOOL_PATH = REPO / "dev" / "repo_wide_guards.py"
BOILERPLATE_PATH = REPO / "briefs" / "boilerplate.md"


def _load():
    loader = importlib.machinery.SourceFileLoader("repo_wide_guards", str(TOOL_PATH))
    spec = importlib.util.spec_from_loader("repo_wide_guards", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


rwg = _load()

# Built from parts so this source holds no bare quoted "ls-files" token — the
# detector scans test sources, and a literal here would make the suite its own
# candidate. The self-check below pins this.
_LS = "ls" + "-" + "files"

# The opt-in marker token, also built from parts so this test file's own
# source does not declare itself a repo-wide guard and become a false candidate.
_MK = "repo-wide" + "-guard" + ":"


# ── the registry is the authoritative always-run set ───────────────────

class TestRegistry:
    """The set lanes run. Adding a member needs the criterion argued; the
    detector + validate keep it from rotting."""

    def test_registry_is_non_empty(self):
        # Precondition every other test relies on: there IS an always-run set.
        assert rwg.REGISTRY, "REGISTRY must name at least one repo-wide guard"

    def test_members_are_distinct_node_ids(self):
        # A duplicate would let one rename hide behind another's resolve.
        assert len(rwg.REGISTRY) == len(set(rwg.REGISTRY)), (
            f"duplicate registry entries: {rwg.REGISTRY}")

    def test_two_known_guards_are_registered(self):
        # The two guards that would have caught today's reverts (#776, #645 i9).
        # Named by node id (not file) so test_ledger_cli.py's 35 targeted tests
        # are not swept into the always-run set (#707).
        assert "test_no_raw_connect.py::test_no_raw_sqlite_connect_in_production_sources" in rwg.REGISTRY
        assert "test_ledger_cli.py::test_the_map_covers_every_verb" in rwg.REGISTRY

    def test_the_ledger_guard_is_a_node_id_not_the_whole_file(self):
        # The granularity decision, made explicit: test_ledger_cli.py holds many
        # targeted tests and ONE repo-wide test, so the file must NOT be
        # registered wholesale — only the repo-wide node id. A future edit that
        # broadens this to the file reverses the #707 ruling silently.
        ledger_entries = [n for n in rwg.REGISTRY if n.startswith("test_ledger_cli.py")]
        assert ledger_entries, "precondition: a test_ledger_cli.py entry exists"
        for n in ledger_entries:
            assert "::" in n, (
                f"{n!r} is a FILE, not a node id — registering the whole "
                f"test_ledger_cli.py sweeps in ~35 targeted tests (#707)")

    def test_every_member_resolves_to_a_real_collected_test(self):
        # #671: a registry entry naming a test that does not exist (renamed,
        # deleted, moved) must fail loudly. This is the green base; the
        # red-proof (direction 1) injects a stale entry and watches it refuse.
        for nid in rwg.REGISTRY:
            assert rwg._collect_resolves(nid), (
                f"registry entry {nid!r} does not resolve to a collected test "
                f"— a stale entry must not read as 'all guards passed' (#671)")


class TestLaneContract:
    """The standing brief delegates live registry facts to the executable source."""

    def test_worktree_ledger_invocation_precedes_standing_rules(self):
        text = BOILERPLATE_PATH.read_text(encoding="utf-8")
        invocation = (
            "python3 dev/ledger.py get <id> --ledger "
            "/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md"
        )
        assert text.count(invocation) == 1, (
            "boilerplate must give exactly one unambiguous worktree ledger invocation"
        )
        assert text.index(invocation) < text.index("## Standing rules"), (
            "working ledger invocation must appear before a lane reaches standing rules"
        )

    def test_guard_population_is_not_reasserted_in_prose(self):
        text = BOILERPLATE_PATH.read_text(encoding="utf-8")
        before_scope, separator, _after_scope = text.partition(
            "This catches cross-cutting"
        )
        assert separator, "boilerplate lost the cross-cutting scope boundary"
        source_statement = " ".join(before_scope.rsplit("\n\n", 1)[-1].split())
        assert source_statement == (
            "The command above is the single source for the set and its current "
            "population (`#440`)."
        ), (
            "boilerplate must not restate registry members or a hardcoded count; "
            "the executable list command owns the current population"
        )


# ── the detector signal: narrow enough to stay silent, broad enough to fire ──

class TestDetectorSignal:
    """The signal is a bare git-ls-files (whole-repo enumeration). Direction 2
    demands silence on healthy inputs; the detector must NOT flag test_lint.py
    wholesale."""

    def test_bare_ls_files_is_a_candidate(self):
        # The whole-repo form: ls-files is the last positional arg.
        src = f'subprocess.run(["git", "{_LS}"], cwd=REPO, capture_output=True)'
        assert rwg.is_whole_repo_enumeration(src) is True

    def test_trailing_comma_bare_is_still_a_candidate(self):
        src = f'["git", "{_LS}",]'
        assert rwg.is_whole_repo_enumeration(src) is True

    def test_path_restricted_ls_files_is_silent(self):
        # test_guard_evidence.py's shape: ls-files <subdir>. Ordinary module
        # test enumerating a directory — must stay silent (#755).
        src = f'["git", "-C", str(ROOT), "{_LS}", "screenshots"]'
        assert rwg.is_whole_repo_enumeration(src) is False

    def test_error_unmatch_single_file_is_silent(self):
        # test_lint.py's shape: ls-files --error-unmatch <one file>. Checking a
        # specific file is tracked is NOT a whole-repo enumeration.
        src = f'git("{_LS}", "--error-unmatch", str(rel), check=False)'
        assert rwg.is_whole_repo_enumeration(src) is False

    def test_ordinary_glob_of_a_directory_is_silent(self):
        # The common "glob a couple of files" healthy input the brief names —
        # an ordinary module test iterating a directory must not fire.
        src = 'names = sorted(p.name for p in briefs_dir.glob("*.md"))'
        assert rwg.is_whole_repo_enumeration(src) is False

    def test_rglob_of_a_subdirectory_is_silent(self):
        # rglob rooted at a subdirectory (not the repo root) is the ordinary
        # case; repo-rooted rglob can't be distinguished statically without
        # false positives, so the detector excludes rglob entirely (named).
        src = 'for p in target.rglob("*"): assert p.is_file()'
        assert rwg.is_whole_repo_enumeration(src) is False

    def test_prose_mention_without_quotes_is_silent(self):
        # A comment/docstring that says "git ls-files" (no quoted token) must
        # not fire — only the executable argv form matches.
        src = '# this guard runs git ls-files over production sources\npass'
        assert rwg.is_whole_repo_enumeration(src) is False


# ── the opt-in marker signal (#780) ──────────────────────────────────────

class TestMarkerSignal:
    """The opt-in marker comment is the escape hatch for guards the
    lexical detector cannot see (parser-coverage family). It is exact and
    zero-false-positive because no ordinary test contains it by accident."""

    def test_marker_comment_declares(self):
        src = f'    # {_MK} scans every parser verb against a hand map\npass'
        assert rwg.is_declared_repo_wide(src) is True

    def test_marker_at_module_level_declares(self):
        src = f'# {_MK} every production source for a raw connect\npass'
        assert rwg.is_declared_repo_wide(src) is True

    def test_no_marker_is_silent(self):
        # An ordinary test with no marker must not fire (#755).
        src = 'def test_something():\n    assert 1 + 1 == 2\n'
        assert rwg.is_declared_repo_wide(src) is False

    def test_prose_mention_of_guard_is_silent(self):
        # A docstring that says "repo wide guard" (no ``#`` token) must not
        # fire — only the exact comment form matches.
        src = '"""a repo wide guard that checks things"""\npass'
        assert rwg.is_declared_repo_wide(src) is False


class TestDetectorOnRealFiles:
    """The concrete healthy/sick inputs the brief demands, against the REAL
    tree (not synthetic strings)."""

    def test_the_real_raw_connect_guard_is_a_candidate(self):
        # test_no_raw_connect.py is THE exemplar whole-repo guard and the reason
        # this exists. Its source must trip the file-enumeration signal.
        src = (REPO / "test_no_raw_connect.py").read_text(encoding="utf-8")
        assert rwg.is_whole_repo_enumeration(src) is True

    def test_the_real_ledger_guard_is_declared(self):
        # test_ledger_cli.py::test_the_map_covers_every_verb is the
        # parser-coverage guard — no ls-files, invisible to the lexical
        # detector. It now carries the marker, so it is detected by the
        # second signal (#780 closes the blind spot).
        src = (REPO / "test_ledger_cli.py").read_text(encoding="utf-8")
        assert rwg.is_declared_repo_wide(src) is True

    def test_the_real_ledger_guard_has_no_ls_files(self):
        # Precondition: the parser-coverage guard does NOT use git ls-files,
        # which is why the marker was needed.
        src = (REPO / "test_ledger_cli.py").read_text(encoding="utf-8")
        assert rwg.is_whole_repo_enumeration(src) is False, (
            "test_ledger_cli.py is the parser-coverage family — it must not "
            "trip the ls-files signal, because it is the blind spot the "
            "marker exists for")

    def test_test_lint_py_is_not_flagged_wholesale(self):
        # THE trap (#707/#755): test_lint.py holds 563 tests and uses
        # --error-unmatch + directory globs, never a bare whole-repo ls-files,
        # and does not carry the marker. If either signal flags it, the
        # targeted-subset ruling is reversed by a helper meant to support it.
        src = (REPO / "test_lint.py").read_text(encoding="utf-8")
        assert rwg.is_whole_repo_enumeration(src) is False, (
            "test_lint.py must not trip the ls-files signal — flagging it "
            "wholesale is the trap this tool exists to avoid (#707)")
        assert rwg.is_declared_repo_wide(src) is False, (
            "test_lint.py must not carry the marker — it is not a repo-wide "
            "guard (#755)")
        lint = REPO / "test_lint.py"
        assert lint not in rwg.find_candidate_files(), (
            "find_candidate_files must not return test_lint.py")

    def test_path_restricted_real_files_are_not_candidates(self):
        # test_guard_evidence.py and test_client_dist.py use git ls-files but
        # with a path / --error-unmatch — ordinary module tests. They also do
        # not carry the marker.
        for name in ("test_guard_evidence.py", "test_client_dist.py"):
            src = (REPO / name).read_text(encoding="utf-8")
            assert rwg.is_whole_repo_enumeration(src) is False, (
                f"{name} must not trip the ls-files signal (path/flag-restricted)")
            assert rwg.is_declared_repo_wide(src) is False, (
                f"{name} must not carry the marker (#755)")

    def test_today_only_registered_files_are_candidates(self):
        # The honest current state: both registered guards are now detected
        # (test_no_raw_connect by ls-files + marker; test_ledger_cli by marker
        # alone), and both are registered — so detect_unregistered() is empty.
        # If a new unregistered candidate appears, this reds and names it.
        unreg = rwg.detect_unregistered()
        assert unreg == [], (
            f"unregistered repo-wide candidate(s) to classify: "
            f"{[p.name for p in unreg]} — register or exclude with a reason")


class TestSelfGuard:
    """This suite builds synthetic ls-files AND marker strings; if it held
    either literally it would become its own false candidate. Pinned."""

    def test_this_files_own_source_is_not_a_candidate(self):
        own = Path(__file__).read_text(encoding="utf-8")
        assert rwg.is_whole_repo_enumeration(own) is False, (
            "this test's own source trips the ls-files signal — obfuscate "
            "the synthetic strings so the suite is not a false candidate")
        assert rwg.is_declared_repo_wide(own) is False, (
            "this test's own source trips the marker signal — obfuscate "
            "the synthetic strings so the suite is not a false candidate")
