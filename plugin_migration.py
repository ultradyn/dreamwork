"""Validated inventory and reversible removal for plugin discovery aliases."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

from plugin_resolver import (
    MAX_MANIFEST_BYTES, MAX_PLUGINS, PLUGIN_ID, PluginResolutionError,
    bounded_manifest_json, frontmatter_name,
)

SCHEMA = "dreamwork-plugin-preservation-v1"
MAX_SCAN_ENTRIES = 10000
MAX_SCAN_DEPTH = 32


def validate_source(source: Path) -> Path:
    real = source.resolve(strict=True)
    skill = real / "SKILL.md"
    if not PLUGIN_ID.fullmatch(real.name) or not skill.is_file():
        raise ValueError(f"not a Dreamwork plugin package: {source}")
    try:
        name = frontmatter_name(skill)
    except PluginResolutionError as error:
        raise ValueError(str(error)) from error
    if name != real.name:
        raise ValueError(
            f"plugin frontmatter name {name!r} does not match package "
            f"{real.name!r}: {source}"
        )
    return real


def source_dirs(arguments: list[Path]) -> list[Path]:
    result: list[Path] = []
    for source in arguments:
        real = validate_source(source)
        if real not in result:
            result.append(real)
    return result


def recursive_entries(root: Path) -> tuple[list[Path], list[str]]:
    if not root.is_dir():
        return [], []
    found: list[Path] = []
    unsafe: list[str] = []
    stack = [(root, 0)]
    scanned = 0
    while stack:
        directory, depth = stack.pop()
        if depth > MAX_SCAN_DEPTH:
            unsafe.append(f"refusing discovery tree deeper than {MAX_SCAN_DEPTH}: {directory}")
            continue
        try:
            entries = list(directory.iterdir())
        except OSError as error:
            unsafe.append(f"refusing unreadable discovery directory {directory}: {error}")
            continue
        scanned += len(entries)
        if scanned > MAX_SCAN_ENTRIES:
            unsafe.append(f"refusing discovery tree larger than {MAX_SCAN_ENTRIES} entries: {root}")
            break
        if any(entry.name == "SKILL.md" for entry in entries):
            found.append(directory)
            continue
        for entry in entries:
            if entry.name.startswith(".") or entry.name == "node_modules":
                continue
            if entry.is_symlink():
                try:
                    if entry.resolve(strict=True).is_dir():
                        stack.append((entry, depth + 1))
                except OSError:
                    continue
            elif entry.is_dir():
                stack.append((entry, depth + 1))
    return found, unsafe


def canonical_roots(roots: list[Path]) -> list[Path]:
    result: list[Path] = []
    for root in roots:
        resolved = root.expanduser().resolve()
        if resolved not in result:
            result.append(resolved)
    return result


def build_inventory(roots: list[Path]) -> tuple[dict[str, object], list[str]]:
    resolved_roots = canonical_roots(roots)
    plugins: dict[str, dict[str, object]] = {}
    unsafe: list[str] = []
    for root in resolved_roots:
        if not root.is_dir():
            continue
        entries, scan_errors = recursive_entries(root)
        unsafe.extend(scan_errors)
        for entry in entries:
            try:
                discovered_name = frontmatter_name(entry / "SKILL.md")
            except PluginResolutionError:
                continue
            if not PLUGIN_ID.fullmatch(discovered_name):
                continue
            if not entry.is_symlink():
                unsafe.append(f"refusing non-symlink discovery entry: {entry}")
                continue
            try:
                target = validate_source(entry.resolve(strict=True))
            except (OSError, ValueError) as error:
                unsafe.append(f"refusing unreadable plugin symlink {entry}: {error}")
                continue
            if target.name != discovered_name:
                unsafe.append(f"refusing mismatched plugin symlink: {entry} -> {target}")
                continue
            if any(target.is_relative_to(candidate) for candidate in resolved_roots):
                unsafe.append(
                    f"refusing plugin source inside discovery root: {entry} -> {target}; "
                    "move/copy it to bundled, sibling, or explicit storage first"
                )
                continue
            skill = str((target / "SKILL.md").resolve())
            record = plugins.get(discovered_name)
            if record and record["path"] != skill:
                unsafe.append(
                    f"refusing ambiguous preserved sources for {discovered_name}: "
                    f"{record['path']} and {skill}"
                )
                continue
            if not record:
                if len(plugins) >= MAX_PLUGINS:
                    unsafe.append(f"refusing more than {MAX_PLUGINS} discovered plugins")
                    continue
                record = {"id": discovered_name, "path": skill, "links": []}
                plugins[discovered_name] = record
            links = record["links"]
            assert isinstance(links, list)
            links.append(str(entry.absolute()))
    ordered = []
    for plugin_id in sorted(plugins):
        record = plugins[plugin_id]
        record["links"] = sorted(set(record["links"]))
        ordered.append(record)
    return {
        "schema": SCHEMA,
        "roots": [str(path) for path in resolved_roots],
        "plugins": ordered,
    }, unsafe

def write_inventory(path: Path, inventory: dict[str, object]) -> None:
    encoded = bounded_manifest_json(inventory) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        fd, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(raw_path)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_manifest(path: Path) -> dict[str, object]:
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError(f"manifest too large: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"schema", "roots", "plugins"}:
        raise ValueError("manifest must be a preservation inventory object")
    if data["schema"] != SCHEMA:
        raise ValueError(f"manifest schema must be {SCHEMA}")
    if not isinstance(data["roots"], list) or not isinstance(data["plugins"], list):
        raise ValueError("manifest roots and plugins must be arrays")
    return data


def discoverable_for_sources(
    sources: list[Path], roots: list[Path]
) -> tuple[list[tuple[Path, Path]], list[str]]:
    links: list[tuple[Path, Path]] = []
    unsafe: list[str] = []
    for root in canonical_roots(roots):
        entries, scan_errors = recursive_entries(root)
        unsafe.extend(scan_errors)
        for entry in entries:
            try:
                discovered_name = frontmatter_name(entry / "SKILL.md")
            except PluginResolutionError:
                continue
            matching = [source for source in sources if source.name == discovered_name]
            if not matching:
                continue
            if not entry.is_symlink():
                unsafe.append(f"refusing non-symlink discovery entry: {entry}")
                continue
            try:
                target = entry.resolve(strict=True)
            except OSError as error:
                unsafe.append(f"refusing unreadable symlink {entry}: {error}")
                continue
            source = matching[0]
            if target != source:
                unsafe.append(
                    f"refusing foreign symlink: {entry} -> {target} "
                    f"(expected {source})"
                )
                continue
            links.append((entry, source))
    return links, unsafe


def rollback(records: list[tuple[Path, str | None, Path]]) -> list[str]:
    failures: list[str] = []
    for link, raw_target, backup in reversed(records):
        try:
            if link.exists() or link.is_symlink():
                continue
            if backup.exists() or backup.is_symlink():
                backup.rename(link)
            elif raw_target is not None:
                link.symlink_to(raw_target)
            else:
                failures.append(f"rollback source vanished for {link}")
        except OSError as error:
            failures.append(f"rollback failed for {link}: {error}")
    return failures


def remove_links_transactionally(links: list[tuple[Path, Path]]) -> int:
    records = [
        (link, expected, link.with_name(
            f".{link.name}.dreamwork-hide.{uuid.uuid4().hex}"
        ))
        for link, expected in links
    ]
    staged: list[tuple[Path, str | None, Path]] = []
    try:
        for link, expected, backup in records:
            link.rename(backup)
            staged.append((link, None, backup))
            if not backup.is_symlink():
                raise OSError(f"discovery alias became a non-symlink: {link}")
            raw_target = os.readlink(backup)
            staged[-1] = (link, raw_target, backup)
            if backup.resolve(strict=True) != expected:
                raise OSError(
                    f"discovery alias changed during staging: {link}"
                )
    except OSError as error:
        failures = rollback(staged)
        print(f"plugin migration stage failed; rolled back: {error}", file=sys.stderr)
        if failures:
            print("; ".join(failures), file=sys.stderr)
        return 2
    try:
        expected_by_link = {link: expected for link, expected, _ in records}
        for link, _, backup in staged:
            if not backup.is_symlink() or backup.resolve(strict=True) != expected_by_link[link]:
                raise OSError(f"staged alias changed before cleanup: {link}")
            backup.unlink()
    except OSError as error:
        failures = rollback(staged)
        print(f"plugin migration cleanup failed; rolled back: {error}", file=sys.stderr)
        if failures:
            print("; ".join(failures), file=sys.stderr)
        return 2
    for link, _, _ in records:
        print(f"removed {link}")
    return 0


def hide(sources: list[Path], roots: list[Path], check: bool) -> int:
    links, unsafe = discoverable_for_sources(sources, roots)
    if unsafe:
        print("\n".join(unsafe), file=sys.stderr)
        return 2
    if check:
        for link, _ in links:
            print(f"discoverable plugin symlink: {link}", file=sys.stderr)
        if links:
            return 1
        print("Dreamwork plugins are absent from the checked discovery roots")
        return 0
    if not links:
        print("no matching Dreamwork plugin discovery symlinks found")
        return 0
    return remove_links_transactionally(links)
