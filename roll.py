#!/usr/bin/env python3
"""Advisory dice for the dreamwork loop.

Rolls backlog-vs-maintenance, and which maintenance item. Advisory only:
the agent's judgment (a mess, easier-now-than-later, human steer) always
overrides the roll. Custom weights should be persisted as a Routines line
in the target's DREAMWORK.md, e.g.:

    roll: --backlog 80 --weight docs=4 --weight coverage=1

Output contract: the LAST line is always the machine-readable pick
("backlog" or "maintenance: <item>"). Above it, a human-friendly breakdown
of raw rolls and probability gates (suppress with --quiet). ANSI colors
auto-enable on a TTY (--color always|never|auto).
"""

import argparse
import random
import sys

# goal-alignment is deliberately absent: it is never rolled. Alignment
# precedes the roll deterministically (selection step 0; rotation leads
# with it).
MAINTENANCE = {
    "self-review": 3,
    "coverage": 2,
    "docs": 2,
    "task-grooming": 2,
    "dream-grooming": 1,
    "dogfood-reflection": 2,
}


class Style:
    def __init__(self, enabled):
        c = lambda code: (lambda s: f"\033[{code}m{s}\033[0m") if enabled \
            else (lambda s: str(s))
        self.head = c("1;36")   # bold cyan
        self.roll = c("1;33")   # bold yellow
        self.win = c("1;32")    # bold green
        self.dim = c("2")       # dim
        self.bold = c("1")


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
    p.add_argument("--quiet", "-q", action="store_true",
                   help="suppress the breakdown; print only the pick")
    p.add_argument("--color", choices=("auto", "always", "never"),
                   default="auto", help="colorize the breakdown (default auto)")
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
    use_color = args.color == "always" or (
        args.color == "auto" and sys.stdout.isatty())
    st = Style(use_color)

    if args.list:
        print(st.head("weights"))
        print(f"  backlog: {args.backlog}  maintenance-pool: {args.maintenance}")
        for item, w in weights.items():
            print(f"  {item}: {w}")
        return

    rng = random.Random(args.seed)
    out = None if args.quiet else []

    def note(line):
        if out is not None:
            out.append(line)

    if not args.no_backlog:
        gate_total = args.backlog + args.maintenance
        r = rng.randrange(gate_total)
        hit_backlog = r < args.backlog
        note(st.head("gate 1: backlog vs maintenance"))
        note(f"  roll {st.roll(r)} of 0..{gate_total - 1}  "
             f"{st.dim(f'(< {args.backlog} → backlog, ≥ {args.backlog} → maintenance)')}")
        note(f"  → {st.win('backlog') if hit_backlog else st.bold('maintenance pool')}")
        if hit_backlog:
            if out:
                print("\n".join(out))
            print("backlog")
            return
    else:
        note(st.dim("gate 1 skipped: --no-backlog"))

    total = sum(weights.values())
    r = rng.randrange(total)
    note(st.head("gate 2: maintenance item"))
    note(f"  roll {st.roll(r)} of 0..{total - 1}")
    cursor = 0
    pick = None
    for item, w in weights.items():
        lo, hi = cursor, cursor + w - 1
        marker = "→" if (pick is None and lo <= r <= hi) else " "
        line = f"  {marker} {item} {st.dim(f'[{lo}..{hi}]')}"
        if marker == "→":
            pick = item
            line = f"  {marker} {st.win(item)} {st.dim(f'[{lo}..{hi}]')}"
        note(line)
        cursor += w
    if out:
        print("\n".join(out))
    print(f"maintenance: {pick}")


if __name__ == "__main__":
    main()
