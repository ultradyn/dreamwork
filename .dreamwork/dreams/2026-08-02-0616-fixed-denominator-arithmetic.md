# 2026-08-02-0616 — the fixed-denominator family and the arithmetic that survives repair

## The insight

The #937 defect has a cleaner statement than the brief gave it, and finding it
changed the tool's design.

The brief frames it as "a denominator that cannot notice it is too small" — the
mirror of #868 (a denominator that can silently reach zero). That is right. But
the arithmetic the brief draws (`enrolled=19 detected=52 unenrolled=33`) only
holds **pre-repair**, when enrolled rows still carry the bad pin. After the
campaign's 19 repairs landed, the enrolled rows no longer carry `@ dc739001`, so
`detected` dropped to 33 (the unenrolled residue) and `detected − enrolled`
became `33 − 18 = 15`, which is meaningless.

The honest formula is `unenrolled = detected − covered`, where `covered` counts
detected occurrences whose `(doc, token)` identity IS enrolled AND pinned to the
bad revision. Pre-repair: `52 − 19 = 33`. Post-repair: `33 − 0 = 33`. **The
number is stable across repair** because it counts occurrences the ledger never
enrolled, not occurrences it enrolled and then fixed. That stability is the
property that makes the tool useful at every stage of the campaign, not just at
measurement time.

I almost built `unenrolled = detected − enrolled` (the naive subtraction the
brief's example suggests). It would have reported 15 today and 33 before the
repairs — a number that means different things at different times and explains
nothing. The covered/identity-matching approach costs 6 lines and reports a
number that means the same thing always.

## The line-vs-occurrence trap, fourth instance

The ledger records `grep -c` undercounting handoffs.md (7 lines, 8 occurrences —
one line carries two pins). My measurement found it again in two more documents:
`551-posture-remind.md` (3 lines, 4 occurrences) and `render-architecture.md`
(1 line, 2 occurrences). That is the same disease in a fourth organ tonight. The
tool counts occurrences (`-o` semantics) and attributes both pins on a single
line to their respective tokens — which is how it correctly named
`watch.py:3984-3996` as unenrolled on a line whose other citation
(`watch.py:3999-4006 @ 4e83d224`) is enrolled and repaired.

This is `lessons.md`, "A tool built to stop a failure, bypassed by hand,
reproduces that exact failure" — but the specific instance (grep counting lines
when the corpus carries two pins per line) may not have its own lesson yet. If
it does not, it should: it has now bitten the census, the coordinator's
handoffs.md repair, and two more documents, all in one night.

## Out-of-scope: the 29 vs 33 distinction

4 of the 33 detected occurrences in `citation-anchoring-design.md` are not
citations at all — they are prose discussing the `@ dc739001` pin as a concept
("stripping one `@ dc739001` from…"). They have no `watch.py:NNNN` token and no
enrollable identity. They are always unenrolled by construction. The tool marks
them `PROSE (no citation token)` so a reader does not mistake them for pins to
judge.

The honest "stale pins needing judgement" count is 29, not 33. Anyone who reads
the headline number as "33 stale pins to repair" over-counts by 4. This is not a
tool defect — the tool faithfully reproduces the brief's measurement methodology
(`git grep -o '@ dc739001'`) — but it is a reading hazard the coordinator should
know about when dispatching the next increment.

## The direction-2 I could not close

Blind spot #1 is real and I proved it: a corpus with `watch.py:42 @ dc739001`
(detected) alongside `watch.py:99 @ a1b2c3d` (a different stale revision) makes
the tool report `detected=1 unenrolled=1` and exit 0, with the `a1b2c3d` pin
completely invisible. The campaign is about dc739001 because that is where it
started, not because that is the only wrong pin. Closing this means scanning
every `@ <hash>` pin — a separate increment, and #925's ruling forbids
open-corpus detection for verdicts. I report it; I do not close it.

The one consolation: a corpus with ONLY a non-dc739001 stale pin (no dc739001
at all) triggers `detected=0` vacuity and exits 2 loudly. So the tool is not
silent when the entire dc739001 population is gone — it is silent only when
dc739001 pins coexist with other-revision stale pins. That is the narrower,
honest statement of the blind spot.
