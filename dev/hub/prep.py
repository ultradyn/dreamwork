#!/usr/bin/env python3
"""Copy dev/hub/fixture into a scratch directory and make its ages real.

Both readers of the fixture go through here — `test_dreamhub.py` imports
`prepare()`, `hub.mjs` shells out to `python3 dev/hub/prep.py <dst>` — so the
relative-age rule has exactly one implementation and the two halves of the
verification cannot disagree about what "stalled" means.

Why the ages are not simply frozen with the rest of the fixture: a state whose
whole meaning is "how long since the last tick" cannot be pinned to a
wall-clock timestamp. A fixture that says `2026-07-25T12:00` is `dreaming`
today, `stalled` tomorrow, and a permanent red light by the weekend — and a
guard whose false reds train you to ignore it is worse than no guard.

So the SHAPES are frozen and only the offsets in `ages.json` are relative.
Each named target gets its `status.json` rewritten with a `last_tick` that
many seconds ago, and its file mtime set to match (the mtime is the fallback
liveness signal for a status.json that cannot be parsed — `torn`).

Usage: python3 dev/hub/prep.py <dst> [<src>]   — prints <dst>
"""

import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixture")

# In the registry the readers build, but deliberately absent from disk: a
# target the human deleted or renamed must render as broken, not vanish.
MISSING_SLUG = "gone"


def prepare(dst, src=FIXTURE, now=None):
    """Copy `src` to `dst` and apply `ages.json`. Returns `dst`."""
    now = time.time() if now is None else now
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    with open(os.path.join(dst, "ages.json"), encoding="utf-8") as f:
        ages = json.load(f)
    for name, age in ages.items():
        if name.startswith("_"):
            continue
        path = os.path.join(dst, name, ".dreamwork", "status.json")
        stamp = now - age
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            # `torn` lands here by design: it is not valid JSON, so only its
            # mtime can carry its age. Rewriting it would destroy the case.
            data = None
        if data is not None:
            data["last_tick"] = datetime.fromtimestamp(
                stamp, timezone.utc).astimezone().isoformat(timespec="seconds")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
        if os.path.exists(path):
            os.utime(path, (stamp, stamp))
    return dst


def registry_for(dst, extra_missing=True):
    """The registry both readers point at the prepared fixture.

    One definition, so the guard and the pytest suite are looking at the same
    set of rows — including `gone`, whose whole point is that it is not there.
    """
    names = sorted(d for d in os.listdir(dst)
                   if os.path.isdir(os.path.join(dst, d)))
    projects = [{"slug": n, "path": os.path.join(dst, n),
                 "added": "2026-07-25T12:00:00"} for n in names]
    if extra_missing:
        projects.append({"slug": MISSING_SLUG,
                         "path": os.path.join(dst, MISSING_SLUG),
                         "added": "2026-07-25T12:00:00"})
    return {"version": 1, "projects": projects}


def main(argv=None):
    """CLI half, for hub.mjs: prepare the targets and (optionally) write the
    registry that points at them, so the guard and the pytest suite cannot
    disagree about which rows exist."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: prep.py <dst> [--home <hubhome>]", file=sys.stderr)
        return 2
    dst = prepare(argv[0])
    if "--home" in argv:
        home = argv[argv.index("--home") + 1]
        os.makedirs(home, exist_ok=True)
        with open(os.path.join(home, "projects.json"), "w",
                  encoding="utf-8") as f:
            json.dump(registry_for(dst), f, indent=2)
    print(dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
