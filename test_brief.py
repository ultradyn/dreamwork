#!/usr/bin/env python3
"""Contract tests for the lane-brief generator (#881).

Two things these tests exist to bind, beyond the ordinary refusals:

**The generator and the validator must agree without sharing a source of
truth.** `dev/brief.py` imports nothing from `dev/dispatch_lane.py` and retypes
the constrained literals. That keeps the validator able to witness a generator
bug at runtime. The cost is drift, and it is paid here: `test_inbox_prefix_…`
binds the two literals, and `test_generated_brief_passes_every_…` runs real
generated output through the validator's own functions.

**A refusal must name a mode it can actually detect.** So each refusal test
asserts the discriminating phrase, not merely a non-zero exit — a refusal for
the wrong reason is indistinguishable from the right one in an exit code.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
CLI = ROOT / "dev" / "brief.py"
sys.path.insert(0, str(ROOT / "dev"))

import brief  # noqa: E402
import dispatch_lane  # noqa: E402


# A minimal core that passes: substantive prose plus a direction-2 section with
# a body. Tests mutate a copy of this to isolate one refusal at a time.
GOOD_CORE = """## The defect, measured

`## Standing rules` was retyped 33 times and produced 32 distinct bodies.

## Direction 2 — construct these and run them

1. A core that is empty still emits.
2. A frame file with no sections still emits a brief that looks fine.
"""


def _this_branch() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture(scope="module")
def lane() -> str:
    """The branch this test tree is on — a real worktree, so no fixture git."""
    return _this_branch()


@pytest.fixture(scope="module")
def generated(lane: str) -> str:
    return brief.build(881, lane, ["dev/brief.py", "test_brief.py"], GOOD_CORE)


# --- the generator and the validator agree, without sharing a truth ---------

def test_inbox_prefix_matches_the_validators_literal_without_importing_it():
    """Drift between the two independent literals is a test failure, not a dispatch failure."""
    source = (ROOT / "dev" / "brief.py").read_text(encoding="utf-8")
    assert "from dispatch_lane import" not in source
    assert "import dispatch_lane" not in source, (
        "brief.py must not import the validator; sharing its notion of a valid "
        "brief would stop the validator witnessing a generator bug"
    )
    assert brief.COORDINATOR_INBOX_PREFIX == dispatch_lane.COORDINATOR_INBOX_PREFIX


def test_generated_brief_passes_every_dispatch_lane_refusal(generated, lane, tmp_path):
    """The whole point: generated output cannot fail dispatch validation."""
    contract = dispatch_lane.CONTRACT_PATH.read_text(encoding="utf-8")
    checkout = dispatch_lane._briefs_dir().parent.parent

    dispatch_lane.validate_prompt(generated, contract, checkout / "inbox.md")
    task, branch = dispatch_lane._identity(generated)
    assert (task, branch) == (881, lane)
    head = generated[: generated.find(contract)]
    assert dispatch_lane._worktree(head) == brief.worktree_for(lane)
    dispatch_lane.validate_base_sha(head, branch)
    persisted = dispatch_lane.persist_prompt(generated, tmp_path)
    assert persisted.read_text(encoding="utf-8") == generated


def test_base_sha_is_the_branch_point_the_validator_recomputes(generated, lane):
    stated = re.search(r"^Base sha: ([0-9a-f]{40})$", generated, re.MULTILINE)
    assert stated, "generated brief must carry a 40-hex Base sha line"
    merge_base = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "master", lane],
        capture_output=True, text=True, check=True).stdout.strip()
    assert stated.group(1) == merge_base


def test_lane_owns_is_emitted_and_parses_as_lint_reads_it(generated):
    """#465: a worktree brief with no `Lane-owns:` is a lint ERROR; 2 of 40 carried one."""
    import lint  # noqa: PLC0415
    assert lint._parse_lane_owns(generated) == ["dev/brief.py", "test_brief.py"]


def test_worktree_is_asked_of_git_not_guessed(lane):
    """A guessed convention would be wrong for 14 of the 40 most recent briefs (#846 moved it)."""
    assert brief.worktree_for(lane) == ROOT.resolve()
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.worktree_for("no-such-branch-in-any-worktree")
    assert "no worktree is checked out on branch" in str(excinfo.value)


