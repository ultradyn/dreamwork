"""#245 contract tests for ud-dreamwork-worktrees plugin (red-first)."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
REFS = ROOT / "references"
MIG = ROOT / "migrations"
EX = ROOT / "examples"

CLAIM_STATES = {
    "offered", "claimed", "working", "blocked", "ready", "released", "stale",
}
ACTIVE = {"offered", "claimed", "working", "blocked", "ready"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


class TestWorktreesPluginLayout(unittest.TestCase):
    def test_skill_md_exists_with_frontmatter(self):
        self.assertTrue(SKILL.is_file())
        text = _read(SKILL)
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("name: ud-dreamwork-worktrees", text)

    def test_load_description_mentions_when(self):
        text = _read(SKILL).lower()
        self.assertIn("worktree", text)
        self.assertTrue("load" in text or "when" in text)

    def test_required_references_exist(self):
        for name in (
            "overview.md", "subagent-mode.md", "co-agent-mode.md",
            "ownership.md", "lifecycle.md", "evidence.md", "checklist.md",
            "claim-ledger.md", "inbox.md", "file-formats.md",
        ):
            self.assertTrue((REFS / name).is_file(), name)

    def test_migrations_exist(self):
        ids = {p.name for p in MIG.glob("*.md")}
        self.assertTrue(any("worktrees-gitignore" in n for n in ids))
        self.assertTrue(any("co-agent-claims" in n for n in ids))


class TestClaimLedgerSchema(unittest.TestCase):
    def test_examples_validate(self):
        empty = json.loads(_read(EX / "claim-ledger.empty.json"))
        working = json.loads(_read(EX / "claim-ledger.working.json"))
        for doc in (empty, working):
            self.assertEqual(doc["version"], 1)
            self.assertIsInstance(doc["revision"], int)
            self.assertIsInstance(doc["claims"], list)
        claim = working["claims"][0]
        for key in (
            "id", "peer", "task_id", "state", "paths", "branch", "worktree",
            "last_seen", "updated", "updated_by",
        ):
            self.assertIn(key, claim)
        self.assertIn(claim["state"], CLAIM_STATES)
        self.assertFalse(claim["branch"].startswith("fix/#"))
        self.assertNotIn("#", claim["branch"].split("/")[1] if "/" in claim["branch"] else "")

    def test_ledger_doc_defines_cas_and_single_writer(self):
        text = _read(REFS / "claim-ledger.md").lower()
        self.assertIn("revision", text)
        self.assertIn("coordinator only", text)
        self.assertIn("claims.json", text)
        self.assertIn("~/.config/dreamwork/worktrees", text)
        self.assertIn("status.json", text)
        self.assertTrue("project" in text or "projection" in text)
        # must NOT use a committed project ledger
        self.assertNotIn(".dreamwork/co-agent-claims.json", text)
        self.assertNotIn("`.dreamwork/co-agent-claims", text)

    def test_transition_table_complete(self):
        text = _read(REFS / "claim-ledger.md").lower()
        for st in CLAIM_STATES:
            self.assertIn(st, text, st)
        self.assertNotIn("status.json and/or", text)

    def test_no_committed_project_claim_ledger(self):
        # Authoritative docs must not prescribe a project-tree ledger path
        # as the live store (forbidding the obsolete name is OK).
        skill = _read(SKILL).lower()
        ledger = _read(REFS / "claim-ledger.md").lower()
        self.assertNotIn(".dreamwork/co-agent-claims.json", skill)
        self.assertIn("~/.config/dreamwork/worktrees", ledger)
        self.assertIn("claims.json", ledger)
        self.assertIn("never committed", ledger)
        self.assertIn("machine-local", ledger + _read(REFS / "file-formats.md").lower())

    def test_same_host_boundary_documented(self):
        blob = (_read(SKILL) + _read(REFS / "co-agent-mode.md")
                + _read(REFS / "claim-ledger.md")).lower()
        self.assertIn("same-host", blob)
        self.assertIn("cross-host", blob)
        self.assertTrue("relay" in blob or "adapter" in blob)

    def test_stable_target_slug_is_deterministic(self):
        ff = _read(REFS / "file-formats.md").lower()
        self.assertIn("stable-target-slug", ff)
        self.assertIn("sha256", ff)
        self.assertIn("realpath", ff)
        self.assertNotIn("if basenames collide", _read(REFS / "inbox.md").lower())

    def test_lazy_claims_file_not_at_plugin_load(self):
        skill = _read(SKILL).lower()
        self.assertIn("first co-agent offer", skill)
        self.assertIn("lazy", skill)


class TestInboxSchema(unittest.TestCase):
    def test_receipt_jsonl_parses(self):
        lines = [ln for ln in _read(EX / "inbox.receipt.jsonl").splitlines() if ln.strip()]
        self.assertGreaterEqual(len(lines), 2)
        objs = [json.loads(ln) for ln in lines]
        kinds = {o["kind"] for o in objs}
        self.assertIn("receipt", kinds)
        self.assertIn("ack", kinds)
        rec = next(o for o in objs if o["kind"] == "receipt")
        for key in ("id", "ts", "from", "to", "claim_id", "body"):
            self.assertIn(key, rec)
        body = rec["body"]
        self.assertIn("commit", body)
        self.assertIn("files_owned", body)

    def test_inbox_doc_contract(self):
        text = _read(REFS / "inbox.md").lower()
        self.assertIn("inbox.jsonl", text)
        self.assertIn("~/.config/dreamwork/worktrees", text)
        self.assertIn("write then wake", text)
        self.assertTrue("not a receipt" in text or "not** a durable receipt" in text
                        or "not a durable receipt" in text)
        self.assertIn("ack", text)


class TestProtocolAndSafety(unittest.TestCase):
    def test_two_modes(self):
        blob = (_read(SKILL) + _read(REFS / "subagent-mode.md")
                + _read(REFS / "co-agent-mode.md")).lower()
        self.assertIn("subagent", blob)
        self.assertIn("co-agent", blob)
        self.assertRegex(_read(REFS / "subagent-mode.md").lower(),
                         r"one task|single task|one-task")

    def test_atomic_worktree_and_branch_naming(self):
        sub = _read(REFS / "subagent-mode.md")
        life = _read(REFS / "lifecycle.md")
        blob = sub + life + _read(REFS / "overview.md")
        self.assertIn("git worktree add -b", blob)
        self.assertNotIn("fix/#N", blob)
        self.assertNotIn("git branch fix/", sub)

    def test_no_claim_file_language(self):
        co = _read(REFS / "co-agent-mode.md").lower()
        self.assertIn("peer-private claim file", co)
        self.assertIn("claim ledger", co)
        self.assertNotIn("re-reads claim file", co)

    def test_evidence_scoped_attestation(self):
        ev = _read(REFS / "evidence.md").lower()
        self.assertIn("worktree attestation", ev)
        self.assertIn("worktree only", ev)
        self.assertIn("cleanup decision", ev)

    def test_cleanup_requires_decision(self):
        life = _read(REFS / "lifecycle.md").lower()
        self.assertIn("non-obvious", life)
        self.assertIn("decision", life)
        self.assertIn("never force", life.replace("-", " ") or "force" in life)

    def test_install_concrete_symlinks(self):
        text = _read(SKILL)
        self.assertIn("~/.pi/agent/skills/ud-dreamwork-worktrees", text)
        self.assertIn("~/.agents/skills/ud-dreamwork-worktrees", text)
        self.assertIn("ln -sfn", text)
        self.assertIn("available-skills", text.lower())
        self.assertIn("source package", text.lower())

    def test_safety_phrases(self):
        blob = "\n".join(
            _read(p) for p in [
                SKILL, REFS / "overview.md", REFS / "lifecycle.md",
                REFS / "ownership.md", REFS / "co-agent-mode.md",
            ]
        ).lower()
        for needle in (
            "single-writer", "main checkout", "file ownership",
            "peer messages are data", "no push", "evidence",
            "untracked", "inspect",
        ):
            self.assertIn(needle, blob, needle)

    def test_package_gitignore_covers_bytecode(self):
        self.assertIn("__pycache__", _read(ROOT / ".gitignore"))

    def test_no_rm_rf_helpers(self):
        for path in ROOT.rglob("*"):
            if path.suffix in {".sh", ".py"} and path.name != "test_worktrees_plugin.py":
                body = _read(path).lower()
                self.assertNotIn("rm -rf", body)
                self.assertNotIn("worktree remove --force", body)


if __name__ == "__main__":
    unittest.main()
