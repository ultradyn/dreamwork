# Lessons retrieval (#349) — IGC and decision

**Context.** `.dreamwork/lessons.md` is 299 entries / ~3200 lines. The
recorded failure: the 2026-07-25 lesson "revert a deliberate RED injection
with the inverse, never `git checkout <file>`" (lessons.md:757) did not
prevent its own repeat on 2026-07-28 — nothing re-reads 3000 lines before
acting, and the file's only retrieval path is scrolling. The failure is the
READING, not the writing. Binding constraints from the entry: the fix is
NOT summarisation (the evidence half is why the format exists —
file-formats.md) and NOT pruning (few lessons have graduated; pruning costs
memory without buying readability — measured). Posture is `inform`: the
choice is documented here for his review; nothing destructive (no pruning,
no restructuring of existing entries) without him.

## Measurements that decided it

- 299 entries, mean >1 act per entry (a first-pass taxonomy of 8 acts
  classifies 269/299; multi-act membership is the norm, not the exception).
- Whole-corpus pairwise first-sentence similarity (difflib ratio on the
  normalised claim, token-Jaccard without stopwords): exactly ONE pair is a
  true near-duplicate — lessons.md:580 vs :622, the same "guard assertion
  whose subject may not exist must never throw" lesson written twice in one
  batch (d=0.790, j=0.636). Next-highest pair in the file: d=0.645.
- The rule `d>=0.78 AND j>=0.50` catches a near-verbatim repeat of :757
  (d=0.93) but misses genuinely re-worded ones (d=0.37–0.63). So a
  similarity check is a WRITE-time backstop only; it cannot be the
  retrieval fix.

## Matrix

Goals — G1: the loop READS the relevant lesson before the act it governs
(the recorded failure). G2: keeps the evidence half of every entry. G3: no
hand-maintained artifact that can go stale. G4: no destructive change
without him. G5: honest about its own misses (a retrieval tool that
silently misses is the file's failure one level up). G6: cost proportionate
to a P2.

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 |
|---|---|---|---|---|---|---|---|
| I1 generated act→lessons index, consulted at the moment of the act | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| I2 split lessons.md by act | ✘ | ✔ | ? | ? | ✘ | ? | ✔ |
| I3 lint: refuse a NEW lesson whose first sentence near-duplicates an existing one | ✘ | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ |
| I4 = I1 + I3 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

Decisive errors:

- **I2 (G4):** splitting restructures 299 existing entries — excluded by
  the inform posture. Secondary (G2/G3): entries govern more than one act
  (measured above), so a by-act split either mis-files them or duplicates
  them, and duplication is drift.
- **I3 alone (G1):** it gates WRITING a repeat, not READING before the
  act — the 2026-07-28 repeat was an action, not a new entry, so I3 alone
  leaves the recorded failure open. Its catch radius is also near-verbatim
  only (measured), which limits it to backstop duty even at write time.
- Rejected framings: a hand-maintained index (G3 — the next stale file) and
  a summarised index (G2 — loses the evidence half).

**Decision: I4.** I1 is the retrieval fix — `dev/lessons_index.py` derives
an act→lessons index from the entries' own text at read time (never stored,
never hand-maintained), prints the relevant slice verbatim with
`lessons.md:N` cites, and REPORTS its coverage (indexed vs unclassifiable,
unclassifiable named by line). I3 is the write-time backstop — a lint check
that ERRORs when a lesson absent from `HEAD:.dreamwork/lessons.md`
near-duplicates any existing first sentence, and WARNs on the one
pre-existing repeat pair (:580/:622) so HE sees it without me touching the
file. SKILL.md points the coordinator at the relevant slice at the moment
of the act; CLAUDE.md's Verification section points at it before an
injection.

## Risks accepted

- The act taxonomy is a fixed list of anchor regexes in the tool; an entry
  using none of the vocabulary lands in the unclassifiable report (named by
  line, so the gap is visible, and the report is the tool's own G5
  obligation).
- I3's ERROR window is pre-commit: a duplicate that gets committed anyway
  drops to the standing WARN row. Accepted — lint runs before commit is the
  repo's norm, and the WARN never goes silent.
