#!/usr/bin/env python3
"""Advisory dice for the dreamwork loop.

Rolls backlog-vs-maintenance, and which maintenance item. Advisory only:
the agent's judgment (a mess, easier-now-than-later, human steer) always
overrides the roll. Custom weights should be persisted as a Routines line
in the target's DREAMWORK.md, e.g.:

    roll: --backlog 80 --weight docs=4 --weight coverage=1
"""

import argparse
import random
import sys

MAINTENANCE = {
    "goal-alignment": 3,
    "self-review": 3,
    "coverage": 2,
    "docs": 2,
    "task-grooming": 2,
    "dream-grooming": 1,
    "dogfood-reflection": 2,
}


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Advisory backlog/maintenance roll for the dreamwork loop."
    )
    p.add_argument("--backlog", type=int, default=70,
                   help="weight of picking a backlog task (default 70)")
    p.add_argument("--maintenance", type=int, default=30,
                   help="weight of the maintenance pool (default 30)")
    p.add_argument("--weight", action="append", default=[], metavar="ITEM=N",
                   help="override a maintenance item weight (repeatable)")
    p.add_argument("--no-backlog", action="store_true",
                   help="backlog is empty: roll among maintenance only")
    p.add_argument("--list", action="store_true",
                   help="print items and effective weights, no roll")
    p.add_argument("--seed", type=int, help="deterministic roll (testing)")
    return p.parse_args(argv)


def effective_weights(overrides):
    weights = dict(MAINTENANCE)
    for spec in overrides:
        item, _, n = spec.partition("=")
        if item not in weights:
            sys.exit(f"unknown maintenance item: {item!r} "
                     f"(known: {', '.join(weights)})")
        try:
            weights[item] = int(n)
        except ValueError:
            sys.exit(f"bad weight in {spec!r} (want ITEM=N)")
    return {k: v for k, v in weights.items() if v > 0}


def main(argv=None):
    args = parse_args(argv)
    weights = effective_weights(args.weight)
    if args.list:
        print(f"backlog: {args.backlog}  maintenance-pool: {args.maintenance}")
        for item, w in weights.items():
            print(f"  {item}: {w}")
        return
    rng = random.Random(args.seed)
    if not args.no_backlog:
        if rng.randrange(args.backlog + args.maintenance) < args.backlog:
            print("backlog")
            return
    total = sum(weights.values())
    r = rng.randrange(total)
    for item, w in weights.items():
        r -= w
        if r < 0:
            print(f"maintenance: {item}")
            return


if __name__ == "__main__":
    main()
