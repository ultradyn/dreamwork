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
        delivered = Path(f"/proc/{child}/cmdline").read_bytes().split(b"\0")
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
