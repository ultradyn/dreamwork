import importlib.util
import socket
import subprocess
import sys
from pathlib import Path

import pytest


CLI = Path(__file__).parent / "dev" / "bisect_guard.py"
SPEC = importlib.util.spec_from_file_location("bisect_guard", CLI)
bg = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = bg
SPEC.loader.exec_module(bg)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def valid_recipe(*tail: str) -> str:
    return "\n".join((
        'guards port="39899":',
        '    #!/usr/bin/env bash',
        '    audit_shape() {',
        '      _holder_line=$(ss -tlnp)',
        '      served=$(curl -sf "http://127.0.0.1:{{port}}/data.json")',
        '      if [ "$served" != "$OUT/target" ]; then return 1; fi',
        '      node "dev/capture/$g.mjs" "$OUT/$g" {{port}}',
        '      python3 lint.py guard-execution "$OUT" $GUARDS || fail=1',
        '    }',
        *tail,
        '',
    ))


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def revision_tree(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "master")
    for rel in ("watch.py", "lint.py"):
        (root / rel).write_text("# fixture\n")
    (root / "dev/capture/fixture").mkdir(parents=True)
    (root / "dev/capture/fixture/index.html").write_text("fixture\n")
    (root / "dev/capture/qroll.mjs").write_text("// fixture\n")
    (root / "justfile").write_text(valid_recipe())
    git(root, "add", ".")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "fixture")
    return root, git(root, "rev-parse", "HEAD")


def test_judged_pass_is_distinct_from_judged_failure():
    passed = "  PASS qroll\n"
    failed = "  FAIL qroll (exit 1)\n        FAIL persisted roll was lost\n"
    assert bg.classify_output(passed, 0, "qroll")[0] is bg.Verdict.PASS
    verdict, reason = bg.classify_output(failed, 1, "qroll")
    assert verdict is bg.Verdict.FAIL
    assert reason == "persisted roll was lost"


def test_crash_sentinel_is_did_not_judge_not_fail():
    output = (
        "  FAIL qroll (exit 1)\n"
        "        FAIL the guard threw before finishing its checks: missing .git\n")
    verdict, reason = bg.classify_output(output, 1, "qroll")
    assert verdict is bg.Verdict.DID_NOT_JUDGE
    assert "crashed before" in reason


def test_unclassified_nonzero_refuses_instead_of_guessing_failure():
    verdict, reason = bg.classify_output("Error: module missing\n", 1, "qroll")
    assert verdict is bg.Verdict.DID_NOT_JUDGE
    assert "without a complete judgement receipt" in reason


def test_unmet_guard_precondition_is_not_scored_as_behavioural_failure():
    output = (
        "  FAIL qroll (exit 1)\n"
        "        FAIL precondition: server named its target\n"
        "        FAIL persistence assertion that depends on that target\n")
    verdict, reason = bg.classify_output(output, 1, "qroll")
    assert verdict is bg.Verdict.DID_NOT_JUDGE
    assert reason == "guard precondition failed: precondition: server named its target"


def test_archive_without_git_cannot_judge(revision_tree, tmp_path):
    repo, sha = revision_tree
    archive = tmp_path / "archive"
    archive.mkdir()
    subprocess.check_call(
        ["bash", "-c", f"git -C '{repo}' archive {sha} | tar -x -C '{archive}'"])
    reason = bg.inspect_revision_tree(archive, sha, "qroll")
    assert reason == "revision tree has no .git; source-pinning guards cannot run"


def test_present_day_untracked_contamination_is_did_not_judge(revision_tree):
    repo, sha = revision_tree
    (repo / ".gitignore").write_text("client/dist/\n")
    git(repo, "add", ".gitignore")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "ignore dist")
    sha = git(repo, "rev-parse", "HEAD")
    dist = repo / "client/dist"
    dist.mkdir(parents=True)
    (dist / "present-day.js").write_text("// not from this revision\n")
    reason = bg.inspect_revision_tree(repo, sha, "qroll")
    assert reason is not None
    assert reason.startswith("revision tree is contaminated before the guard:")
    assert "client/" in reason


def test_exact_clean_revision_with_git_satisfies_preconditions(revision_tree):
    repo, sha = revision_tree
    assert bg.inspect_revision_tree(repo, sha, "qroll") is None


def test_comment_magic_and_echo_cannot_manufacture_a_judged_pass(revision_tree):
    repo, _sha = revision_tree
    (repo / "justfile").write_text(
        "# guard-execution; already held; is serving\n"
        "guards:\n"
        "    echo '  PASS qroll'\n")
    git(repo, "add", "justfile")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "fake gate")
    sha = git(repo, "rev-parse", "HEAD")

    result = bg.judge_revision(repo, sha, "qroll", free_port(), "guard preflight: OK [test]")

    assert result.verdict is bg.Verdict.DID_NOT_JUDGE
    assert result.reason == "historical guards recipe has no direct judged-guard gate"


def test_structural_recipe_check_does_not_claim_to_interpret_shell_semantics(revision_tree):
    repo, sha = revision_tree

    # audit_shape is never called: this is the explicit remaining false-green.
    assert bg.inspect_revision_tree(repo, sha, "qroll") is None


def test_any_did_not_judge_forces_bisect_skip_exit():
    preflight = "guard preflight: OK [fixture]"
    results = [
        bg.Result("a", "a" * 40, bg.Verdict.PASS, "judged", preflight),
        bg.Result("b", "b" * 40, bg.Verdict.DID_NOT_JUDGE, "contaminated", preflight),
    ]
    assert bg._exit_for(results, preflight) == 125


def test_red_under_caution_refuses_boundary_claim():
    preflight = "guard preflight: CAUTION [fixture]"
    result = bg.Result("b", "b" * 40, bg.Verdict.FAIL, "named failure", preflight)
    assert bg._exit_for([result], preflight) == 125


def test_green_under_caution_remains_usable():
    preflight = "guard preflight: CAUTION [fixture]"
    result = bg.Result("a", "a" * 40, bg.Verdict.PASS, "judged", preflight)
    assert bg._exit_for([result], preflight) == 0
