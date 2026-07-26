import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from plugin_resolver import (
    PluginResolutionError, bounded_manifest_json, parse_declared_plugins, resolve_plugins,
)


def dreamwork(path: Path, *loads: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    body = "# Dreamwork\n\n## Plugins\n\n" + "".join(
        f"- Load: `{name}` — test\n" for name in loads
    ) + "- Don't load:\n"
    (path / "DREAMWORK.md").write_text(body)
    return path


def plugin(path: Path, name: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use when Dreamwork loads {name}.\n---\n\n# {name}\n"
    )
    return path


def test_dreamwork_file_size_is_bounded(tmp_path):
    target = tmp_path / "target"; target.mkdir()
    (target / "DREAMWORK.md").write_text("#" * (256 * 1024 + 1))
    with pytest.raises(PluginResolutionError, match="DREAMWORK.md exceeds"):
        resolve_plugins(target, tmp_path / "core", [])


def test_declared_plugin_count_is_bounded(tmp_path):
    target = dreamwork(tmp_path / "target", *(f"ud-dreamwork-p{i}" for i in range(33)))
    with pytest.raises(PluginResolutionError, match="more than 32"):
        resolve_plugins(target, tmp_path / "core", [])


def test_skill_file_size_is_bounded(tmp_path):
    core = tmp_path / "core"
    target = dreamwork(tmp_path / "target", "ud-dreamwork-huge")
    package = core / "plugins" / "ud-dreamwork-huge"; package.mkdir(parents=True)
    (package / "SKILL.md").write_text("---\nname: ud-dreamwork-huge\n---\n" + "x" * (1024 * 1024))
    with pytest.raises(PluginResolutionError, match="SKILL.md exceeds"):
        resolve_plugins(target, core, [])


def test_no_declaration_loads_nothing_even_with_explicit_root(tmp_path):
    target = dreamwork(tmp_path / "target")
    root = tmp_path / "ordinary-discovery"
    plugin(root / "ud-dreamwork-visible", "ud-dreamwork-visible")
    assert resolve_plugins(target, tmp_path / "core", [root]) == []


def test_parse_only_load_entries_under_plugins_heading(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "DREAMWORK.md").write_text(
        "# Dreamwork\n\n`ud-dreamwork-outside`\n\n## Plugins\n\n"
        "- Load: `ud-dreamwork-a` — yes\n"
        "- Don't load: `ud-dreamwork-b`\n\n## Other\n"
        "- Load: `ud-dreamwork-after`\n"
    )
    assert parse_declared_plugins(target / "DREAMWORK.md") == ["ud-dreamwork-a"]


def test_resolves_explicit_skill_file_fallback(tmp_path):
    core = tmp_path / "core"
    target = dreamwork(tmp_path / "target", "ud-dreamwork-direct")
    direct = plugin(tmp_path / "odd" / "package", "ud-dreamwork-direct") / "SKILL.md"
    got = resolve_plugins(target, core, [], {"ud-dreamwork-direct": direct})
    assert got == [{"id": "ud-dreamwork-direct", "path": str(direct.resolve())}]


def test_resolves_bundled_sibling_and_explicit_candidates(tmp_path):
    core = tmp_path / "install" / "ud-dreamwork"
    target = dreamwork(tmp_path / "target", "ud-dreamwork-bundled", "ud-dreamwork-sibling", "ud-dreamwork-explicit")
    bundled = plugin(core / "plugins" / "ud-dreamwork-bundled", "ud-dreamwork-bundled")
    sibling = plugin(core.parent / "ud-dreamwork-sibling", "ud-dreamwork-sibling")
    root = tmp_path / "packages"
    explicit = plugin(root / "ud-dreamwork-explicit", "ud-dreamwork-explicit")
    got = resolve_plugins(target, core, [root])
    assert got == [
        {"id": "ud-dreamwork-bundled", "path": str((bundled / "SKILL.md").resolve())},
        {"id": "ud-dreamwork-sibling", "path": str((sibling / "SKILL.md").resolve())},
        {"id": "ud-dreamwork-explicit", "path": str((explicit / "SKILL.md").resolve())},
    ]


def test_same_real_package_via_symlink_is_not_ambiguous(tmp_path):
    core = tmp_path / "install" / "ud-dreamwork"
    target = dreamwork(tmp_path / "target", "ud-dreamwork-one")
    package = plugin(core / "plugins" / "ud-dreamwork-one", "ud-dreamwork-one")
    root = tmp_path / "fallback"; root.mkdir()
    (root / "ud-dreamwork-one").symlink_to(package, target_is_directory=True)
    got = resolve_plugins(target, core, [root])
    assert len(got) == 1 and got[0]["path"] == str((package / "SKILL.md").resolve())


def test_missing_reports_every_deterministic_candidate(tmp_path):
    core = tmp_path / "install" / "ud-dreamwork"
    target = dreamwork(tmp_path / "target", "ud-dreamwork-missing")
    root = tmp_path / "fallback"
    with pytest.raises(PluginResolutionError) as err:
        resolve_plugins(target, core, [root])
    text = str(err.value)
    assert "ud-dreamwork-missing" in text
    assert str(core / "plugins" / "ud-dreamwork-missing" / "SKILL.md") in text
    assert str(core.parent / "ud-dreamwork-missing" / "SKILL.md") in text
    assert str(root / "ud-dreamwork-missing" / "SKILL.md") in text


def test_bundled_precedence_ignores_distinct_lower_fallback(tmp_path):
    core = tmp_path / "install" / "ud-dreamwork"
    target = dreamwork(tmp_path / "target", "ud-dreamwork-two")
    bundled = plugin(core / "plugins" / "ud-dreamwork-two", "ud-dreamwork-two")
    root = tmp_path / "fallback"
    plugin(root / "ud-dreamwork-two", "ud-dreamwork-two")
    assert resolve_plugins(target, core, [root]) == [
        {"id": "ud-dreamwork-two", "path": str((bundled / "SKILL.md").resolve())}
    ]


def test_distinct_candidates_in_same_explicit_tier_fail_ambiguous(tmp_path):
    core = tmp_path / "install" / "ud-dreamwork"
    target = dreamwork(tmp_path / "target", "ud-dreamwork-two")
    roots = [tmp_path / "fallback-a", tmp_path / "fallback-b"]
    for root in roots:
        plugin(root / "ud-dreamwork-two", "ud-dreamwork-two")
    with pytest.raises(PluginResolutionError, match="ambiguous"):
        resolve_plugins(target, core, roots)


def test_unclosed_frontmatter_fails_validation(tmp_path):
    core = tmp_path / "core"
    target = dreamwork(tmp_path / "target", "ud-dreamwork-open")
    package = core / "plugins" / "ud-dreamwork-open"; package.mkdir(parents=True)
    (package / "SKILL.md").write_text("---\nname: ud-dreamwork-open\n# no closing delimiter\n")
    with pytest.raises(PluginResolutionError, match="frontmatter"):
        resolve_plugins(target, core, [])


def test_frontmatter_name_must_match_declaration(tmp_path):
    core = tmp_path / "core"
    target = dreamwork(tmp_path / "target", "ud-dreamwork-wanted")
    plugin(core / "plugins" / "ud-dreamwork-wanted", "ud-dreamwork-other")
    with pytest.raises(PluginResolutionError, match="frontmatter name"):
        resolve_plugins(target, core, [])


@pytest.mark.parametrize("bad", ["../ud-dreamwork-bad", "ud-dreamwork-a/b", "UD-dreamwork-x", "ud-dreamwork-"])
def test_invalid_plugin_ids_fail_closed(tmp_path, bad):
    target = dreamwork(tmp_path / "target", bad)
    with pytest.raises(PluginResolutionError, match="invalid plugin id"):
        resolve_plugins(target, tmp_path / "core", [])


def test_initialization_uses_direct_resolver_not_ordinary_discovery():
    text = Path("initialization.md").read_text()
    assert "plugin_resolver.py" in text
    assert "Discover what's available from the skills visible to you" not in text
    assert "use the harness's\n   list-skills command" not in text
    assert "read each emitted\n   `SKILL.md` directly" in text


def test_template_records_explicit_ids_without_ambient_discovery_prompts():
    text = Path("DREAMWORK.template.md").read_text()
    assert "explicit plugin IDs" in text
    assert "New plugins appearing" not in text


def test_bundled_plugin_docs_do_not_recommend_discovery_symlinks():
    paths = [Path("plugins/ud-dreamwork-worktrees/SKILL.md"),
             Path("plugins/ud-dreamwork-worktrees/references/overview.md")]
    text = "\n".join(path.read_text() for path in paths)
    assert "available-skills" not in text
    assert "harness skills root" not in text
    assert "~/.pi/agent/skills" not in text
    assert "plugin_resolver.py" in text


def test_manifest_output_is_bounded():
    with pytest.raises(PluginResolutionError, match="manifest exceeds"):
        bounded_manifest_json([{"id": "ud-dreamwork-x", "path": "/" + "x" * 65536}])


def test_cli_accepts_explicit_id_to_skill_path(tmp_path):
    target = dreamwork(tmp_path / "target", "ud-dreamwork-direct")
    direct = plugin(tmp_path / "odd" / "package", "ud-dreamwork-direct") / "SKILL.md"
    script = Path(__file__).with_name("plugin_resolver.py")
    run = subprocess.run([
        sys.executable, str(script), "--target", str(target),
        "--core", str(tmp_path / "core"),
        "--path", f"ud-dreamwork-direct={direct}",
    ], text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)[0]["path"] == str(direct.resolve())


def test_cli_emits_bounded_json(tmp_path):
    core = tmp_path / "core"
    target = dreamwork(tmp_path / "target", "ud-dreamwork-cli")
    p = plugin(core / "plugins" / "ud-dreamwork-cli", "ud-dreamwork-cli")
    script = Path(__file__).with_name("plugin_resolver.py")
    run = subprocess.run(
        [sys.executable, str(script), "--target", str(target), "--core", str(core)],
        text=True, capture_output=True,
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == [{"id": "ud-dreamwork-cli", "path": str((p / "SKILL.md").resolve())}]
    assert len(run.stdout) < 4096