# --- direction 2, construction 1: an EMPTY authored core still emits --------

def test_empty_core_is_refused(lane):
    for empty in ("", "   \n\n\t\n"):
        with pytest.raises(brief.BriefFault) as excinfo:
            brief.build(881, lane, ["dev/brief.py"], empty)
        assert "the authored core is empty" in str(excinfo.value)


# --- direction 2, construction 2: a PLACEHOLDER core still emits ------------

@pytest.mark.parametrize("core", [
    "TODO",
    "- TODO: describe the defect\n- TODO: the fix shape\n",
    "<describe the defect>\n\n<the direction-2 candidates>\n",
    "**TODO**\n\n...\n\n[fill in]\n",
    "## The defect\n\n## The fix shape\n\n## Direction 2\n",
])
def test_placeholder_core_is_refused(lane, core):
    """Placeholder-detection that only catches literally-empty is not enough."""
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], core)
    message = str(excinfo.value)
    assert ("no substantive line" in message or "has no body" in message), message


def test_a_copied_heading_with_no_body_is_refused_by_name(lane):
    core = GOOD_CORE + "\n## The fix shape\n\n## Verification\n\nRun the suite.\n"
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], core)
    assert "'## The fix shape' has no body" in str(excinfo.value)


def test_a_sentence_that_merely_mentions_todo_is_not_a_placeholder(lane):
    """Measured: the only placeholder tokens in 40 brief heads are #881's own prose.

    A token-level `contains("TODO")` refusal would reject the brief that
    commissioned this tool, so detection is line-shaped.
    """
    core = GOOD_CORE + (
        "\nA generator that emits a frame-with-`TODO`-core is a generator that "
        "will be used that way at 3am.\n")
    assert "TODO" in brief.build(881, _this_branch(), ["dev/brief.py"], core)


def test_a_core_with_no_direction_2_section_is_refused(lane):
    core = "## The defect, measured\n\nThe block was retyped 33 times.\n"
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], core)
    assert "names no direction-2 construction with a body" in str(excinfo.value)


def test_a_direction_2_heading_with_no_body_is_refused(lane):
    """The phrase alone is a token, not a statement (#699) — require a body after it."""
    core = "## The defect\n\nMeasured: 32 distinct bodies.\n\n## Direction 2\n"
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], core)
    assert "has no body" in str(excinfo.value)


# --- direction 2, construction 3: accepted by dispatch, carrying no rules ---

def test_a_frame_that_yields_no_sections_is_refused(lane, tmp_path):
    """Degrade to zero — the denominator assertion.

    A generator that finds nothing to template emits a brief that dispatch
    accepts and that carries no standing rules. `lessons.md`: *"a dispatch
    carrying no rules at all looks exactly like a healthy one"*.
    """
    empty_frame = tmp_path / "frame.md"
    empty_frame.write_text("# Frame\n\nProse with no `## ` sections at all.\n")
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], GOOD_CORE, frame_path=empty_frame)
    assert "yielded ZERO sections" in str(excinfo.value)


def test_the_no_rules_brief_would_otherwise_have_passed_dispatch(lane, tmp_path):
    """Prove the refusal above is load-bearing rather than belt-and-braces.

    Build the same brief with the frame step bypassed and show `dispatch_lane`
    accepts it. If dispatch refused it anyway, the denominator assertion would
    be redundant and this test would say so.
    """
    contract = dispatch_lane.CONTRACT_PATH.read_text(encoding="utf-8")
    checkout = dispatch_lane._briefs_dir().parent.parent
    full = brief.build(881, lane, ["dev/brief.py"], GOOD_CORE)
    ruleless = full.replace(
        "\n\n".join(brief.frame_sections(brief.FRAME_PATH.read_text())) + "\n\n", "")

    # Line-anchored: GOOD_CORE names `## Standing rules` in prose, and a
    # substring test would pass on the core's own sentence rather than on the
    # absence of the heading.
    head = ruleless[: ruleless.find(contract)]
    assert not re.search(r"^## Standing rules$", head, re.MULTILINE)
    assert re.search(r"^## Standing rules$", full, re.MULTILINE), (
        "the positive control: the unmodified brief DOES carry the heading, so "
        "the removal above is what the assertion above is reading"
    )
    dispatch_lane.validate_prompt(ruleless, contract, checkout / "inbox.md")
    dispatch_lane.validate_base_sha(ruleless[: ruleless.find(contract)], lane)
    dispatch_lane.persist_prompt(ruleless, tmp_path)


