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

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
CLI = ROOT / "dev" / "brief.py"
sys.path.insert(0, str(ROOT / "dev"))

import brief  # noqa: E402
import dispatch_lane  # noqa: E402
import lint  # noqa: E402


# A minimal core that passes: substantive prose plus a direction-2 section with
# a body. Tests mutate a copy of this to isolate one refusal at a time.
GOOD_CORE = """## The defect, measured

`## Standing rules` was retyped 33 times and produced 32 distinct bodies.

## Direction 2 — construct these and run them

1. A core that is empty still emits.
2. A frame file with no sections still emits a brief that looks fine.
"""


def _indent(text: str) -> str:
    """Markdown-mode bodies sit indented under their `- **#id**` head line.

    Measured against `ledger._read_records`: an unindented body is dropped
    entirely, and the head line comes back INSIDE `body` in markdown mode but
    not in store mode — which is why `brief._core_of` exists.
    """
    return "\n".join(f"  {line}" if line.strip() else "" for line in text.splitlines())


@pytest.fixture(scope="module")
def lane_checkout(tmp_path_factory) -> tuple[str, Path]:
    """A real, fixture-owned lane, independent of the ambient checkout state."""
    name = f"brief-fixture-{os.getpid()}-{time.time_ns()}"
    path = tmp_path_factory.mktemp("brief-lane") / "worktree"
    ambient = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(ROOT), "worktree", "add", "-q", "-b", name, str(path), "HEAD"],
        check=True,
    )
    try:
        actual = brief.worktree_for(name)
        still_ambient = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert path.resolve() != ROOT.resolve() and still_ambient == ambient, (
            "ambient checkout branch coupling: the fixture must not attach or reuse "
            "the checkout running pytest"
        )
        assert actual == path.resolve(), (
            "ambient checkout branch coupling: the brief-test lane must be the "
            f"fixture-created worktree {path.resolve()}, got {actual}"
        )
        yield name, path.resolve()
    finally:
        subprocess.run(
            ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(path)],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(ROOT), "branch", "-D", name],
            check=True, capture_output=True, text=True,
        )
        assert not path.exists(), f"fixture lane worktree survived teardown: {path}"


@pytest.fixture(scope="module")
def lane(lane_checkout: tuple[str, Path]) -> str:
    """The real branch name created for this test module."""
    return lane_checkout[0]


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


def test_worktree_is_asked_of_git_not_guessed(lane, lane_checkout):
    """A guessed convention would be wrong for 14 of the 40 most recent briefs (#846 moved it)."""
    assert lane == lane_checkout[0], (
        "ambient checkout branch coupling: lane must come from the fixture-owned checkout"
    )
    assert brief.worktree_for(lane) == lane_checkout[1]
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.worktree_for("no-such-branch-in-any-worktree")
    assert "no worktree is checked out on branch" in str(excinfo.value)


def test_prepared_build_composes_before_the_worktree_exists(tmp_path):
    branch = "brief-prepared-936-does-not-exist"
    base = subprocess.run(
        ["git", "rev-parse", "master"], cwd=ROOT,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    expected = (tmp_path / "future-worktree").resolve()
    text = brief.build(
        881, branch, ["dev/brief.py"], GOOD_CORE,
        prepared_worktree=expected, prepared_base_sha=base,
    )
    assert f"Worktree: {expected}" in text
    assert f"Branch: {branch}" in text
    assert f"Base sha: {base}" in text


def _scope_fixture(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "widget.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "test_widget.py").write_text(
        "from pkg import widget\ndef test_widget(): assert widget.VALUE == 1\n",
        encoding="utf-8",
    )
    (tmp_path / "test_import_only.py").write_text(
        "from pkg import widget\ndef test_unrelated(): assert True\n",
        encoding="utf-8",
    )
    return tmp_path


def test_scope_report_names_an_import_derived_test_the_authored_scope_omits():
    report = brief._scope_derivation_report(
        ROOT, ["dev/land_lane.py", "test_land_lane.py"]
    )
    assert (
        "selected 2 existing test(s)" in report
        and "authored Lane-owns covered 1 of 2" in report
        and "1 omitted: test_suite_baseline.py" in report
    ), f"scope derivation lost omitted test_suite_baseline.py: {report}"


def test_scope_report_reads_the_base_tree_not_a_dirty_authored_checkout(tmp_path):
    root = _scope_fixture(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git", "-c", "user.name=brief-test", "-c",
            "user.email=brief-test@example.invalid", "commit", "-qm", "base",
        ],
        cwd=root, check=True,
    )
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    (root / "test_dirty_only.py").write_text(
        "from pkg import widget\ndef test_dirty_only(): assert widget.VALUE == 1\n",
        encoding="utf-8",
    )

    report = brief._base_scope_derivation_report(
        root, base, ["pkg/widget.py", "test_widget.py", "test_import_only.py"]
    )

    assert "selected 2 existing test(s)" in report, report
    assert "test_dirty_only.py" not in report, report


def test_scope_report_does_not_double_count_a_derived_test_already_named(tmp_path):
    root = _scope_fixture(tmp_path)
    report = brief._scope_derivation_report(
        root, ["pkg/widget.py", "test_widget.py", "test_import_only.py"]
    )
    assert "selected 2 existing test(s)" in report, report
    assert "authored Lane-owns covered 2 of 2; 0 omitted" in report, report


