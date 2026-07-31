"""Measurement for #724: how many open ids does sweep flag ONLY because of sha width?

Whole-history sweep, then for each flagged finding check whether the body cites
a short prefix of the flagged commit's full sha (the width-mismatch case).
Resolves via `git rev-parse`, never startswith against the short %h.
"""
import subprocess, re, sys
sys.path.insert(0, "dev")
from pathlib import Path
import ledger  # the worktree's own copy (#607)
import lint

DW = Path("/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork")
# Use the SAME dispatch the real sweep uses (#671), not the raw markdown file —
# the store is the source of truth, so raw markdown has no ## Open section.
text, source = lint.ledger_view(DW)
print(f"source of truth: {source}")

# whole history — pass since=None by giving sweep ALL commits
commits = ledger._git_subjects(".", None)
print(f"commits over whole history: {len(commits)}")

n, findings = ledger.sweep(text, commits)
print(f"sweep examined {n}, flagged {len(findings)} open ids (whole history)\n")

SHA = re.compile(r"\b([0-9a-f]{7,40})\b")

def resolve(short):
    """Return full 40-char sha for a short prefix, or None if unresolvable."""
    try:
        out = subprocess.run(["git", "rev-parse", short],
                             capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            return None
        full = out.stdout.strip()
        # rev-parse echoes the input back if it can't resolve; require 40 hex
        if len(full) == 40 and re.fullmatch(r"[0-9a-f]{40}", full):
            return full
    except (OSError, subprocess.SubprocessError):
        pass
    return None

width_only = []
other = []
for tid, rows in findings:
    body_for_tid = ""
    for ids, body in ledger.ledger_entries(ledger.open_section_text(text) or ""):
        if tid in ids:
            body_for_tid = body
            break
    # candidate shas that name this id
    flag_shas = {sha for sha, _ in rows}
    flag_fulls = set()
    for s in flag_shas:
        f = resolve(s)
        if f:
            flag_fulls.add(f)
    # shas cited in the body
    cited_short = SHA.findall(body_for_tid)
    cited_fulls = {c for c in (resolve(s) for s in cited_short) if c}
    # does any cited sha resolve to a flagged commit?
    overlap = flag_fulls & cited_fulls
    if overlap:
        # width mismatch: body cites the commit, but substring failed
        # show both widths
        details = []
        for fs in flag_shas:
            for cs in cited_short:
                if resolve(cs) == resolve(fs):
                    details.append((cs, fs, resolve(fs)))
        width_only.append((tid, details))
    else:
        other.append(tid)

print(f"=== FLAGGED ONLY BECAUSE OF WIDTH MISMATCH: {len(width_only)} ===")
for tid, details in width_only:
    for cited, flagged, full in details:
        print(f"  #{tid}: body cites {cited} ({len(cited)}c), git %h = {flagged} ({len(flagged)}c), full = {full}")

print(f"\n=== FLAGGED FOR OTHER REASONS (cited sha does not resolve to the flagged commit): {len(other)} ===")
print("  " + ", ".join(f"#{t}" for t in other))
