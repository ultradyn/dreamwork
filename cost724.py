"""Cost measurement for #724: how many (sha, tid) comparisons reach the
subtraction line, and what does rev-parse resolution cost on that set?"""
import subprocess, sys, time, re
sys.path.insert(0, "dev")
from pathlib import Path
import ledger, lint, watch

DW = Path("/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork")
text, source = lint.ledger_view(DW)
commits = ledger._git_subjects(".", None)

# replicate sweep's loop up to the subtraction line to count comparisons
open_ids, _ = watch.parse_ledger(text)
bodies = {}
for ids, body in ledger.ledger_entries(ledger.open_section_text(text) or ""):
    for tid in ids:
        bodies[tid] = body

comparisons = 0
compared_shas = set()
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
for sha, subject in commits:
    m = ledger.SWEEP_SUBJECT.match(subject)
    if not m:
        continue
    id_text = next(g for g in m.groups() if g)
    for tid in (int(x) for x in ledger.SWEEP_ID.findall(id_text)):
        if str(tid) not in open_ids:
            continue
        comparisons += 1
        compared_shas.add(sha)

print(f"commits: {len(commits)}")
print(f"comparisons reaching the subtraction line: {comparisons}")
print(f"distinct commit shas compared: {len(compared_shas)}")

# cost: resolve each compared commit sha + each cited sha in the compared bodies
# Approach: for each comparison, resolve the commit sha (from %h, already unique)
# and check if any cited sha in the body resolves to the same full sha.
cited_in_compared_bodies = set()
for sha in compared_shas:
    m2 = ledger.SWEEP_SUBJECT.match(next(s for sh, s in commits if sh == sha))
for tid_str in open_ids:
    tid = int(tid_str)
    if tid in bodies:
        for s in SHA_RE.findall(bodies[tid]):
            cited_in_compared_bodies.add(s)
print(f"distinct cited shas in ALL open bodies: {len(cited_in_compared_bodies)}")

# time resolving all compared commit shas + all cited shas
to_resolve = list(compared_shas) + list(cited_in_compared_bodies)
print(f"total rev-parse calls needed (pre-computed set): {len(to_resolve)}")

t0 = time.perf_counter()
resolved = {}
for s in to_resolve:
    out = subprocess.run(["git", "rev-parse", s], capture_output=True, text=True)
    if out.returncode == 0 and len(out.stdout.strip()) == 40:
        resolved[s] = out.stdout.strip()
t1 = time.perf_counter()
print(f"rev-parse {len(to_resolve)} shas: {(t1-t0)*1000:.1f} ms")

# baseline: current sweep cost (substring only)
t0 = time.perf_counter()
n, findings = ledger.sweep(text, commits)
t1 = time.perf_counter()
print(f"current sweep (substring, no resolution): {(t1-t0)*1000:.1f} ms, flagged {len(findings)}")
