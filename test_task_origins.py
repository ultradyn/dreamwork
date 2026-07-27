"""#216 — first-seen origin parsing over the ledger's git history.

Every test builds a REAL temporary git repository and snapshots
`.dreamwork/tasks.md` through it, because the thing under test is a claim
about history: an origin is read from the FIRST snapshot where an id
appears in a leading bold task token, and no later edit may retroactively
classify that arrival. Two of these tests (the first two) are the
sabotage pair — they were run against a version of the module that read
only the CURRENT snapshot, and both went red, proving the check cannot be
satisfied by parsing the working tree.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import task_origins  # noqa: E402

LEDGER = task_origins.DEFAULT_PATH
T = 1784900000


def ledger_repo(path: Path, snapshots, name="tasks.md"):
    """A git repo at `path` committing each (text, when) snapshot in order.

    Returns the list of commit SHAs, oldest first. Timestamps are pinned
    through the environment so first_seen values are asserted exactly.
    """
    path.mkdir(parents=True, exist_ok=True)
    led = path / LEDGER
    led.parent.mkdir(parents=True, exist_ok=True)
    base = dict(os.environ,
                GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
    subprocess.run(["git", "-C", str(path), "init", "-q"], env=base,
                   check=True, capture_output=True)
    shas = []
    for i, (text, when) in enumerate(snapshots):
        env = dict(base, GIT_AUTHOR_DATE="@%d +0000" % when,
                   GIT_COMMITTER_DATE="@%d +0000" % when)
        led.write_text(text)
        subprocess.run(["git", "-C", str(path), "add", LEDGER],
                       env=env, check=True, capture_output=True)
        subprocess.run(["git", "-C", str(path), "commit", "-q", "-m",
                        "ledger %d" % i], env=env, check=True,
                       capture_output=True)
        sha = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                             env=env, check=True, capture_output=True
                             ).stdout.decode().strip()
        shas.append(sha)
    return shas


def by_id(result):
    return {t["id"]: t for t in result["tasks"]}


HEAD = "# Task ledger\n\nNext id: **400**\n\n## Open\n\n"


class TestFirstSightIsFinal:
    """The rule the module exists for: arrival is classified ONCE."""

    def test_first_seen_human_survives_a_later_loop_edit(self, tmp_path):
        # SABOTAGE-PROVEN: a current-snapshot reader reports loop here.
        shas = ledger_repo(tmp_path, [
            (HEAD + "- **#300** — a task · P2 · task · origin: **human**\n", T),
            (HEAD + "- **#300** — a task · P2 · task · origin: **loop**\n",
             T + 3600),
        ])
        rec = by_id(task_origins.task_origins(tmp_path))[300]
        assert rec["origin"] == "human"
        assert rec["first_commit"] == shas[0]
        assert rec["first_seen"] == T

    def test_first_seen_unmarked_stays_unknown_after_a_later_marker(self, tmp_path):
        # SABOTAGE-PROVEN: a current-snapshot reader reports human here.
        # Backfilling a marker later is documentation, not time travel.
        shas = ledger_repo(tmp_path, [
            (HEAD + "- **#300** — a task · P2 · task\n", T),
            (HEAD + "- **#300** — a task · P2 · task · origin: **human**\n",
             T + 3600),
        ])
        rec = by_id(task_origins.task_origins(tmp_path))[300]
        assert rec["origin"] == "unknown"
        assert rec["first_commit"] == shas[0]

    def test_a_deleted_task_stays_in_history(self, tmp_path):
        ledger_repo(tmp_path, [
            (HEAD + "- **#300** — a task · P2 · task · origin: **loop**\n", T),
            (HEAD, T + 3600),
        ])
        rec = by_id(task_origins.task_origins(tmp_path))[300]
        assert rec["origin"] == "loop"


class TestEntryGrammarAtFirstSight:
    def test_combined_ids_share_the_first_sight_entry(self, tmp_path):
        shas = ledger_repo(tmp_path, [
            (HEAD + "- **#250/#251** — a combined filing · P2 · task · "
                    "origin: **loop**\n", T),
        ])
        res = by_id(task_origins.task_origins(tmp_path))
        assert res[250]["origin"] == "loop"
        assert res[251]["origin"] == "loop"
        assert res[250]["first_commit"] == shas[0] == res[251]["first_commit"]

    def test_an_earlier_separate_appearance_wins(self, tmp_path):
        # #250 arrives alone, then the pair is filed together: #250 keeps
        # its earlier record, #251 is classified from the combined entry.
        shas = ledger_repo(tmp_path, [
            (HEAD + "- **#250** — alone first · P2 · task · origin: **human**\n", T),
            (HEAD + "- **#250/#251** — combined later · P2 · task · "
                    "origin: **loop**\n", T + 3600),
        ])
        res = by_id(task_origins.task_origins(tmp_path))
        assert res[250]["origin"] == "human"
        assert res[250]["first_commit"] == shas[0]
        assert res[251]["origin"] == "loop"
        assert res[251]["first_commit"] == shas[1]

    def test_body_references_never_classify(self, tmp_path):
        # `blocked on #264` in a body is a cross-reference. If body ids
        # classified, #264 would arrive early and unknown, and its real
        # first entry would never get to speak.
        shas = ledger_repo(tmp_path, [
            (HEAD + "- **#100** — an old task · P2 · task · blocked on #264\n", T),
            (HEAD + "- **#264** — the real one · P2 · task · origin: **loop**\n",
             T + 3600),
        ])
        res = by_id(task_origins.task_origins(tmp_path))
        assert res[264]["origin"] == "loop"
        assert res[264]["first_commit"] == shas[1]
        assert res[264]["first_seen"] == T + 3600

    def test_a_wrapped_marker_is_read_at_first_sight(self, tmp_path):
        # The loop writes at ~72 columns, so `origin:` may end a line with
        # the value opening the next — the linter's grammar, reused.
        ledger_repo(tmp_path, [
            (HEAD + "- **#300** — a task with a long title that wraps · P2 · "
                    "origin:\n  **human** · the body continues\n", T),
        ])
        assert by_id(task_origins.task_origins(tmp_path))[300]["origin"] == "human"

    def test_invalid_and_duplicate_markers_fail_closed_to_unknown(self, tmp_path):
        ledger_repo(tmp_path, [
            (HEAD + "- **#300** — bad value · P2 · origin: **bot**\n"
                    "- **#301** — two claims · P2 · origin: **human** · "
                    "origin: **loop**\n"
                    "- **#302** — wrong case · P2 · origin: **Human**\n", T),
        ])
        res = by_id(task_origins.task_origins(tmp_path))
        assert res[300]["origin"] == "unknown"
        assert res[301]["origin"] == "unknown"
        assert res[302]["origin"] == "unknown"

    def test_pre_and_post_cutoff_ids_are_both_parsed(self, tmp_path):
        # The cutoff governs the LINTER's demands, not history: a history
        # parser covers every id, old and new alike.
        ledger_repo(tmp_path, [
            (HEAD + "- **#100** — an old task · P2 · task\n"
                    "- **#300** — a new task · P2 · task · origin: **human**\n", T),
        ])
        res = by_id(task_origins.task_origins(tmp_path))
        assert res[100]["origin"] == "unknown"
        assert res[300]["origin"] == "human"

    def test_same_timestamp_commits_resolve_in_commit_order(self, tmp_path):
        # A chronological tie must be deterministic: the parent commit is
        # the earlier sight, whatever the clock says (or fails to say).
        shas = ledger_repo(tmp_path, [
            (HEAD + "- **#300** — a task · P2 · origin: **human**\n", T),
            (HEAD + "- **#300** — a task · P2 · origin: **loop**\n", T),
        ])
        rec = by_id(task_origins.task_origins(tmp_path))[300]
        assert rec["origin"] == "human"
        assert rec["first_commit"] == shas[0]


class TestRecordShape:
    def test_a_record_carries_what_the_renderer_will_need(self, tmp_path):
        shas = ledger_repo(tmp_path, [
            (HEAD + "- **#300** — a titled task · P2 · task · origin: **loop**\n", T),
        ])
        rec = by_id(task_origins.task_origins(tmp_path))[300]
        assert rec == {"id": 300, "origin": "loop", "first_commit": shas[0],
                       "first_seen": T, "title": "a titled task · P2 · task · "
                                                 "origin: **loop**"}

    def test_the_json_is_deterministic_and_round_trips(self, tmp_path):
        ledger_repo(tmp_path, [
            (HEAD + "- **#300** — b · origin: **human**\n", T),
            (HEAD + "- **#42** — a · P2\n- **#300** — b · origin: **human**\n",
             T + 3600),
        ])
        one = task_origins.task_origins(tmp_path)
        two = task_origins.task_origins(tmp_path)
        assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)
        json.loads(json.dumps(one))  # the whole shape is JSON-serializable
        assert [t["id"] for t in one["tasks"]] == [42, 300]


class TestHistoryCompleteness:
    def test_a_full_history_reports_complete(self, tmp_path):
        ledger_repo(tmp_path, [(HEAD + "- **#1** — a · P2\n", T)])
        assert task_origins.task_origins(tmp_path)["history_complete"] is True

    def test_a_shallow_clone_reports_incomplete(self, tmp_path):
        src = tmp_path / "src"
        ledger_repo(src, [
            (HEAD + "- **#1** — a · P2\n", T),
            (HEAD + "- **#1** — a · P2\n- **#2** — b · origin: **loop**\n",
             T + 3600),
        ])
        dst = tmp_path / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1",
                        "file://" + str(src), str(dst)],
                       check=True, capture_output=True)
        res = task_origins.task_origins(dst)
        # #1 arrived before the shallow boundary: claiming full coverage
        # would be a lie, so the flag goes false rather than the record.
        assert res["history_complete"] is False
        assert "shallow" in res["history_note"]


class TestBoundaries:
    def test_a_non_repo_is_a_real_error(self, tmp_path):
        with pytest.raises(task_origins.TaskOriginsError):
            task_origins.task_origins(tmp_path)

    def test_a_missing_ledger_is_not_an_error_but_an_empty_history(self, tmp_path):
        ledger_repo(tmp_path, [("no entries\n", T)], name="other.md")
        # nothing committed under the ledger path at all
        res = task_origins.task_origins(tmp_path)
        assert res["tasks"] == []
        assert res["history_complete"] is True

    @pytest.mark.parametrize("bad", ["/etc/passwd", "../escape.md",
                                     "a/../../escape.md"])
    def test_the_path_cannot_escape_the_repo(self, tmp_path, bad):
        ledger_repo(tmp_path, [(HEAD, T)])
        with pytest.raises(task_origins.TaskOriginsError):
            task_origins.task_origins(tmp_path, path=bad)


class TestCli:
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(Path(task_origins.__file__)), *args],
            capture_output=True, text=True)

    def test_default_stdout_is_machine_readable_json(self, tmp_path):
        ledger_repo(tmp_path, [
            (HEAD + "- **#300** — a task · origin: **human**\n", T)])
        proc = self.run_cli("--repo", str(tmp_path))
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout)
        assert out["tasks"][0]["id"] == 300
        assert out["tasks"][0]["origin"] == "human"

    def test_json_flag_and_path_option(self, tmp_path):
        ledger_repo(tmp_path, [
            (HEAD + "- **#300** — a task · origin: **loop**\n", T)])
        proc = self.run_cli("--repo", str(tmp_path), "--path", LEDGER, "--json")
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["tasks"][0]["origin"] == "loop"

    def test_a_non_repo_exits_nonzero(self, tmp_path):
        proc = self.run_cli("--repo", str(tmp_path))
        assert proc.returncode != 0
        assert proc.stderr.strip()

    def test_an_escaping_path_exits_nonzero(self, tmp_path):
        ledger_repo(tmp_path, [(HEAD, T)])
        proc = self.run_cli("--repo", str(tmp_path), "--path", "../x.md")
        assert proc.returncode != 0
