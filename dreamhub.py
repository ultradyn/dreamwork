#!/usr/bin/env python3
"""dreamhub.py — read-only aggregate overview of several dreamwork targets.

Plan: .dreamwork/docs/plans/dreamhub-stage1.md (human go 2026-07-25 10:48).
Design record: dreamhub-design.md (skill root).

Stdlib only, one file — so `just deploy`'s snapshot pattern applies to it
unchanged. Binds 127.0.0.1 exclusively. Writes NOTHING outside
`~/.config/dreamwork/hub/`: every per-project fact is read live from that
project's own `.dreamwork/` (and from its running watch instance) and is
never cached to disk, because a cached copy is a second source of truth
that goes stale exactly when it matters.

Reuse with watch.py is at the PROTOCOL layer, never the code layer: the hub
polls each target's `GET /mtime` and re-reads `GET /data.json` only when it
changes — the same contract watch's own client uses. So the hub never parses
`questions.md`, the open-question count keeps exactly one implementation,
and a target whose watch is down reports "unknown" rather than a second,
subtly different answer. No `import watch`.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time

# Where the machine-local state lives. Which projects exist is a fact about
# THIS MACHINE, not about any repo — committing it would be wrong on the next
# machine and would leak local paths. `DREAMHUB_HOME` overrides it, which is
# what the tests and the guards point at their own fixtures with.
DEFAULT_HOME = os.path.join("~", ".config", "dreamwork", "hub")

# Registry schema version. Bump only for a shape change that an older
# dreamhub could misread; readers refuse anything they do not know.
REGISTRY_VERSION = 1

SLUG_OK = re.compile(r"[^a-z0-9._-]+")


def hub_home():
    return os.path.abspath(os.path.expanduser(
        os.environ.get("DREAMHUB_HOME") or DEFAULT_HOME))


def registry_path():
    return os.path.join(hub_home(), "projects.json")


def normalise(path):
    """User input → the one canonical form we store and compare.

    `~`, relative paths and trailing slashes all collapse here, so `add .`
    twice from two different directories cannot produce two entries for one
    project.
    """
    return os.path.abspath(os.path.expanduser(path))


def is_target(path):
    """Does this directory look like a dreamwork target?

    A target has a `.dreamwork/` or a `DREAMWORK.md`. The check exists so a
    typo'd path is rejected at `add` time rather than sitting in the list
    looking healthy — a registry entry that never resolves is indistinguish-
    able from a project whose loop is merely quiet.
    """
    return (os.path.isdir(os.path.join(path, ".dreamwork"))
            or os.path.isfile(os.path.join(path, "DREAMWORK.md")))


def slug_for(path, taken):
    """Stable, human-typeable name for a project — assigned ONCE, at add time.

    Recomputing a slug on read would mean that adding a colliding project
    silently renames an existing one, and every link, bookmark and log line
    that named the old slug would quietly point somewhere else. So the slug
    is stored, and this function is called exactly once per project.
    """
    base = SLUG_OK.sub("-", os.path.basename(path.rstrip(os.sep)).lower())
    base = base.strip("-") or "target"
    if base not in taken:
        return base
    return f"{base}-{hashlib.sha1(path.encode()).hexdigest()[:6]}"


class RegistryError(Exception):
    """The registry exists but cannot be understood."""


def _blank():
    return {"version": REGISTRY_VERSION, "projects": []}


def load_registry(strict=False):
    """Read the registry. Missing file = empty registry, which is normal.

    An UNREADABLE file is not normal, and `strict` is the difference that
    matters: a writer that treated corruption as "empty" would rewrite the
    file and destroy whatever was in it. Readers degrade; writers refuse.
    """
    path = registry_path()
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        return _blank()
    except OSError as e:
        if strict:
            raise RegistryError(f"cannot read {path}: {e.strerror}")
        return _blank()
    try:
        data = json.loads(raw)
    except ValueError as e:
        if strict:
            raise RegistryError(f"{path} is not valid JSON ({e}); fix or "
                                f"move it aside — refusing to overwrite it")
        return _blank()
    if not isinstance(data, dict) or not isinstance(
            data.get("projects"), list):
        if strict:
            raise RegistryError(f"{path} is not a dreamhub registry — "
                                f"refusing to overwrite it")
        return _blank()
    if data.get("version") != REGISTRY_VERSION:
        if strict:
            raise RegistryError(
                f"{path} is registry version {data.get('version')!r}, this "
                f"dreamhub speaks {REGISTRY_VERSION}")
        return _blank()
    return data


def save_registry(reg):
    """Atomic replace: a torn write here loses the human's whole project list.

    Same reasoning as status.json being read defensively — except the hub is
    the writer, so it can simply make the torn state impossible.
    """
    path = registry_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def find(reg, slug_or_path):
    """Look a project up by slug first, then by path — `remove` takes either,
    because the human knows where a project IS more reliably than what the
    hub decided to call it."""
    for p in reg["projects"]:
        if p["slug"] == slug_or_path:
            return p
    target = normalise(slug_or_path)
    for p in reg["projects"]:
        if p["path"] == target:
            return p
    return None


def add_project(reg, path, force=False):
    """Register `path`. Returns (entry, created:bool).

    Adding an already-registered path is idempotent and silent — the human
    re-running `add` after a shell restart should not get an error, and must
    never get a second entry for one directory.
    """
    path = normalise(path)
    existing = next((p for p in reg["projects"] if p["path"] == path), None)
    if existing:
        return existing, False
    if not os.path.isdir(path):
        raise RegistryError(f"{path} is not a directory")
    if not force and not is_target(path):
        raise RegistryError(
            f"{path} has no .dreamwork/ and no DREAMWORK.md — not a dreamwork "
            f"target. Pass --force if you meant it.")
    entry = {
        "slug": slug_for(path, {p["slug"] for p in reg["projects"]}),
        "path": path,
        "added": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    reg["projects"].append(entry)
    return entry, True


# ---------------------------------------------------------------- CLI

def cmd_add(args):
    reg = load_registry(strict=True)
    entry, created = add_project(reg, args.path, force=args.force)
    if created:
        save_registry(reg)
        print(f"added {entry['slug']}  {entry['path']}")
    else:
        print(f"already registered as {entry['slug']}  {entry['path']}")
    return 0


def cmd_remove(args):
    reg = load_registry(strict=True)
    entry = find(reg, args.slug)
    if not entry:
        print(f"dreamhub: no project '{args.slug}' — try `dreamhub list`",
              file=sys.stderr)
        return 1
    reg["projects"].remove(entry)
    save_registry(reg)
    print(f"removed {entry['slug']}  {entry['path']}")
    return 0


def cmd_list(args):
    reg = load_registry()
    if not reg["projects"]:
        print("no projects registered — `dreamhub add <path>`")
        return 0
    width = max(len(p["slug"]) for p in reg["projects"])
    for p in reg["projects"]:
        print(f"{p['slug']:<{width}}  {p['path']}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="dreamhub",
        description="one page over several dreaming projects on this machine")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="register a dreamwork target")
    a.add_argument("path")
    a.add_argument("--force", action="store_true",
                   help="register even if it does not look like a target")
    a.set_defaults(fn=cmd_add)

    r = sub.add_parser("remove", help="unregister a project (slug or path)")
    r.add_argument("slug")
    r.set_defaults(fn=cmd_remove)

    ls = sub.add_parser("list", help="show the registry")
    ls.set_defaults(fn=cmd_list)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 0
    try:
        return args.fn(args)
    except RegistryError as e:
        print(f"dreamhub: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