def test_scope_report_faults_when_a_source_file_derives_no_existing_test(tmp_path):
    (tmp_path / "worker.rs").write_text("fn main() {}\n", encoding="utf-8")
    with pytest.raises(brief.BriefFault) as excinfo:
        brief._scope_derivation_report(tmp_path, ["worker.rs"])
    message = str(excinfo.value)
    assert "scope derivation FAULT: selected 0 existing test(s)" in message, message
    assert "name=0 import=0 map=0" in message, message


def test_scope_report_reports_an_irrelevant_import_without_refusing(tmp_path):
    root = _scope_fixture(tmp_path)
    report = brief._scope_derivation_report(
        root, ["pkg/widget.py", "test_widget.py"]
    )
    assert "1 omitted: test_import_only.py" in report, report
    assert "This is a report, not an edit grant" in report, report


@pytest.mark.parametrize("owns", [["pkg/"], ["pkg/*.py"]])
def test_scope_report_does_not_treat_a_directory_or_glob_as_a_gate_diff(
    tmp_path, owns,
):
    _scope_fixture(tmp_path)
    report = brief._scope_derivation_report(tmp_path, owns)
    assert report.startswith("scope derivation NOT CHECKED"), report
    assert "found 0 existing non-inert files" in report, report


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


@pytest.mark.parametrize("prohibition", [
    "Do NOT edit any `.md` document.",
    "You must not edit any Markdown file.",
])
def test_blanket_markdown_prohibition_is_refused_by_meaning(lane, prohibition):
    core = GOOD_CORE + "\n## Scope\n\n" + prohibition + "\n"
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], core)
    assert "prohibits the whole Markdown-file class" in str(excinfo.value)
    assert ".dreamwork/inbox.md" in str(excinfo.value)


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
    assert "TODO" in brief.build(881, lane, ["dev/brief.py"], core)


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


# --- #947: the heading definition and the refusal message -------------------
#
# The house style opens a sentence with a task id (`#847 is the campaign`).
# A bare leading `#` was read as an ATX heading, so the section the line
# belonged to was left apparently empty and the refusal blamed the author for
# omitting text that was present. A heading requires `# ` (space) per CommonMark
# §4.2, and a fenced code block is never a heading — a brief whose job is to
# describe document structure must be able to quote Markdown.


def test_a_body_line_starting_with_hash_NNN_is_not_treated_as_a_heading(lane):
    """Direction 1, false-positive. core-847b measured: the body's first line
    `#847 is the whole campaign ...` read as a section opener, so the heading
    above it was refused for 'has no body'. `#NNN` is not a CommonMark ATX
    heading (no space after the opening `#`), so it is prose and must build."""
    core = GOOD_CORE + (
        "\n## Read the ledger entry for #847 first\n\n"
        "#847 is the whole campaign and it is long. #937 is the increment.\n")
    out = brief.build(881, lane, ["dev/brief.py"], core)
    assert "#847 is the whole campaign" in out


def test_a_real_ATX_heading_inside_a_code_fence_is_not_a_section(lane):
    """Direction 1, false-positive, the third measured instance. A fenced
    quotation of Markdown (``## Read ...``) was counted as a section of the
    brief and refused. The fence was ignored and the real heading inside it
    was honoured; fenced blocks are content, never section openers.

    The fixture is shaped to discriminate fence handling from the heading-space
    rule: the fence holds TWO consecutive ATX headings with no prose between.
    Heading-space alone cannot save this — only fence tracking does, because a
    heading followed immediately by a heading is exactly the empty-section shape
    the refusal keys on. A fence-disabled build flags `## Inside` as empty."""
    core = GOOD_CORE + (
        "\n## What happens, measured\n\n"
        "Two instances tonight. The verbatim failing example:\n\n"
        "```markdown\n"
        "## Inside a fence\n\n"
        "## After, still fenced\n\n"
        "Both are quotation, never sections of the brief.\n"
        "```\n\n"
        "The first was a genuine defect; the second was this misparse.\n")
    out = brief.build(881, lane, ["dev/brief.py"], core)
    assert "## Inside a fence" in out


def test_a_genuinely_empty_section_is_still_refused_and_names_what_it_saw(lane):
    """Direction 1, the keep-case. The real empty-section refusal caught a
    genuine defect in a core tonight and must survive the fix. A heading
    followed by another heading with no prose between is still refused, and
    the message names BOTH the empty heading and the line that revealed it
    (#940: a refusal names what it observed, not only the condition)."""
    core = GOOD_CORE + "\n## The fix shape\n\n## Verification\n\nRun the suite.\n"
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], core)
    message = str(excinfo.value)
    assert "'## The fix shape' has no body" in message, message
    assert "## Verification" in message, message


# --- #952: an unclosed fence must not silently end the section walk ---------
#
# #947 made the walk track fences so a quoted heading is not read as a section.
# The tracking keys on an opener setting in_fence and a closer clearing it; a
# fence that opens and never closes left in_fence true to end-of-core, so every
# later line was skipped and any empty sections after it passed UNNOTICED.
# Master before #947 LOUDLY false-positived on quoted headings; #947 converted
# that into a SILENT acceptance for the rest of the core. Loud-and-wrong became
# quiet-and-wrong (#952). The walk must now refuse, naming the opening line and
# the closing delimiter (#940).


