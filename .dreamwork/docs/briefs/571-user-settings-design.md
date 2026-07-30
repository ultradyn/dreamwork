# Brief #571 — DESIGN ONLY: persistent user settings, schema + seam + frontend exposure

Origin: human (his add-idea, journal ord=67, receipt 09a8897b, filed #571).
**This is a design task: produce a written design doc, an IGC, and a
recommendation. No production code is authorised.**

His words: *"Add persistent user settings in the database, probably just
store it as jsonb if you can. indexed by userid, ofc. this will give us
flexibility to then design and build a principled settings system for the
frontend, including tags for the settings, descriptions, support for
enums etc — actually, just check ~/src/refs/amr-ui/ for a good example
of what I'm thinking of, structurally."*

## Lane-owns

- NEW `.dreamwork/docs/plans/user-settings.md` — the design doc.
- A doc-map row if the repo's doc-map convention covers plans (check how
  prior plans are registered; follow the existing pattern).

**Explicitly not yours:** every production file. `watch.py`,
`ledger_store.py`, `lint.py`, `file-formats.md`, the justfile, the
ledger — all coordinator-owned or live-lane regions. This lane READS,
designs, and writes ONE new doc.

## What the design must settle

1. **Read the reference first**: `~/src/refs/amr-ui/` — he named it as
   the structural example (settings with tags, descriptions, enum
   support). Read how it models settings (schema, metadata, grouping)
   and say what maps and what does not.
2. **The store shape.** His sketch: jsonb, indexed by userid. Ground it
   in THIS repo's reality: the ledger store is SQLite (ledger_store.py),
   machine-local per clone by design (.gitignore C1, the #264 finding),
   and v1 is single-user. Questions the doc must answer: a new table in
   the ledger store vs a separate settings store; what "jsonb" means in
   SQLite (TEXT + JSON validation); whether userid is a real key in v1
   (single-user machine-local) or a forward-looking column.
3. **The settings model**: a setting has a key, a value, and metadata
   (tag/group, description, type incl. enum-with-closed-set, default).
   Where does the metadata live — in the DB per setting, or declared in
   code (a registry the DB only stores overrides for)? Look at how
   amr-ui does it. Note the posture file (`.dreamwork/posture`) is a
   PRECEDENT for declared-in-code settings with an on-disk override —
   the design must say how user settings relate to posture (are posture
   axes settings? is this a superset?).
4. **The read/write seam**: how the server reads settings (every
   collect()? cached with /mtime invalidation like #560's
   status_derive?) and how the page writes them (a new write route —
   E2Shadow + WRITE_ROUTE_HANDLERS implications; idempotency per #274).
5. **The frontend surface**: a settings page/panel — where it lives
   (the #295 answer already asked for "a settings page … a button group
   for these 3 options under a gfx settings section", and #228 is the
   standing unify-dashboard-settings task — READ both and reconcile).
6. **First consumers**, each named with what it needs: #573 (ask-me
   composer toggle), #570's future autoexpand-persistence setting, the
   #295 dither toggle (gfx section).
7. **An IGC** (his method — see .dreamwork/docs/igc-method.md if
   present, or the igc skill) over the genuine forks: store-in-ledger vs
   separate store; metadata-in-DB vs registry-in-code; posture
   relationship; settings page vs per-surface controls.

## The doc's shape

Follow the repo's design-doc pattern (see
`.dreamwork/docs/plans/orchestrator-posture.md` for a recent example):
context, the problem, the IGC (ideas × goals with refutations), the
survivor with a recommendation, sub-decisions surfaced as Q1..Qn with
recs for the human, and an explicit "authorises no code" line.

## Verification

- Design lane: no test red-proof applies. Review-gate standard: every
  factual claim about the codebase cites file:line verified while
  writing; the amr-ui claims cite paths in `~/src/refs/amr-ui/`.
- No ports, no browser, no servers. NEVER read_file an image.
- Commits: `git commit --only <paths>` (new file `git add`ed first).

## Handoff (#398)

`## Pending` line appended to the literal path
`.dreamwork/handoffs.md`: task id, bare shas, no parentheticals, no
model claims. Marker grep empty before finishing. Report: commits, the
IGC summary, the recommendation, the sub-decisions for the human,
amr-ui mappings, FLAGs, found-not-fixed.
