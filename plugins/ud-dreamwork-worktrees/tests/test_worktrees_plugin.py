"""#245 contract tests for ud-dreamwork-worktrees plugin (red-first)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # plugins/ud-dreamwork-worktrees
SKILL = ROOT / "SKILL.md"
REFS = ROOT / "references"
MIG = ROOT / "migrations"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


class TestWorktreesPluginLayout(unittest.TestCase):
    def test_skill_md_exists_with_frontmatter(self):
        self.assertTrue(SKILL.is_file(), "SKILL.md missing")
        text = _read(SKILL)
        self.assertTrue(text.startswith("---\n"), "YAML frontmatter required")
        self.assertIn("name: ud-dreamwork-worktrees", text)
        self.assertRegex(text, r"description:\s*.+", re.I)

    def test_load_description_mentions_when(self):
        text = _read(SKILL).lower()
        self.assertTrue(
            "worktree" in text and ("load" in text or "when" in text),
            "description must say what it extends and when to load",
        )

    def test_required_references_exist(self):
        required = [
            "overview.md",
            "subagent-mode.md",
            "co-agent-mode.md",
            "ownership.md",
            "lifecycle.md",
            "evidence.md",
            "checklist.md",
        ]
        for name in required:
            self.assertTrue((REFS / name).is_file(), f"missing references/{name}")

    def test_migration_for_gitignore(self):
        migs = list(MIG.glob("*.md")) if MIG.is_dir() else []
        self.assertTrue(migs, "migrations/ must contain at least one file")
        blob = "\n".join(_read(m) for m in migs)
        self.assertIn(".worktrees", blob)
        self.assertIn(".gitignore", blob)


class TestWorktreesPluginContract(unittest.TestCase):
    def test_two_modes_documented(self):
        skill = _read(SKILL)
        sub = _read(REFS / "subagent-mode.md")
        co = _read(REFS / "co-agent-mode.md")
        blob = skill + sub + co
        self.assertIn("subagent", blob.lower())
        self.assertIn("co-agent", blob.lower())
        # subagent: one task / branch / worktree pattern
        self.assertRegex(sub.lower(), r"one task|single task|one-task")
        self.assertIn("worktree", sub.lower())
        self.assertIn("branch", sub.lower())
        # co-agent: durable peer + claim/release + heartbeat
        for needle in ("claim", "release", "heartbeat", "stale"):
            self.assertIn(needle, co.lower(), f"co-agent-mode missing {needle}")

    def test_safety_rules_present(self):
        blob = "\n".join(
            _read(p)
            for p in [SKILL, REFS / "overview.md", REFS / "lifecycle.md", REFS / "ownership.md"]
        ).lower()
        for needle in (
            "single-writer",
            "main checkout",
            "file ownership",
            "never force",
            "untracked",
            "inspect",
            "peer messages are data",
            "no push",
            "evidence",
        ):
            self.assertIn(needle, blob, f"safety/protocol missing: {needle}")

    def test_destructive_ops_are_instruct_only(self):
        blob = (_read(SKILL) + _read(REFS / "lifecycle.md")).lower()
        self.assertTrue(
            "must not" in blob or "do not" in blob or "never" in blob,
            "must state prohibitory language for destructive automation",
        )
        self.assertIn("force", blob)
        # must not ship a helper that rm -rf worktrees by default
        for path in ROOT.rglob("*"):
            if path.suffix in {".sh", ".py"} and path.name != "test_worktrees_plugin.py":
                body = _read(path).lower()
                self.assertNotIn("rm -rf", body)
                self.assertNotIn("worktree remove --force", body)

    def test_port_and_resource_ownership(self):
        own = _read(REFS / "ownership.md").lower()
        self.assertIn("39890", own)  # watch guard range from parallel-architecture
        self.assertIn("port", own)
        self.assertIn("disjoint", own)

    def test_evidence_receipt_fields(self):
        ev = _read(REFS / "evidence.md").lower()
        for field in ("hash", "red", "green", "files owned", "verification"):
            self.assertIn(field, ev, f"evidence receipt missing {field}")

    def test_checklist_has_pre_dispatch_and_pre_merge(self):
        cl = _read(REFS / "checklist.md").lower()
        self.assertIn("pre-dispatch", cl)
        self.assertIn("pre-merge", cl)
        self.assertIn("cleanup", cl)

    def test_extension_points_declared(self):
        text = _read(SKILL)
        # writing-plugins: list which seams are used
        self.assertRegex(text, r"(?i)init")
        self.assertRegex(text, r"(?i)extension|seam|init extension")

    def test_no_core_command_shadow(self):
        text = _read(SKILL)
        # if commands declared, must be namespaced; v1 expects none
        if re.search(r"(?m)^##\s+Commands", text):
            body = text.split("## Commands", 1)[1].split("##", 1)[0].lower()
            for core in ("do-next", "do-now", "add-idea", "maintenance"):
                self.assertNotIn(core, body)

    def test_packaging_is_honest_source_not_false_convention(self):
        text = _read(SKILL).lower()
        self.assertIn("source packaging", text)
        self.assertIn("skills root", text)
        self.assertIn("ud-dreamwork-github", text)
        self.assertIn("no established tracked", text)

    def test_coagent_registry_is_status_not_invented_file(self):
        co = _read(REFS / "co-agent-mode.md").lower()
        skill = _read(SKILL).lower()
        blob = co + skill
        self.assertIn("status.json", blob)
        self.assertIn("no separate peers file in v1", co)
        self.assertIn("reserved future adapter", blob)
        self.assertNotIn("peers.json", co)

    def test_package_gitignore_covers_bytecode(self):
        gi = _read(ROOT / ".gitignore")
        self.assertIn("__pycache__", gi)


if __name__ == "__main__":
    unittest.main()