def test_an_unclosed_code_fence_is_refused_and_names_the_line_and_remedy(lane):
    """Direction 1, the hole #947 opened. The discriminating pair from #952:
    two cores identical except whether the fence closes. The unclosed one must
    REFUSE, and the refusal must name the line the fence opened on plus the
    remedy (a line of N backticks/tildes), not only the condition (#940).

    The opening line is derived from the fixture, not pinned: a literal tuned
    to today's fixture is a check with an expiry date, and the line number is
    exactly the load-bearing detail this refusal exists to report."""
    tail = (
        "\n## What happens, measured\n\n"
        "Prose before the fence, so the section carries a body.\n\n"
        "```markdown\n"
        "## quoted, not a section\n"
        "\n"
        "## Empty after the open fence\n"
        "\n"
        "## Also empty\n")
    core = GOOD_CORE + tail
    fence_line = core.splitlines().index("```markdown") + 1  # 1-based, as the walk numbers
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], core)
    message = str(excinfo.value)
    assert "opens a fenced code block" in message, message
    assert f"line {fence_line}" in message, message
    assert "never closes it" in message, message
    assert "3 backtick" in message, message          # the remedy names the delimiter


def test_unclosed_and_closed_fences_refuse_for_different_reasons(lane):
    """The two refusals must READ differently. A red for the wrong reason is
    indistinguishable from the right one in a -q summary. The closed fence is
    refused for the ordinary empty-section reason (it swallowed nothing); the
    unclosed fence is refused for the fence itself, and neither message is the
    other's."""
    head = GOOD_CORE + "\n## Around the fence\n\nProse before it.\n\n"
    empties = "## Empty A\n\n## Empty B\n\n## Closer\n\nProse after.\n"
    closed = head + "```markdown\n## quoted\n```\n\n" + empties
    unclosed = head + "```markdown\n## quoted\n" + empties
    with pytest.raises(brief.BriefFault) as closed_exc:
        brief.build(881, lane, ["dev/brief.py"], closed)
    with pytest.raises(brief.BriefFault) as open_exc:
        brief.build(881, lane, ["dev/brief.py"], unclosed)
    closed_msg, open_msg = str(closed_exc.value), str(open_exc.value)
    assert "sections with no body" in closed_msg and "## Empty A" in closed_msg, closed_msg
    assert "opens a fenced code block" in open_msg and "never closes it" in open_msg, open_msg
    assert closed_msg != open_msg


def test_a_closed_fence_quoting_headings_still_passes():
    """#947's coverage must survive. A properly closed fence that quotes real
    ATX headings (with no prose between them) is content, not structure, and a
    core that quotes it still validates. Losing this would be the worst outcome
    here — it is the false positive #947 exists to fix. validate_core is the
    production seam; calling it directly is the real function, not a double."""
    core = (
        "## The defect, measured\n\n"
        "Real prose so the section has substance.\n\n"
        "## Direction 2 - construct these and run them\n\n"
        "```markdown\n"
        "## Inside a fence\n\n"
        "## After, still fenced\n"
        "```\n\n"
        "1. A closed fence quotes headings without opening sections.\n")
    # The two fenced headings are NOT counted: they are quotation, not sections
    # (#947). Only the two real headings outside the fence are examined.
    assert brief.validate_core(core) == 2


def test_validate_core_returns_the_section_count_on_success():
    """#868: the denominator must be visible on every path, including the happy
    one. validate_core returns how many ATX sections it examined so a caller
    can print it; a run that examined zero must not read like one that examined
    forty and found them all written."""
    core = (
        "## One\n\nBody.\n\n"
        "## Direction 2 - construct these\n\n"
        "1. a case.\n\n"
        "## Two\n\nBody.\n")
    assert brief.validate_core(core) == 3


def test_brief_generation_reports_an_uncovered_headline_beside_a_covered_claim(capsys):
    core = (
        "## Verify the premises\n\n"
        "17 recipes are registered.\n\n"
        "`just --summary | wc -w`\n\n"
        "## The surviving gap\n\n"
        "5 recipes carry a setting whose meaning was not re-derived.\n\n"
        "## Direction 2 - construct these\n\n"
        "A word-form count can escape the scan.\n"
    )
    assert brief.validate_core(core) == 3
    report = capsys.readouterr().err
    assert "1 uncovered: line 9 '5 recipes'" in report, (
        f"quantity verification lost uncovered 5 recipes: {report}"
    )
    assert "found 2 asserted quantities" in report, report
    assert "covered 1 of 2" in report, report


def test_quantity_report_zero_population_is_not_all_verified():
    report = brief._quantity_verification_report(
        "## Verify premises\n\nNo decimal quantities here.\n"
    )
    assert "NOT CHECKED: found 0 asserted quantities" in report, report
    assert "covered 0 of 0" in report, report
    assert "not an all-verified result" in report, report


def test_quantity_report_excludes_identifier_and_evidence_number_shapes():
    core = (
        "## Verify premises\n\n"
        "Task #972 at lint.py:5781 used v2.3 on 2026-08-02 and reached 40%.\n"
        "The estimate was ~200 lines and the grouped value was 1,300.\n"
        "> Past refusal: 13 recipes were claimed.\n\n"
        "```text\n17 is expected output, not an assertion\n```\n"
    )
    report = brief._quantity_verification_report(core)
    assert "found 0 asserted quantities" in report, report


