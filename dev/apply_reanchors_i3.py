#!/usr/bin/env python3
"""Apply reviewed citation re-anchors for #777 increment 3.

Each entry is (doc, old_path, old_line, new_path, new_line, source).
`source` is "tool" (accepted proposal), "review" (rejected tool proposal,
corrected by prose reading), or "disambig" (resolved an ambiguous refusal
by reading the prose to pick the watch.py definition).
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

# (doc, old_path, old_line, new_path, new_line, source)
ANCHORS = [
    # answer-record-ids.md
    (".dreamwork/docs/answer-record-ids.md", "watch.py", 6524, "watch.py", 2667, "tool"),
    # dogfood-orchestration.md — REJECTED f.read→router.js; corrected to read_bytes
    (".dreamwork/docs/dogfood-orchestration.md", "watch.py", 6752, "watch.py", 909, "review"),
    # filebytes-range.md
    (".dreamwork/docs/plans/filebytes-range.md", "watch.py", 8957, "watch.py", 5139, "tool"),
    (".dreamwork/docs/plans/filebytes-range.md", "watch.py", 7099, "watch.py", 804, "tool"),
    (".dreamwork/docs/plans/filebytes-range.md", "watch.py", 7167, "watch.py", 974, "tool"),
    (".dreamwork/docs/plans/filebytes-range.md", "watch.py", 8737, "watch.py", 4606, "tool"),
    (".dreamwork/docs/plans/filebytes-range.md", "watch.py", 7140, "watch.py", 947, "tool"),
    (".dreamwork/docs/plans/filebytes-range.md", "watch.py", 8898, "watch.py", 4860, "tool"),
    # filebytes-range.md — REJECTED _send_bytes→5139 for 7107; corrected to read_bytes 909
    (".dreamwork/docs/plans/filebytes-range.md", "watch.py", 7107, "watch.py", 909, "review"),
    # filebytes-range.md — RESOLVED refusals (ambiguous, disambiguated to watch.py)
    (".dreamwork/docs/plans/filebytes-range.md", "watch.py", 9032, "watch.py", 5190, "disambig"),  # do_GET
    (".dreamwork/docs/plans/filebytes-range.md", "watch.py", 7107, "watch.py", 909, "disambig_duplicate"),  # read_bytes at :66 (same target as review above)
    # hub-public-auth.md
    (".dreamwork/docs/plans/hub-public-auth.md", "watch.py", 11651, "watch.py", 6077, "tool"),
    (".dreamwork/docs/plans/hub-public-auth.md", "watch.py", 10756, "watch.py", 3797, "tool"),
    # posture-autonomy-axis.md
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 12967, "watch.py", 4313, "tool"),
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 13009, "watch.py", 4394, "tool"),
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 13040, "watch.py", 4437, "tool"),
    # posture-autonomy-axis.md:89 — REJECTED posture_line; corrected to route entry 6087
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 14170, "watch.py", 6087, "review_route"),
    # posture-autonomy-axis.md:90
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 13061, "watch.py", 4505, "tool"),
    # posture-autonomy-axis.md:281 — REJECTED off→file_notify; corrected to route entry 6087
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 14170, "watch.py", 6087, "review_route_dup"),
    # posture-autonomy-axis.md:297-301
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 12967, "watch.py", 4313, "tool"),
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 13009, "watch.py", 4394, "tool"),
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 13040, "watch.py", 4437, "tool"),
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 13061, "watch.py", 4505, "tool"),
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 14066, "watch.py", 5863, "tool"),
    # posture-autonomy-axis.md:426 (two on same line)
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 13040, "watch.py", 4437, "tool"),
    (".dreamwork/docs/plans/posture-autonomy-axis.md", "watch.py", 13061, "watch.py", 4505, "tool"),
    # superseded-contracts.md
    (".dreamwork/docs/plans/superseded-contracts.md", "watch.py", 10267, "watch.py", 5533, "tool"),
    # task-store-schema.md
    (".dreamwork/docs/plans/task-store-schema.md", "watch.py", 6599, "ledger_parse.py", 66, "tool"),
    # task-transition-boundary.md
    (".dreamwork/docs/plans/task-transition-boundary.md", "watch.py", 8505, "watch.py", 5672, "tool"),
    (".dreamwork/docs/plans/task-transition-boundary.md", "watch.py", 6948, "watch.py", 2042, "tool"),
    (".dreamwork/docs/plans/task-transition-boundary.md", "watch.py", 6970, "watch.py", 2042, "tool"),
    # tasks-page.md
    (".dreamwork/docs/plans/tasks-page.md", "watch.py", 6558, "watch.py", 1619, "tool"),
    (".dreamwork/docs/plans/tasks-page.md", "watch.py", 6317, "watch.py", 1540, "tool"),
    # tasks-page.md:201 — REJECTED ledger_entries; corrected to ENTRY_HEAD at ledger_parse.py:37
    (".dreamwork/docs/plans/tasks-page.md", "watch.py", 6367, "ledger_parse.py", 37, "review"),
    (".dreamwork/docs/plans/tasks-page.md", "watch.py", 6450, "watch.py", 1570, "tool"),
    (".dreamwork/docs/plans/tasks-page.md", "watch.py", 6317, "watch.py", 1623, "tool"),
    # tasks-page.md:1015 — REJECTED LEDGER_ID; corrected to _open_ids at watch.py:1648
    (".dreamwork/docs/plans/tasks-page.md", "watch.py", 6448, "watch.py", 1648, "review"),
    (".dreamwork/docs/plans/tasks-page.md", "watch.py", 6450, "watch.py", 1570, "tool"),
    # tasks-page.md:1112 — REJECTED landed_ids; corrected to _LEDGER_SNAPS at watch.py:1619
    (".dreamwork/docs/plans/tasks-page.md", "watch.py", 6558, "watch.py", 1619, "tool_dup"),
    # user-event-journal-implementation.md
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8066, "watch.py", 4721, "tool"),
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8389, "watch.py", 5380, "tool"),
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8128, "watch.py", 5380, "tool"),
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8387, "watch.py", 4639, "tool"),
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8505, "watch.py", 5672, "tool"),
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 7423, "watch.py", 2561, "tool"),
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8026, "watch.py", 4603, "tool"),
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8433, "watch.py", 2561, "tool"),
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8354, "watch.py", 5366, "tool"),
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8387, "watch.py", 5380, "tool"),
    # user-event-journal-implementation.md — RESOLVED refusals (_send ambiguous → watch.py:5081)
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8231, "watch.py", 5081, "disambig"),
    (".dreamwork/docs/plans/user-event-journal-implementation.md", "watch.py", 8231, "watch.py", 5081, "disambig_dup"),
    # user-settings.md
    (".dreamwork/docs/plans/user-settings.md", "watch.py", 13859, "watch.py", 4164, "tool"),
    (".dreamwork/docs/plans/user-settings.md", "watch.py", 13688, "watch.py", 6077, "tool"),
    (".dreamwork/docs/plans/user-settings.md", "watch.py", 15460, "watch.py", 6077, "tool"),
    (".dreamwork/docs/plans/user-settings.md", "watch.py", 13903, "watch.py", 4264, "tool"),
    # user-settings.md:123 — REJECTED _handle_posture for 14011; corrected to resolve_posture at 4394
    (".dreamwork/docs/plans/user-settings.md", "watch.py", 14011, "watch.py", 4394, "review"),
    (".dreamwork/docs/plans/user-settings.md", "watch.py", 15246, "watch.py", 5863, "tool"),
    (".dreamwork/docs/plans/user-settings.md", "watch.py", 15460, "watch.py", 6077, "tool"),
    (".dreamwork/docs/plans/user-settings.md", "watch.py", 13688, "watch.py", 4207, "tool"),
    (".dreamwork/docs/plans/user-settings.md", "watch.py", 14936, "watch.py", 6077, "tool"),
    # reload-signal-design.md
    (".dreamwork/docs/reload-signal-design.md", "watch.py", 9185, "watch.py", 4280, "tool"),
    (".dreamwork/docs/reload-signal-design.md", "watch.py", 7571, "watch.py", 1360, "tool"),
    (".dreamwork/docs/reload-signal-design.md", "watch.py", 9055, "watch.py", 3553, "tool"),
    (".dreamwork/docs/reload-signal-design.md", "watch.py", 9123, "watch.py", 3797, "tool"),
]


def apply(doc_rel: str, old_path: str, old_line: int, new_path: str, new_line: int) -> int:
    path = ROOT / doc_rel
    text = path.read_text(encoding="utf-8")
    old = f"{old_path}:{old_line}"
    new = f"{new_path}:{new_line}"
    if old not in text:
        return 0
    # For ledger_parse.py anchors, don't create back-to-back :N: by matching substrings
    # Simple replace is safe because the old citation is past-EOF (won't match in-range)
    count = text.count(old)
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    return count


def main():
    # Deduplicate by (doc, old_path, old_line) — multiple entries for same citation
    # are the same replacement (e.g., posture has 12967 at :85 and :297, both → 4313)
    seen = {}
    for doc, op, ol, np, nl, src in ANCHORS:
        key = (doc, op, ol)
        if key not in seen:
            seen[key] = (np, nl)

    total_replacements = 0
    for (doc, op, ol), (np, nl) in sorted(seen.items()):
        n = apply(doc, op, ol, np, nl)
        if n:
            print(f"  {doc}: {op}:{ol} -> {np}:{nl}  ({n} occurrence(s))")
            total_replacements += n
    print(f"\nTotal: {total_replacements} replacements across {len(seen)} unique citations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
