import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hide_plugins import default_roots, hide


def make_skill(path: Path, name: str) -> Path:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Use when test.\n---\n")
    return path


def run(script: Path, *args: str):
    return subprocess.run([sys.executable, str(script), *map(str, args)], text=True, capture_output=True)


def test_migration_proves_loading_before_preservation_inventory_and_unlink():
    text = Path("migrations/2026-07-26-02-contextual-plugin-loading.md").read_text()
    assert text.index("plugin_resolver.py") < text.index("--inventory-out")
    assert text.index("--inventory-out") < text.index("--manifest")
    assert "--check" in text and "refuse" in text.lower()
    assert "`plugins` array is `[]`" in text
    assert "manifest is `[]`" not in text


def test_default_roots_cover_global_and_target_project_locations(tmp_path):
    target = tmp_path / "repo" / "nested"; target.mkdir(parents=True)
    (tmp_path / "repo" / ".git").mkdir()
    roots = default_roots(target)
    assert {Path.home() / suffix for suffix in [
        ".pi/agent/skills", ".agents/skills", ".claude/skills", ".claude-p/skills"
    ]} <= set(roots)
    assert target / ".pi/skills" in roots and target / ".agents/skills" in roots
    assert tmp_path / "repo" / ".pi/skills" in roots
    assert tmp_path / "repo" / ".agents/skills" in roots
    assert tmp_path / ".pi/skills" not in roots