def test_quantity_report_requires_local_coverage_inside_the_verification_block():
    core = (
        "## Verify premises\n\n"
        "11 files are affected.\n\n"
        "This paragraph separates the claim from the unrelated command.\n\n"
        "`find . -type f | wc -l`\n"
    )
    report = brief._quantity_verification_report(core)
    assert "covered 0 of 1" in report, report
    assert "line 3 '11 files'" in report, report


def test_quantity_report_states_that_adjacent_coverage_is_not_semantic_proof():
    core = (
        "## Verify premises\n\n"
        "13 recipes are registered.\n\n"
        "`grep -c pipefail justfile`\n"
    )
    report = brief._quantity_verification_report(core)
    assert "covered 1 of 1; 0 uncovered" in report, report
    assert "does not verify that a command can produce the claimed quantity" in report


def test_quantity_report_detects_bare_range_ends_but_not_word_or_grouped_counts():
    report = brief._quantity_verification_report(
        "## Premises\n\n"
        "The change teaches 4 to 6 lessons, thirteen recipes, and 1,300 files.\n"
    )
    assert "found 2 asserted quantities" in report, report
    assert "line 3 '4'" in report and "line 3 '6 lessons'" in report, report


def test_blocking_report_finds_a_prose_stop_condition_without_a_numbered_list():
    report = brief._blocking_number_report(
        "Stop if this is not 254 branches; the premise would no longer hold."
    )

    assert "line 1 '254 branches' justification claim MISSING" in report, (
        f"blocking report lost 254 branches: {report}"
    )
    assert "found 1 blocking number(s)" in report, report
    assert "covered 0 of 1" in report, report
    assert "State: presented with unjustified blocking numbers" in report, report


def test_blocking_report_reads_the_house_blocking_section_and_stops_at_context():
    core = (
        "**BLOCKING — these findings are invariant:**\n\n"
        "1. The forbidden prefix count is **0**.\n"
        "2. The stale record count is **0**.\n\n"
        "Direction 1 must name the omitted blocking number.\n\n"
        "**NOT BLOCKING — context only:** around 15 worktrees. Do not stop if it moves.\n"
    )

    report = brief._blocking_number_report(core)

    assert "found 2 blocking number(s)" in report, report
    assert "covered 2 of 2" in report, report
    assert "line 3 '0'" in report and "line 4 '0'" in report, report
    assert "15 worktrees" not in report, report


def test_blocking_report_never_treats_a_justification_claim_as_correctness():
    report = brief._blocking_number_report(
        "Dispatching will not change this invariant.\n"
        "Stop if there are not 15 worktrees.\n"
    )

    assert "covered 1 of 1" in report, report
    assert "justification claim PRESENT" in report, report
    assert "Justification correctness is NOT CHECKED" in report, report
    assert "which of these can the act of dispatching change?" in report, report


def test_blocking_report_zero_population_is_not_all_justified():
    report = brief._blocking_number_report(
        "Three findings are described in words, with no numeric stop-condition."
    )

    assert "NOT CHECKED: found 0 blocking numbers" in report, report
    assert "covered 0 of 0" in report, report
    assert "State: no blocking numbers presented" in report, report
    assert "not an all-justified result" in report, report


def test_validate_core_reports_but_does_not_certify_a_false_invariance(capsys):
    core = GOOD_CORE + (
        "\nThis is invariant because the brief says so.\n"
        "Stop if there are not 15 worktrees.\n"
    )

    assert brief.validate_core(core) == 2
    report = capsys.readouterr().err
    assert "found 1 blocking number(s)" in report, report
    assert "invariance justification claims covered 1 of 1" in report, report
    assert "Justification correctness is NOT CHECKED" in report, report


def _citation_ledger(tmp_path: Path) -> Path:
    dreamwork = tmp_path / ".dreamwork"
    dreamwork.mkdir()
    ledger = dreamwork / "tasks.md"
    ledger.write_text(
        "# Tasks\n\n## Open\n\n"
        "- **#140** — **DECIDED**: show the deployed revision, no deploy hook\n"
        "  instead show the SHA being served so a stale view announces itself\n\n"
        "- **#141** — Calm grey is genuinely empty\n\n"
        "## Recently landed\n",
        encoding="utf-8",
    )
    return ledger


def test_citation_report_places_the_real_title_beside_a_high_overlap_wrong_gloss(
    tmp_path,
):
    ledger = _citation_ledger(tmp_path)
    core = "- **#140** — show a loud wrong state, so an unavailable check looks checked."

    report = brief._citation_authority_report(core, ledger)

    assert "#140 RESOLVED" in report, (
        f"citation #140 was not reported as resolved: {report}"
    )
    assert "show a loud wrong state" in report
    assert "DECIDED**: show the deployed revision, no deploy hook" in report
    assert "Semantic agreement is NOT CHECKED and requires human judgment" in report


