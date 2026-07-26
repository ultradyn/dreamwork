#!/usr/bin/env python3
"""Inventory and safely remove Dreamwork plugin discovery symlinks."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from plugin_migration import (
    build_inventory, hide, load_manifest, source_dirs, write_inventory,
)


def project_roots(target: Path) -> list[Path]:
    current = target.expanduser().resolve()
    if current.is_file():
        current = current.parent
    ancestors: list[Path] = []
    while True:
        ancestors.extend([current / ".pi/skills", current / ".agents/skills"])
        if (current / ".git").exists() or current.parent == current:
            break
        current = current.parent
    return ancestors


def default_roots(target: Path | None = None) -> list[Path]:
    home = Path.home()
    roots = [home / ".pi/agent/skills", home / ".agents/skills",
             home / ".claude/skills", home / ".claude-p/skills"]
    return roots + project_roots(target or Path.cwd())


def manifest_links(inventory: dict[str, object]) -> list[Path]:
    links: list[Path] = []
    plugins = inventory["plugins"]
    assert isinstance(plugins, list)
    for record in plugins:
        assert isinstance(record, dict)
        record_links = record.get("links")
        assert isinstance(record_links, list)
        links.extend(Path(link) for link in record_links if isinstance(link, str))
    return links


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--target", type=Path, default=Path.cwd())
    parser.add_argument("--root", type=Path, action="append",
                        help="replace automatic roots (primarily for tests)")
    parser.add_argument("--additional-root", type=Path, action="append", default=[],
                        help="configured package/settings root; repeat as needed")
    parser.add_argument("--plugin", type=Path, action="append", default=[])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--inventory-out", type=Path)
    args = parser.parse_args(argv)
    roots = (args.root or default_roots(args.target)) + args.additional_root
    modes = bool(args.plugin) + bool(args.manifest) + bool(args.inventory_out)
    if modes != 1:
        print("plugin migration failed: choose exactly one source mode", file=sys.stderr)
        return 2
    try:
        if args.inventory_out:
            inventory, unsafe = build_inventory(roots)
            if unsafe:
                print("\n".join(unsafe), file=sys.stderr)
                return 2
            write_inventory(args.inventory_out, inventory)
            links = manifest_links(inventory)
            for link in links:
                print(f"discoverable plugin symlink: {link}", file=sys.stderr)
            if links:
                return 1
            print("Dreamwork plugins are absent from the checked discovery roots")
            return 0
        if args.manifest:
            expected = load_manifest(args.manifest)
            current, unsafe = build_inventory(roots)
            if unsafe:
                print("\n".join(unsafe), file=sys.stderr)
                return 2
            if expected != current:
                print("plugin migration failed: manifest does not match current inventory", file=sys.stderr)
                return 2
            plugins = expected["plugins"]
            assert isinstance(plugins, list)
            sources = source_dirs([Path(record["path"]).parent for record in plugins])
            return hide(sources, roots, args.check)
        return hide(source_dirs(args.plugin), roots, args.check)
    except (AssertionError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"plugin migration failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
