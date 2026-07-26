#!/usr/bin/env python3
"""Resolve only Dreamwork plugins explicitly loaded by a target.

Plugin source packages remain valid Agent Skills, but inactive plugins must not
live under ordinary harness discovery roots. This resolver deliberately knows
only install-relative package locations and explicit fallback roots.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PLUGIN_ID = re.compile(r"^ud-dreamwork-[a-z0-9]+(?:-[a-z0-9]+)*$")
LOAD_LINE = re.compile(r"^\s*-\s*Load:\s*`([^`]+)`(?:\s|$)")
HEADING = re.compile(r"^##\s+(.+?)\s*$")
NAME_LINE = re.compile(r"^name:\s*(.*?)\s*$")
MAX_DREAMWORK_BYTES = 256 * 1024
MAX_SKILL_BYTES = 1024 * 1024
MAX_PLUGINS = 32
MAX_MANIFEST_BYTES = 64 * 1024


class PluginResolutionError(ValueError):
    pass


def parse_declared_plugins(path: Path) -> list[str]:
    """Return ordered Load IDs from the literal Plugins section only."""
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return []
    if size > MAX_DREAMWORK_BYTES:
        raise PluginResolutionError(
            f"DREAMWORK.md exceeds {MAX_DREAMWORK_BYTES} bytes: {path}"
        )
    lines = path.read_text(encoding="utf-8").splitlines()
    in_plugins = False
    result: list[str] = []
    for line in lines:
        heading = HEADING.match(line)
        if heading:
            in_plugins = heading.group(1).strip().casefold() == "plugins"
            continue
        if not in_plugins:
            continue
        match = LOAD_LINE.match(line)
        if not match:
            continue
        plugin_id = match.group(1)
        if not PLUGIN_ID.fullmatch(plugin_id):
            raise PluginResolutionError(f"invalid plugin id in {path}: {plugin_id!r}")
        if plugin_id in result:
            raise PluginResolutionError(f"duplicate plugin declaration in {path}: {plugin_id}")
        result.append(plugin_id)
        if len(result) > MAX_PLUGINS:
            raise PluginResolutionError(
                f"DREAMWORK.md declares more than {MAX_PLUGINS} plugins: {path}"
            )
    return result


def frontmatter_name(path: Path) -> str:
    try:
        size = path.stat().st_size
        if size > MAX_SKILL_BYTES:
            raise PluginResolutionError(
                f"SKILL.md exceeds {MAX_SKILL_BYTES} bytes: {path}"
            )
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise PluginResolutionError(f"cannot read plugin {path}: {error}") from error
    if not lines or lines[0].strip() != "---":
        raise PluginResolutionError(f"plugin has no YAML frontmatter: {path}")
    names: list[str] = []
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        match = NAME_LINE.match(line)
        if match:
            names.append(match.group(1).strip().strip("'\""))
    if not closed:
        raise PluginResolutionError(f"plugin has unclosed YAML frontmatter: {path}")
    if len(names) != 1:
        raise PluginResolutionError(
            f"plugin frontmatter requires exactly one name (found {len(names)}): {path}"
        )
    return names[0]


def candidate_tiers(
    core: Path, plugin_id: str, roots: list[Path], explicit: dict[str, Path]
) -> list[list[Path]]:
    return [
        [core / "plugins" / plugin_id / "SKILL.md"],
        [core.parent / plugin_id / "SKILL.md"],
        [explicit[plugin_id]] if plugin_id in explicit else [],
        [root / plugin_id / "SKILL.md" for root in roots],
    ]


def candidate_paths(
    core: Path, plugin_id: str, roots: list[Path], explicit: dict[str, Path]
) -> list[Path]:
    return [path for tier in candidate_tiers(core, plugin_id, roots, explicit) for path in tier]


def resolve_plugins(
    target: Path, core: Path, roots: list[Path], explicit: dict[str, Path] | None = None
) -> list[dict[str, str]]:
    declared = parse_declared_plugins(target / "DREAMWORK.md")
    explicit = explicit or {}
    resolved: list[dict[str, str]] = []
    for plugin_id in declared:
        searched = candidate_paths(core, plugin_id, roots, explicit)
        found: dict[Path, Path] = {}
        for tier in candidate_tiers(core, plugin_id, roots, explicit):
            tier_found: dict[Path, Path] = {}
            for candidate in tier:
                if not candidate.is_file():
                    continue
                real = candidate.resolve()
                name = frontmatter_name(real)
                if name != plugin_id:
                    raise PluginResolutionError(
                        f"plugin frontmatter name {name!r} does not match declared "
                        f"{plugin_id!r}: {real}"
                    )
                tier_found[real] = candidate
            if tier_found:
                found = tier_found
                break
        if not found:
            paths = "\n  ".join(str(path) for path in searched)
            raise PluginResolutionError(
                f"declared plugin {plugin_id!r} is not installed; searched:\n  {paths}\n"
                "Install it bundled under the Dreamwork core, as a canonical "
                "sibling package, or pass an explicit --root."
            )
        if len(found) > 1:
            paths = "\n  ".join(str(path) for path in found)
            raise PluginResolutionError(
                f"declared plugin {plugin_id!r} is ambiguous; distinct packages found:\n  {paths}"
            )
        real = next(iter(found))
        resolved.append({"id": plugin_id, "path": str(real)})
    return resolved


def parse_explicit_paths(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        plugin_id, separator, raw_path = value.partition("=")
        if not separator or not PLUGIN_ID.fullmatch(plugin_id) or not raw_path:
            raise PluginResolutionError(
                f"invalid --path {value!r}; expected ud-dreamwork-id=/path/to/SKILL.md"
            )
        if plugin_id in result:
            raise PluginResolutionError(f"duplicate --path for {plugin_id}")
        result[plugin_id] = Path(raw_path)
    return result


def bounded_manifest_json(result: object) -> str:
    encoded = json.dumps(result, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_MANIFEST_BYTES:
        raise PluginResolutionError(
            f"plugin manifest exceeds {MAX_MANIFEST_BYTES} bytes"
        )
    return encoded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--core", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--root", type=Path, action="append", default=[])
    parser.add_argument(
        "--path", action="append", default=[], metavar="ID=SKILL.md",
        help="explicit fallback for one declared plugin",
    )
    args = parser.parse_args(argv)
    try:
        explicit = parse_explicit_paths(args.path)
        result = resolve_plugins(args.target.resolve(), args.core.resolve(), args.root, explicit)
    except PluginResolutionError as error:
        print(f"plugin resolution failed: {error}", file=sys.stderr)
        return 2
    try:
        encoded = bounded_manifest_json(result)
    except PluginResolutionError as error:
        print(f"plugin resolution failed: {error}", file=sys.stderr)
        return 2
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