def test_citation_report_distinguishes_unresolvable_from_resolved(tmp_path):
    ledger = _citation_ledger(tmp_path)
    core = (
        "- **#140** — stale views announce themselves.\n"
        "- **#999999** — this authority does not exist.\n"
    )

    report = brief._citation_authority_report(core, ledger)

    assert "resolved 1; unresolvable 1" in report
    assert "#140 RESOLVED" in report
    assert "#999999 UNRESOLVABLE" in report
    assert "no ledger title" in report


def test_citation_report_zero_population_is_not_all_verified(tmp_path):
    ledger = _citation_ledger(tmp_path)
    core = (
        "A bare #140 reference carries no gloss.\n"
        "`#140 — inline code is evidence, not an authority claim`\n"
        "https://example.test/#140 — a URL fragment is not a citation.\n"
        "```text\n#140 — fenced code is not a citation.\n```\n"
    )

    report = brief._citation_authority_report(core, ledger)

    assert "citation authority NOT CHECKED" in report
    assert "found 0 task citations" in report
    assert "not an all-verified result" in report


def test_citation_report_resolves_an_entry_with_no_note(tmp_path):
    ledger = _citation_ledger(tmp_path)

    report = brief._citation_authority_report(
        "#141: an author supplied gloss despite an empty task note.", ledger
    )

    assert "#141 RESOLVED" in report
    assert "ledger title 'Calm grey is genuinely empty'" in report


def test_tool_verb_check_refuses_an_unknown_master_verb_by_name(capsys):
    core = GOOD_CORE + "\nRun `dev/ledger.py definitely-not-a-verb 979`.\n"
    try:
        brief.validate_core(core)
    except brief.BriefFault as exc:
        message = str(exc)
    else:
        pytest.fail("dev/ledger.py definitely-not-a-verb was accepted")
    assert "tool verb check ERROR" in message, message
    assert "dev/ledger.py" in message, message
    assert "'definitely-not-a-verb'" in message, message
    assert "examined 1 invocation(s), 1 derivable, 0 not derivable" in message, message
    assert capsys.readouterr().err == ""


def test_argparse_and_documented_subcommand_surfaces_resolve_on_master(capsys):
    core = GOOD_CORE + (
        "\nRun `ledger.py get 979`, then persist with "
        "`dev/lane_scratch.py write proof.txt`.\n"
    )
    assert brief.validate_core(core) == 2
    report = capsys.readouterr().err
    assert "tool verb check OK" in report, report
    assert "examined 2 invocation(s), 2 derivable, 0 not derivable" in report, report
    assert "argparse choices: ledger.py" in report, report
    assert "documented subcommands: dev/lane_scratch.py" in report, report


def test_documented_subcommand_surface_rejects_an_unknown_verb(capsys):
    core = GOOD_CORE + "\nRun `dev/lane_scratch.py definitely-not-a-verb proof.txt`.\n"
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.validate_core(core)
    message = str(excinfo.value)
    assert "dev/lane_scratch.py" in message, message
    assert "'definitely-not-a-verb'" in message, message
    assert "examined 1 invocation(s), 1 derivable, 0 not derivable" in message, message
    assert capsys.readouterr().err == ""


def test_underivable_surface_is_not_checked_and_does_not_refuse(capsys):
    core = GOOD_CORE + "\nRun `dev/brief.py imaginary-verb`.\n"
    assert brief.validate_core(core) == 2
    report = capsys.readouterr().err
    assert "tool verb check NOT CHECKED" in report, report
    assert "examined 1 invocation(s), 0 derivable, 1 not derivable" in report, report
    assert "the 1 were NOT CHECKED" in report, report
    assert "not derivable: dev/brief.py" in report, report


def test_existing_verb_does_not_claim_to_validate_arguments_or_interpreter(capsys):
    core = GOOD_CORE + (
        "\n`dev/ledger.py get` has a real verb but an invalid argument shape.\n"
        "Run `/home/xertrov/.llm-general/skills/ud-dreamwork/dev/ledger.py get 979`; "
        "that skill-dir path still selects the main checkout's interpreter.\n"
    )
    assert brief.validate_core(core) == 2
    report = capsys.readouterr().err
    assert "examined 2 invocation(s), 2 derivable, 0 not derivable" in report, report


def test_fenced_and_quoted_non_commands_are_not_tool_invocations(capsys):
    core = GOOD_CORE + (
        "\nThe refusal said \"dev/ledger.py definitely-not-a-verb is invalid\".\n"
        "The lane must not run this fenced example:\n"
        "```sh\n"
        "dev/ledger.py definitely-not-a-verb 979\n"
        "```\n"
    )
    assert brief.validate_core(core) == 2
    report = capsys.readouterr().err
    assert "examined 0 invocation(s), 0 derivable, 0 not derivable" in report, report


def test_all_empty_sections_are_reported_not_just_the_first(lane):
    """Direction 1, enumerate. core-847b cost two launch cycles because the
    refusal named one empty section; the author fixed it, relaunched, and hit
    another. Report EVERY offender, and print the denominator so a run that
    examined zero sections cannot read as a clean pass (#868)."""
    core = (
        "## The defect, measured\n\n"
        "Real prose here so the core carries substance.\n\n"
        "## Empty one\n\n"
        "## Direction 2 — construct these\n\n"
        "1. A case that is real.\n\n"
        "## Empty two\n\n"
        "## Closer\n\n"
        "Also real prose, for substance.\n")
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(881, lane, ["dev/brief.py"], core)
    message = str(excinfo.value)
    assert "'## Empty one'" in message, message
    assert "'## Empty two'" in message, message
    # denominator visible — "N of M sections" — so zero-examined is detectable
    assert re.search(r"\d+\s+of\s+\d+\s+sections", message), message


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