def test_the_frame_actually_carries_the_measured_rules():
    """A frame file with sections but no RULES degrades to zero one layer down."""
    sections = brief.frame_sections(brief.FRAME_PATH.read_text(encoding="utf-8"))
    assert len(sections) >= 3, sections
    titles = [section.splitlines()[0] for section in sections]
    assert "## Standing rules" in titles
    assert "## Live-state prohibitions — absolute" in titles
    rules = brief.FRAME_PATH.read_text(encoding="utf-8")
    for measured in (
        "You never merge and you never push",     # 33/33 of retyped blocks
        "Do not use `attn`",                      # 31/33
        "2 threads",                              # 29/33
        "`git commit --only <paths>`",            # 27/33
        "WARN ROW\nSET",                          # 14/33 — the one that drifted most
        "Rebase onto local `master`",             #  9/33
        "dev/lane_scratch.py",                    # 25/31
    ):
        assert measured.replace("\n", " ") in " ".join(rules.split()), measured


# --- the delivered prompt, not the intended one ----------------------------

def test_the_cli_delivers_the_whole_brief_on_stdout(tmp_path, lane):
    """Verify what a caller would actually receive, not what build() returned.

    `lessons.md` records a shell-quoting bug that delivered a 24-character
    prompt while every instrument read normal. The generator's output crosses a
    process boundary before it reaches `dispatch_lane`, so measure it there.
    """
    core_file = tmp_path / "core.md"
    core_file.write_text(GOOD_CORE, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CLI), "--task", "881", "--lane", lane,
         "--owns", "dev/brief.py", "--core", str(core_file)],
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == brief.build(881, lane, ["dev/brief.py"], GOOD_CORE)
    assert len(result.stdout) > 20_000, len(result.stdout)
    assert result.stdout.endswith(
        dispatch_lane.CONTRACT_PATH.read_text(encoding="utf-8").rstrip("\n") + "\n")


def test_the_cli_refuses_with_a_named_reason_and_writes_no_file(tmp_path, lane):
    core_file = tmp_path / "core.md"
    core_file.write_text("TODO\n", encoding="utf-8")
    out = tmp_path / "brief.md"
    result = subprocess.run(
        [sys.executable, str(CLI), "--task", "881", "--lane", lane,
         "--owns", "dev/brief.py", "--core", str(core_file), "--out", str(out)],
        capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "brief refused: the authored core has no substantive line" in result.stderr
    assert not out.exists(), "a refused brief must not leave a file behind"


# --- the remaining refusals -------------------------------------------------

def test_no_owns_is_refused(lane):
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, [], GOOD_CORE)
    assert "`Lane-owns:` mandatory" in str(excinfo.value)


def test_a_core_declaring_a_generated_field_is_refused(lane):
    """Two `Branch:` lines leave dispatch_lane unable to name the corpus artifact."""
    core = GOOD_CORE + "\nBranch: some-other-lane\n"
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], core)
    assert "declares Branch:, which this tool generates" in str(excinfo.value)


def test_an_unknown_task_is_refused_with_the_denominator(lane):
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(999_999, lane, ["dev/brief.py"], GOOD_CORE)
    message = str(excinfo.value)
    assert "#999999 not found" in message
    assert re.search(r"\((\d+) entries read\)", message), (
        "a not-found must state how many entries were read — a not-found "
        "against an empty ledger is a fact about the ledger (#667)"
    )


def test_an_empty_ledger_is_refused_rather_than_reported_as_not_found(tmp_path, lane):
    (tmp_path / ".dreamwork").mkdir()
    ledger = tmp_path / ".dreamwork" / "tasks.md"
    ledger.write_text("# Tasks\n\n## Open\n\n## Recently landed\n", encoding="utf-8")
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], GOOD_CORE, ledger=ledger)
    assert "holds NO entries at all" in str(excinfo.value)