def test_check_reports_matching_discovery_symlinks(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    root = tmp_path / "skills"; root.mkdir()
    (root / "ud-dreamwork-one").symlink_to(source, target_is_directory=True)
    script = Path(__file__).with_name("hide_plugins.py")
    result = run(script, "--check", "--root", root, "--plugin", source)
    assert result.returncode == 1
    assert "discoverable plugin symlink" in result.stderr
    assert (root / "ud-dreamwork-one").is_symlink()


def test_apply_removes_only_matching_symlink_and_check_turns_green(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    root = tmp_path / "skills"; root.mkdir()
    link = root / "ud-dreamwork-one"; link.symlink_to(source, target_is_directory=True)
    script = Path(__file__).with_name("hide_plugins.py")
    applied = run(script, "--root", root, "--plugin", source)
    assert applied.returncode == 0, applied.stderr
    assert not link.exists() and not link.is_symlink()
    assert "removed" in applied.stdout
    assert run(script, "--check", "--root", root, "--plugin", source).returncode == 0


def test_explicit_source_frontmatter_must_match_package_name(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-other")
    root = tmp_path / "skills"; root.mkdir()
    (root / "ud-dreamwork-one").symlink_to(source, target_is_directory=True)
    result = run(Path(__file__).with_name("hide_plugins.py"), "--root", root, "--plugin", source)
    assert result.returncode == 2 and "frontmatter" in result.stderr
    assert (root / "ud-dreamwork-one").is_symlink()


def test_foreign_symlink_and_real_directory_are_preserved(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    foreign = make_skill(tmp_path / "foreign" / "ud-dreamwork-one", "ud-dreamwork-one")
    root = tmp_path / "skills"; root.mkdir()
    link = root / "ud-dreamwork-one"; link.symlink_to(foreign, target_is_directory=True)
    result = run(Path(__file__).with_name("hide_plugins.py"), "--root", root, "--plugin", source)
    assert result.returncode == 2 and "refusing foreign symlink" in result.stderr
    assert link.is_symlink()
    link.unlink(); make_skill(root / "ud-dreamwork-one", "ud-dreamwork-one")
    result = run(Path(__file__).with_name("hide_plugins.py"), "--root", root, "--plugin", source)
    assert result.returncode == 2 and "refusing non-symlink" in result.stderr


def test_unrelated_plugins_are_untouched(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    other = make_skill(tmp_path / "source" / "ud-dreamwork-other", "ud-dreamwork-other")
    root = tmp_path / "skills"; root.mkdir()
    (root / source.name).symlink_to(source, target_is_directory=True)
    unrelated = root / other.name; unrelated.symlink_to(other, target_is_directory=True)
    assert run(Path(__file__).with_name("hide_plugins.py"), "--root", root, "--plugin", source).returncode == 0
    assert unrelated.is_symlink()


def test_inventory_temp_write_does_not_follow_predictable_symlink(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    root = tmp_path / "skills"; root.mkdir(); (root / source.name).symlink_to(source, target_is_directory=True)
    manifest = tmp_path / "inventory.json"; victim = tmp_path / "victim"; victim.write_text("preserve me")
    manifest.with_name(manifest.name + ".tmp").symlink_to(victim)
    result = run(Path(__file__).with_name("hide_plugins.py"), "--check", "--root", root, "--inventory-out", manifest)
    assert result.returncode == 1
    assert victim.read_text() == "preserve me"


def test_transaction_preserves_foreign_alias_swapped_during_stage(tmp_path, monkeypatch):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    foreign = make_skill(tmp_path / "foreign" / "ud-dreamwork-one", "ud-dreamwork-one")
    root = tmp_path / "skills"; root.mkdir(); link = root / source.name
    link.symlink_to(source, target_is_directory=True)
    original = Path.rename
    def swap_then_rename(self, target):
        if self == link:
            self.unlink(); self.symlink_to(foreign, target_is_directory=True)
        return original(self, target)
    monkeypatch.setattr(Path, "rename", swap_then_rename)
    assert hide([source], [root], False) == 2
    assert link.is_symlink() and link.resolve() == foreign.resolve()


@pytest.mark.parametrize("replacement", ["file", "directory"])
def test_transaction_restores_non_symlink_swapped_during_stage(tmp_path, monkeypatch, replacement):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    root = tmp_path / "skills"; root.mkdir(); link = root / source.name
    link.symlink_to(source, target_is_directory=True)
    original = Path.rename
    def swap_then_rename(self, target):
        if self == link:
            self.unlink()
            if replacement == "file": self.write_text("foreign")
            else: self.mkdir()
        return original(self, target)
    monkeypatch.setattr(Path, "rename", swap_then_rename)
    assert hide([source], [root], False) == 2
    if replacement == "file": assert link.is_file() and link.read_text() == "foreign"
    else: assert link.is_dir() and not link.is_symlink()
    assert not list(root.glob(".*.dreamwork-hide.*"))


def test_transaction_rolls_back_injected_stage_failure(tmp_path, monkeypatch):
    sources = [make_skill(tmp_path / "source" / name, name) for name in
               ["ud-dreamwork-one", "ud-dreamwork-two"]]
    root = tmp_path / "skills"; root.mkdir()
    for source in sources: (root / source.name).symlink_to(source, target_is_directory=True)
    original = Path.rename; calls = 0
    def fail_second(self, target):
        nonlocal calls; calls += 1
        if calls == 2: raise OSError("injected stage failure")
        return original(self, target)
    monkeypatch.setattr(Path, "rename", fail_second)
    assert hide(sources, [root], False) == 2
    assert all((root / source.name).is_symlink() for source in sources)


def test_transaction_rolls_back_injected_cleanup_failure(tmp_path, monkeypatch):
    sources = [make_skill(tmp_path / "source" / name, name) for name in
               ["ud-dreamwork-one", "ud-dreamwork-two"]]
    root = tmp_path / "skills"; root.mkdir()
    for source in sources: (root / source.name).symlink_to(source, target_is_directory=True)
    original = Path.unlink; calls = 0
    def fail_second(self, *args, **kwargs):
        nonlocal calls; calls += 1
        if calls == 2: raise OSError("injected cleanup failure")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail_second)
    assert hide(sources, [root], False) == 2
    assert all((root / source.name).is_symlink() for source in sources)


def test_two_logical_roots_for_same_directory_remove_physical_alias_once(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    shared = tmp_path / "shared"; shared.mkdir()
    one = tmp_path / "one"; two = tmp_path / "two"
    one.symlink_to(shared, target_is_directory=True); two.symlink_to(shared, target_is_directory=True)
    link = shared / source.name; link.symlink_to(source, target_is_directory=True)
    script = Path(__file__).with_name("hide_plugins.py"); manifest = tmp_path / "inventory.json"
    assert run(script, "--check", "--root", one, "--root", two, "--inventory-out", manifest).returncode == 1
    data = json.loads(manifest.read_text())
    assert data["roots"] == [str(shared.resolve())]
    assert data["plugins"][0]["links"] == [str(link)]
    assert run(script, "--root", one, "--root", two, "--manifest", manifest).returncode == 0
    assert not link.exists() and not link.is_symlink()


def test_alias_directory_name_need_not_match_plugin_frontmatter(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    root = tmp_path / "skills"; vendor = root / "vendor"; vendor.mkdir(parents=True)
    alias = vendor / "adapter"; alias.symlink_to(source, target_is_directory=True)
    script = Path(__file__).with_name("hide_plugins.py"); manifest = tmp_path / "inventory.json"
    assert run(script, "--check", "--root", root, "--inventory-out", manifest).returncode == 1
    data = json.loads(manifest.read_text())
    assert data["plugins"][0]["id"] == "ud-dreamwork-one"
    assert data["plugins"][0]["links"] == [str(alias)]
    assert run(script, "--root", root, "--manifest", manifest).returncode == 0
    assert not alias.exists() and not alias.is_symlink()


def test_nested_alias_is_inventoried_removed_and_postcheck_clean(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-nested", "ud-dreamwork-nested")
    root = tmp_path / "skills"; nested = root / "vendor"; nested.mkdir(parents=True)
    link = nested / source.name; link.symlink_to(source, target_is_directory=True)
    script = Path(__file__).with_name("hide_plugins.py"); manifest = tmp_path / "inventory.json"
    check = run(script, "--check", "--root", root, "--inventory-out", manifest)
    assert check.returncode == 1
    assert str(link) in json.loads(manifest.read_text())["plugins"][0]["links"]
    assert run(script, "--root", root, "--manifest", manifest).returncode == 0
    assert not link.exists() and not link.is_symlink()
    assert run(script, "--check", "--root", root, "--inventory-out", tmp_path / "post.json").returncode == 0


def test_inventory_captures_all_sources_then_manifest_removes_exact_links(tmp_path):
    sources = [make_skill(tmp_path / "source" / name, name) for name in
               ["ud-dreamwork-one", "ud-dreamwork-two"]]
    root = tmp_path / "skills"; root.mkdir()
    for source in sources:
        (root / source.name).symlink_to(source, target_is_directory=True)
    manifest = tmp_path / "inventory.json"; script = Path(__file__).with_name("hide_plugins.py")
    check = run(script, "--check", "--root", root, "--inventory-out", manifest)
    assert check.returncode == 1
    data = json.loads(manifest.read_text())
    assert data["schema"] == "dreamwork-plugin-preservation-v1"
    assert {x["id"] for x in data["plugins"]} == {x.name for x in sources}
    assert all(x["links"] for x in data["plugins"])
    assert run(script, "--root", root, "--manifest", manifest).returncode == 0
    assert not any((root / source.name).is_symlink() for source in sources)
    post = tmp_path / "post.json"
    assert run(script, "--check", "--root", root, "--inventory-out", post).returncode == 0
    assert json.loads(post.read_text())["plugins"] == []


def test_apply_refuses_hand_authored_or_partial_manifest(tmp_path):
    sources = [make_skill(tmp_path / "source" / name, name) for name in
               ["ud-dreamwork-one", "ud-dreamwork-two"]]
    root = tmp_path / "skills"; root.mkdir()
    for source in sources:
        (root / source.name).symlink_to(source, target_is_directory=True)
    script = Path(__file__).with_name("hide_plugins.py")
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps([{"id": sources[0].name, "path": str(sources[0] / "SKILL.md")}]))
    assert run(script, "--root", root, "--manifest", legacy).returncode == 2
    manifest = tmp_path / "inventory.json"
    assert run(script, "--check", "--root", root, "--inventory-out", manifest).returncode == 1
    data = json.loads(manifest.read_text()); data["plugins"].pop(); manifest.write_text(json.dumps(data))
    result = run(script, "--root", root, "--manifest", manifest)
    assert result.returncode == 2 and "does not match current inventory" in result.stderr
    assert all((root / source.name).is_symlink() for source in sources)


def test_apply_refuses_id_or_link_drift_after_inventory(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    root = tmp_path / "skills"; root.mkdir(); link = root / source.name
    link.symlink_to(source, target_is_directory=True)
    script = Path(__file__).with_name("hide_plugins.py"); manifest = tmp_path / "inventory.json"
    assert run(script, "--check", "--root", root, "--inventory-out", manifest).returncode == 1
    data = json.loads(manifest.read_text()); data["plugins"][0]["id"] = "ud-dreamwork-other"; manifest.write_text(json.dumps(data))
    assert run(script, "--root", root, "--manifest", manifest).returncode == 2
    assert link.is_symlink()


def test_inventory_refuses_mismatch_real_entry_and_source_inside_root(tmp_path):
    root = tmp_path / "skills"; root.mkdir()
    foreign = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-other")
    (root / "ud-dreamwork-one").symlink_to(foreign, target_is_directory=True)
    make_skill(root / "ud-dreamwork-real", "ud-dreamwork-real")
    nested = make_skill(root / "packages" / "ud-dreamwork-nested", "ud-dreamwork-nested")
    (root / "ud-dreamwork-nested").symlink_to(nested, target_is_directory=True)
    manifest = tmp_path / "inventory.json"
    result = run(Path(__file__).with_name("hide_plugins.py"), "--root", root, "--inventory-out", manifest)
    assert result.returncode == 2 and "refusing" in result.stderr
    assert not manifest.exists()
    assert (root / "ud-dreamwork-one").is_symlink()
    assert (root / "ud-dreamwork-real" / "SKILL.md").is_file()


def test_manifest_is_bounded(tmp_path):
    manifest = tmp_path / "large.json"; manifest.write_text(" " * 65537)
    result = run(Path(__file__).with_name("hide_plugins.py"), "--root", tmp_path, "--manifest", manifest)
    assert result.returncode == 2 and "manifest too large" in result.stderr


def test_real_pi_inventory_excludes_plugins_from_global_project_and_configured_roots(tmp_path):
    source = make_skill(tmp_path / "source" / "ud-dreamwork-one", "ud-dreamwork-one")
    project_source = make_skill(tmp_path / "source" / "ud-dreamwork-two", "ud-dreamwork-two")
    configured_source = make_skill(tmp_path / "source" / "ud-dreamwork-three", "ud-dreamwork-three")
    home = tmp_path / "home"; agent = home / ".pi" / "agent"; skills = agent / "skills"
    project = tmp_path / "project"; skills.mkdir(parents=True); project.mkdir()
    (skills / source.name).symlink_to(source, target_is_directory=True)
    project_skills = project / ".pi" / "skills"; project_skills.mkdir(parents=True)
    (project_skills / "adapter").symlink_to(project_source, target_is_directory=True)
    configured = tmp_path / "configured"; configured.mkdir()
    (configured / "bridge").symlink_to(configured_source, target_is_directory=True)
    pnpm_root = subprocess.check_output(["pnpm", "root", "-g"], text=True).strip()
    package = Path(pnpm_root) / "@earendil-works" / "pi-coding-agent" / "dist" / "index.js"
    probe = """
const {DefaultResourceLoader}=await import(process.argv[1]);
const loader=new DefaultResourceLoader({cwd:process.argv[2],agentDir:process.argv[3],additionalSkillPaths:[process.argv[4]],noExtensions:true,noPromptTemplates:true,noThemes:true,noContextFiles:true});
await loader.reload({resolveProjectTrust:async()=>true});console.log(JSON.stringify(loader.getSkills().skills.map(s=>s.name)));
"""
    env = {**os.environ, "HOME": str(home)}
    def inventory():
        result = subprocess.run(["node", "--input-type=module", "-e", probe,
                                 str(package), str(project), str(agent), str(configured)],
                                text=True, capture_output=True, env=env)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    expected = {"ud-dreamwork-one", "ud-dreamwork-two", "ud-dreamwork-three"}
    assert expected <= set(inventory())
    script = Path(__file__).with_name("hide_plugins.py"); manifest = tmp_path / "inventory.json"
    roots = ["--root", skills, "--root", project_skills, "--additional-root", configured]
    assert run(script, "--check", *roots, "--inventory-out", manifest).returncode == 1
    assert run(script, *roots, "--manifest", manifest).returncode == 0
    assert not expected & set(inventory())