def test_the_frame_tells_a_lane_what_warn_means_before_the_gate_refuses_it():
    """#945 — a check that emits a PERMANENT WARN row cannot land: the merge
    gate's lint-comparison refuses any added WARN row (the row-set rule, #794),
    and a lane had no way to learn that until the gate refused its finished work
    — #936 hit exactly this, and the repair was to move the names into an OK
    row. The frame reaches every dispatched lane (`dev/launch_lane.py` calls
    `brief.build()`), so the rule belongs there.

    Deleting the sentences this pins must fail this test by name, not silently:
    this frame already lost a load-bearing instruction that way (#936, where a
    badly-scoped prohibition suppressed ten lanes' dreams). The check pins
    CO-OCCURRENCE in one bullet rather than scattered mentions — a containment
    check over mentions spread across the frame is exactly the #836 false-green.
    """
    frame = brief.FRAME_PATH.read_text(encoding="utf-8")
    # Group each `- ` bullet with its 2-space-indented continuation lines, so a
    # multi-line rule reads as one unit a co-occurrence check can judge whole.
    bullets: list[str] = []
    current: list[str] | None = None
    for line in [*frame.splitlines(), ""]:
        if line.startswith("- "):
            if current is not None:
                bullets.append(" ".join(current))
            current = [line]
        elif current is not None and line.startswith("  ") and line.strip():
            current.append(line)
        elif current is not None:
            bullets.append(" ".join(current))
            current = None
    flat_bullets = [" ".join(b.split()) for b in bullets]
    assert len(flat_bullets) >= 20, (
        f"denominator: the frame must carry its standing-rule bullets, not "
        f"{len(flat_bullets)} — a co-occurrence check over an empty frame "
        f"reads the same as one over a complete frame (#868)"
    )
    warn_rule = [b for b in flat_bullets
                 if "transient condition someone will clear" in b]
    assert len(warn_rule) == 1, (
        f"expected exactly one standing-rule bullet stating WARN means a "
        f"transient condition; found {len(warn_rule)} — the rule must be one "
        f"coherent instruction, not mentions scattered across bullets that a "
        f"containment check would pass on (#836/#945)"
    )
    for needle in ("OK row that names it", "added WARN row", "unlandable"):
        assert needle in warn_rule[0], (
            f"the WARN-meaning bullet lost '{needle}' — deleting this sentence "
            f"must fail this test by name, not silently (#936/#945). The bullet "
            f"is:\n{warn_rule[0]}"
        )


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


def _sandbox_dispatch(tmp_path: Path, lane: str) -> tuple[Path, Path, str]:
    """A throwaway repo holding dispatch_lane, so nothing touches the live corpus."""
    root = tmp_path / "repo"
    base_branch = f"{lane}-brief-test-base"
    (root / "dev").mkdir(parents=True)
    (root / "briefs").mkdir()
    dispatch_copy = root / "dev" / "dispatch_lane.py"
    shutil.copy2(ROOT / "dev" / "dispatch_lane.py", dispatch_copy)
    source = dispatch_copy.read_text(encoding="utf-8")
    source, changed = source.replace(
        '"merge-base", "master", branch_commit',
        f'"merge-base", {base_branch!r}, branch_commit'), source.count(
            '"merge-base", "master", branch_commit')
    assert changed == 1, (
        f"sandbox base adaptation found {changed} dispatch merge-base calls, expected 1"
    )
    dispatch_copy.write_text(source, encoding="utf-8")
    for name in ("lane_liveness.py", "worktree_paths.py", "ledger_store.py"):
        shutil.copy2(ROOT / name, root / name)
    shutil.copytree(ROOT / "dreamwork_db", root / "dreamwork_db")
    shutil.copy2(ROOT / "briefs" / "boilerplate.md", root / "briefs" / "boilerplate.md")
    subprocess.run(["git", "init", "-q", "-b", base_branch, str(root)], check=True)
    subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.invalid",
         "commit", "--allow-empty", "-qm", "base"], cwd=root, check=True)
    (root / ".dreamwork").mkdir()
    (root / ".dreamwork" / "tasks.md").write_text(
        "# Tasks\n\n## Open\n\n- **#881** generated\n\n## Recently landed\n", encoding="utf-8")
    return root / "dev" / "dispatch_lane.py", root, base_branch


