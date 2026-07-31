#!/usr/bin/env python3
"""Red-first contract tests for dev/concurrent_tests.py (#666).

The defect under test is a SILENT wrong number, in three flavours the brief
names: counting yourself (off-by-one that makes the number useless inside a
day), conflating "could not enumerate" with "zero" (#671/#136), and a count that
reads as a verdict about whether it is safe to proceed (#590). Each test asserts
the discriminating substring that would fail if the defect returned.

The /proc reader is injectable via `scan(procs=..., exclude=...)`, so these run
against a synthetic process list and never touch the real one — which is also
why the assertion has to bind the rendered message and not an exit code (the
advisory's contract is advisory: exit 0 always, per #404's shape).
"""
import importlib.machinery
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent
CLI_PATH = REPO / "dev" / "concurrent_tests.py"


def _load():
    loader = importlib.machinery.SourceFileLoader("concurrent_tests", str(CLI_PATH))
    spec = importlib.util.spec_from_loader("concurrent_tests", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


ct = _load()


def _scan(procs, exclude=None):
    return ct.scan(procs, exclude=exclude or set())


# ── trap 1: do not count yourself ──────────────────────────────────────

class TestSelfExclusion:
    """A pytest process that IS us (or our ancestor) is not 'other'."""

    def test_a_sibling_lane_is_counted(self):
        # A separate process tree running `python3 -m pytest -q` is the thing
        # we want to see. Assertion that would fail: dropping the classify()
        # `python* -m pytest` branch makes scan return 0 here.
        procs = [(999, ["python3", "-m", "pytest", "-q"])]
        r = _scan(procs)
        assert r["pytest"] == 1
        assert "1 other pytest suite" in ct.render(r, None)

    def test_our_own_pytest_ancestor_is_not_counted(self):
        # The helper's own ancestor running pytest is "us", not "other". This is
        # the off-by-one: assert it renders "no other pytest suites", which fails
        # if self/ancestor exclusion is removed (the ancestor is counted).
        ancestor = 4242
        procs = [(ancestor, ["python3", "-m", "pytest", "-q"])]
        r = _scan(procs, exclude={ancestor})
        assert r["pytest"] == 0
        assert "no other pytest suites" in ct.render(r, None)

    def test_a_shell_whose_command_text_mentions_pytest_is_not_counted(self):
        # The live trap: my own measurement shell had argv0=zsh with the word
        # 'pytest' in the command text, and `pgrep -f pytest` counted it at 1
        # with zero real suites. Token classification on argv0 must NOT match.
        # Assertion that would fail: a substring match on the joined cmdline.
        procs = [(1, ["/usr/bin/zsh", "-c", "echo pytest; pgrep -fc pytest"])]
        r = _scan(procs)
        assert r["pytest"] == 0

    def test_direct_pytest_argv0_is_counted(self):
        # console_script form: argv[0] basename 'pytest'. Covers `just pytest`
        # when run through a venv shim. Assertion binds the plural form too.
        r = _scan([(7, ["/v/bin/pytest", "-q"])])
        assert r["pytest"] == 1
        assert "1 other pytest suite" in ct.render(r, None)


# ── trap 2: enum-failure is not zero (#671/#136) ───────────────────────

class TestEnumFailureIsNotZero:
    """'I could not enumerate' must render as a fault, never as zero."""

    def test_none_renders_unreadable_not_zero(self):
        r = _scan(None)
        assert r["enumerated"] is False
        msg = ct.render(r, None)
        # Discriminating: the broken instrument names itself, never says "0".
        assert "unreadable" in msg
        assert "no other pytest suites" not in msg
        assert "0 other pytest" not in msg

    def test_empty_is_genuinely_zero_not_unreadable(self):
        # The other half of #136: an empty list IS a real zero (calm), distinct
        # from None (broken). Assert they render differently.
        empty = ct.render(_scan([]), None)
        none = ct.render(_scan(None), None)
        assert "no other pytest suites" in empty
        assert "unreadable" in none
        assert empty != none


# ── trap 3: a count is not a verdict (#590) ────────────────────────────

class TestAdvisoryNotVerdict:
    """The line describes the machine; it never says 'safe' or 'go'."""

    def test_renders_advisory_marker(self):
        # Any non-zero count must carry the advisory marker so it reads as a
        # question, not permission to proceed.
        r = _scan([(1, ["pytest"]), (2, ["pytest"])])
        msg = ct.render(r, None)
        assert "2 other pytest suites" in msg
        assert "(advisory)" in msg
        assert "safe" not in msg.lower()

    def test_browser_counted_separately(self):
        # The third note's actionable axis: one Chromium costs more than several
        # pytest lanes. The count must be separate, not folded into pytest.
        procs = [(1, ["pytest"]), (2, ["/opt/chrome/chrome", "--headless"])]
        r = _scan(procs)
        assert r["pytest"] == 1
        assert r["browser"] == 1
        msg = ct.render(r, None)
        assert "1 browser/guard process" in msg


# ── the third note's scarce resource: memory pressure with 0 suites ────

class TestMemoryPressure:
    """Memory pressure + zero suites is the condition a pytest count cannot see;
    the advisory surfaces it so it does not read as 'fine'."""

    def test_swap_heavy_clause_appears_with_zero_suites(self):
        # >50% swap used. The pytest count is 0, but the line must NOT read as a
        # calm all-clear — it carries the memory clause. This is the red-proof
        # for brief direction-2 candidate 3.
        mem = {"SwapTotal": 60 * 1024 * 1024, "SwapFree": 8 * 1024 * 1024,
               "MemAvailable": 0, "MemTotal": 60 * 1024 * 1024}
        msg = ct.render(_scan([]), mem)
        assert "no other pytest suites" in msg
        assert "mem: swap" in msg
        assert "memory-bound" in msg

    def test_calm_machine_has_no_memory_clause(self):
        # Low swap use omits the clause — #612: fewest tokens that carry meaning.
        mem = {"SwapTotal": 60 * 1024 * 1024, "SwapFree": 55 * 1024 * 1024,
               "MemAvailable": 0, "MemTotal": 60 * 1024 * 1024}
        msg = ct.render(_scan([]), mem)
        assert "mem: swap" not in msg

    def test_no_swap_present_is_calm(self):
        # SwapTotal 0 (swap disabled): the clause cannot apply, must not render.
        msg = ct.render(_scan([]), {"SwapTotal": 0, "SwapFree": 0})
        assert "mem: swap" not in msg


# ── argv-token classification edge cases (brief direction 2 candidate 2) ──

class TestInvocationForms:
    """`python -m pytest` and `just`/`just test` must classify correctly."""

    def test_python_m_pytest_matches(self):
        assert ct.classify(["python3", "-m", "pytest", "-q"]) == "pytest"

    def test_python311_m_pytest_matches(self):
        assert ct.classify(["python3.11", "-m", "pytest"]) == "pytest"

    def test_just_test_does_not_false_match(self):
        # `just test` / `just pytest` argv0 is 'just' — must not be counted as a
        # suite. The suite is the `python3 -m pytest` child just SPAWNS, which a
        # later enumeration sees. Assertion fails if classify scans substrings.
        assert ct.classify(["just", "test"]) is None
        assert ct.classify(["just", "pytest"]) is None

    def test_empty_argv_is_none(self):
        assert ct.classify([]) is None
        assert ct.classify([""]) is None