def _reanchor(
        generated: str, root: Path, lane: str, base_branch: str) -> tuple[str, Path]:
    """Point a generated brief at the sandbox, changing ONLY the identity lines.

    Everything this test reads — the frame sections and the appended contract —
    is the generator's output untouched. The identity lines are already bound
    against the real validator by
    ``test_generated_brief_passes_every_dispatch_lane_refusal``.
    """
    assert base_branch != lane, (
        f"sandbox branch collision: base and lane both name {lane!r}; "
        "the sandbox base must be distinct from the real lane name"
    )
    subprocess.run(["git", "branch", lane, base_branch], cwd=root, check=True)
    base = subprocess.run(["git", "merge-base", base_branch, lane], cwd=root,
                          check=True, capture_output=True, text=True).stdout.strip()
    worktree = root / ".worktrees" / lane
    worktree.mkdir(parents=True)
    text, changed = generated, 0
    for pattern, replacement in (
        (r"^Worktree: .*$", f"Worktree: {worktree}"),
        (r"^Base sha: .*$", f"Base sha: {base}"),
        (r"^Coordinator inbox — ABSOLUTE path.*$",
         f"{brief.COORDINATOR_INBOX_PREFIX}{root / '.dreamwork' / 'inbox.md'}"),
    ):
        text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
        changed += count
    assert changed == 3, f"re-anchoring rewrote {changed} identity lines, expected 3"
    assert re.search(r"^## Standing rules$", text, re.MULTILINE), (
        "precondition: re-anchoring must leave the generated frame intact"
    )
    return text, worktree


def test_the_delivered_argv_carries_the_standing_rules(tmp_path, lane):
    """Direction 2, construction 3 — verify what the runner GOT, not what we sent.

    `lessons.md`: *"a dispatch carrying no rules at all looks exactly like a
    healthy one"* — a shell-quoting bug once delivered a 24-character prompt and
    every instrument read normal. `dispatch_lane` appends the brief as one argv
    item, so `/proc/<pid>/cmdline` is the only authoritative record of it.

    No real lane is dispatched: the runner is `sleep`, in a throwaway repo.
    """
    cli, root, base_branch = _sandbox_dispatch(tmp_path, lane)
    generated = brief.build(881, lane, ["dev/brief.py"], GOOD_CORE)
    # Same branch NAME in the sandbox, so the generator's own `Branch:` line
    # survives re-anchoring untouched and stays part of what is measured.
    anchored, worktree = _reanchor(generated, root, lane, base_branch)
    generated_branch = re.search(r"^Branch: .+$", generated, re.MULTILINE)
    anchored_branch = re.search(r"^Branch: .+$", anchored, re.MULTILINE)
    assert generated_branch and anchored_branch
    assert anchored_branch.group(0) == generated_branch.group(0) == f"Branch: {lane}", (
        "re-anchoring must preserve the generator's real Branch: output verbatim"
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text(anchored, encoding="utf-8")

    process = subprocess.Popen(
        [sys.executable, str(cli), "--prompt", str(prompt), "--",
         sys.executable, "-c", "import time; time.sleep(60)"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, env={**os.environ, "DREAMWORK_ALLOW_PIPED_STDOUT": "1"})
    try:
        lock = worktree / ".dreamwork" / "lane.lock"
        for _ in range(250):
            if lock.is_file():
                break
            time.sleep(0.02)
        else:
            raise AssertionError(f"dispatch never wrote {lock}: {process.stderr.read()}")
        import json  # noqa: PLC0415
        child = json.loads(lock.read_text(encoding="utf-8"))["pid"]
        os.kill(child, 0)
        # Wait for the cmdline to be POPULATED, not merely for the pid to
        # exist.  `os.kill(pid, 0)` succeeds from the moment of fork, but
        # `/proc/<pid>/cmdline` reads EMPTY across the execve window: the
        # kernel swaps the mm_struct and `arg_start`/`arg_end` are briefly
        # zero.  Under full-suite load that window gets hit, and the failure
        # presents as `argv carried 0 brief items: [b'']` — which reads as a
        # delivery defect and is not one.  Measured: the identical tree passed
        # 1521/1521 in one gate run and failed this one test in the next, and
        # passes 5/5 in isolation.
        #
        # This does NOT weaken the assertion.  A genuine delivery failure
        # yields a POPULATED argv that lacks the brief, so it still fails
        # below; only the empty-cmdline exec window is waited out, and an
        # exhausted budget still fails with the same diagnostic.
        for _ in range(250):
            delivered = Path(f"/proc/{child}/cmdline").read_bytes().split(b"\0")
            if any(delivered):
                break
            time.sleep(0.02)
        else:
            raise AssertionError(
                f"/proc/{child}/cmdline stayed empty for 5s: the runner never "
                f"finished exec (stderr: {process.stderr.read()!r})")
    finally:
        process.wait(timeout=30)

    try:
        payload = [item for item in delivered if item.startswith(b"# Task #881")]
        assert len(payload) == 1, f"argv carried {len(payload)} brief items: {delivered!r}"
        text = payload[0].decode("utf-8")
        assert text == anchored, (
            f"delivered {len(text)} bytes, sent {len(anchored)} — the runner did "
            "not receive the brief that was validated"
        )
        assert re.search(r"^## Standing rules$", text, re.MULTILINE)
        assert re.search(r"^## Live-state prohibitions — absolute$", text, re.MULTILINE)
        assert "You never merge and you never push" in text
        assert text.rstrip("\n").endswith(
            dispatch_lane.CONTRACT_PATH.read_text(encoding="utf-8").rstrip("\n"))
    finally:
        os.kill(child, 9)


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


def test_core_from_task_lifts_the_body_and_still_validates_it(lane, tmp_path):
    """The storage answer, executed: the task body IS the authored core's home.

    No draft-prompt column and no second store — and lifting is not templating,
    because `validate_core` still runs on what was lifted. A record with no
    direction-2 reasoning is refused exactly as a hand-written core would be.
    """
    (tmp_path / ".dreamwork").mkdir()
    ledger = tmp_path / ".dreamwork" / "tasks.md"
    rich = ("## The defect\n\nRetyped 33 times, 32 distinct bodies.\n\n"
            "## Direction 2\n\nA check that reads its own fixture cannot fail.\n")
    thin = "Make the thing faster. It is slow.\n"
    ledger.write_text(
        "# Tasks\n\n## Open\n\n"
        f"- **#901** rich record\n\n{_indent(rich)}\n"
        f"- **#902** thin record\n\n{_indent(thin)}\n"
        "\n## Recently landed\n", encoding="utf-8")

    lifted = brief.core_from_task(901, ledger)
    assert "Direction 2" in lifted and "32 distinct bodies" in lifted
    assert re.search(r"^## Direction 2$", brief.build(
        901, lane, ["dev/brief.py"], lifted, ledger=ledger), re.MULTILINE)

    with pytest.raises(brief.BriefFault) as excinfo:
        brief.build(902, lane, ["dev/brief.py"],
                    brief.core_from_task(902, ledger), ledger=ledger)
    assert "names no direction-2 construction" in str(excinfo.value)


def test_core_from_task_refuses_an_empty_body(lane, tmp_path):
    (tmp_path / ".dreamwork").mkdir()
    ledger = tmp_path / ".dreamwork" / "tasks.md"
    ledger.write_text("# Tasks\n\n## Open\n\n- **#903** titled but bodyless\n\n"
                      "## Recently landed\n", encoding="utf-8")
    with pytest.raises(brief.BriefFault) as excinfo:
        brief.core_from_task(903, ledger)
    assert "carries no body beyond its title" in str(excinfo.value)


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


def _dream_rows(tmp_path: Path, documents: dict[str, str]):
    briefs = tmp_path / ".dreamwork" / "docs" / "briefs"
    briefs.mkdir(parents=True)
    for name, text in documents.items():
        (briefs / name).write_text(text, encoding="utf-8")
    rep = lint.Report()
    lint.check_brief_dream_contradictions(tmp_path / ".dreamwork", rep)
    return rep.rows


def test_brief_dream_lint_catches_semantic_variant_and_prints_denominators(tmp_path):
    rows = _dream_rows(tmp_path, {
        "safe.md": "Do not edit `.dreamwork/docs/plan.md`.\n",
        "bad.md": (
            "Something beyond the result? Write `.dreamwork/dreams/x.md`.\n\n"
            "You must not edit any Markdown file.\n"
        ),
    })
    coverage = [detail for level, what, detail in rows
                if level == lint.OK and what == "brief dream rules"]
    errors = [detail for level, _, detail in rows if level == lint.ERROR]
    assert coverage == [
        "examined 2 brief(s); 1 carry the dream-file instruction; 1 carry both "
        "instruction and blanket Markdown prohibition"
    ]
    assert errors == [
        "bad.md instructs .dreamwork/dreams/ but prohibits the Markdown-file "
        "class needed to obey it"
    ]


def test_brief_dream_lint_zero_population_is_loud(tmp_path):
    rows = _dream_rows(tmp_path, {})
    assert rows == [(lint.ERROR, "brief dream rules",
                     "examined 0 brief(s); 0 carry the dream-file instruction; "
                     "0 carry both instruction and blanket Markdown prohibition")]


def test_a_quoted_direction_2_specimen_is_not_an_active_prohibition(tmp_path):
    rows = _dream_rows(tmp_path, {
        "candidate.md": (
            "Write `.dreamwork/dreams/x.md`.\n\n"
            "A false-green candidate says \"do not edit any Markdown file\".\n"
        ),
    })
    assert not [row for row in rows if row[0] == lint.ERROR], rows
    assert "0 carry both" in rows[0][2]


def test_the_nine_measured_artifacts_are_evidence_not_a_permanent_red(tmp_path):
    contradiction = (
        "Write `.dreamwork/dreams/x.md`.\n\n"
        "Do not edit any Markdown file.\n"
    )
    rows = _dream_rows(tmp_path, {
        "930-cx-930pathdepth.md": contradiction,
        "930-a-future-reuse.md": contradiction,
    })
    warns = [detail for level, _, detail in rows if level == lint.WARN]
    errors = [detail for level, _, detail in rows if level == lint.ERROR]
    oks = [detail for level, _, detail in rows if level == lint.OK]
    # Not a permanent RED, and not a permanent WARN either: `land_lane.py`'s
    # lint-comparison phase refuses any ADDED WARN row, and these briefs are
    # evidence that never gets rewritten — so a per-file WARN would make this
    # check unlandable by construction. The names still have to be reported.
    assert warns == [], warns
    assert any("930-cx-930pathdepth.md" in detail
               and "do not rewrite" in detail for detail in oks), oks
    assert errors == [
        "930-a-future-reuse.md instructs .dreamwork/dreams/ but prohibits the "
        "Markdown-file class needed to obey it"
    ]


def test_brief_py_output_does_not_trip_the_dream_lint(tmp_path, generated):
    rows = _dream_rows(tmp_path, {"generated.md": generated})
    assert not [row for row in rows if row[0] == lint.ERROR], rows
    assert "examined 1 brief(s)" in rows[0][2]
