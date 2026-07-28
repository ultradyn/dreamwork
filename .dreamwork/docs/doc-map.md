# Doc map — ud-dreamwork (the skill, self-hosted target)

What lives where, and what the loop keeps current. Link outward; never
duplicate content that has a home below. Single-source rule: a fact
lives in exactly one doc — generic reference (useful to every target)
at the skill root, instance-specific knowledge under `.dreamwork/` —
and everything else points at it. The skill root is shipped product:
this instance is its upstream maintainer, so docs-freshness passes
cover it too.

| Doc | Covers | Loop keeps current? |
|---|---|---|
| `SKILL.md` | The product: philosophy, loop, selection, subagents, durable state, commands, guardrails | Yes — every behavior change lands here or in a reference file |
| `initialization.md` | The 11-step init procedure | Yes |
| `reflection.md` | Post-change checklist | Yes |
| `file-formats.md` | Required shapes for loop-written, tool-parsed files; questions.md in full | Yes — a reader change lands here in the same commit |
| `.dreamwork/docs/reviews-*.md` | Fresh-eyes review findings, kept whole; the fixes land separately | Keep while its proposals are unspent |
| `compaction.md` | Pre-compaction checklist, the notice protocol, per-client sending safeguards | Yes — client dialects change |
| `writing-plugins.md` | Plugin-authoring contract, extension seams, state split | Yes — validate against each new plugin |
| `watch-design.md` | watch.py standing design: routes, confinement, write exceptions, contract | Yes — shipped beside the tool it documents |
| `stop-hook-variant.md` | Unimplemented wake fallback design | Only if implemented or invalidated |
| `DREAMWORK.template.md` | Wizard seed for new targets | Yes — must track wizard section changes |
| `migrations/` | Versioned target-affecting changes; latest filename = version | Append-only; README holds the protocol |
| `.dreamwork/docs/plans/` | Active feature plans, alphabetical (answers-page, artifact-templates, composer-row, daemon-mode, draft-durability-design, dreamhub-stage1, filebytes-range, goal-hierarchies, heartbeat-into-monitor, hub-public-auth, hub-ssh-auth, lan-bind, note-reply-threading-254, parallel-architecture, question-instruction-options, questionnaire-survey, review-essential-marks, subagent-containment, task-store-schema, task-transition-boundary, tasks-page, threaded-notes-spec, ud-dreamtask, ud-dreamwork-github, user-event-journal, user-event-journal-implementation, version-and-upgrade, watch-client-extraction) | Prune when features fully land; `lint.py` fails the row against the directory |
| `.dreamwork/docs/research-*.md` | What a commissioned answer MEANS for this project; the research itself goes to the KB when it is generic | Keep while the conclusion holds |
| `.dreamwork/docs/spikes/` | Timeboxed experiments that answered a question with a number; the branch holds the diff | Keep — a measured answer outlives the code that produced it |
| `.dreamwork/review/` | Rich decision artifacts paired with a questions.md entry | Banner them decided; archive with the answered question |
| `.dreamwork/{lessons,questions}.md` | Distilled lessons; asks for the human | Yes — groomed in rotation |
| `.dreamwork/tasks.md` | The queue's durable half: open tasks, permanent ids, next id | Yes — same commit as any queue change |
| `.dreamwork/docs/github-processes.md` | The repo's GitHub shape and conventions (ud-dreamwork-github plugin) | Yes — re-survey when CI, labels, or PR flow appear |
| `README.md` | Public face of the repo: what dreamwork is, install, where to start | Yes — must not drift from SKILL.md |
| `relay.py` | Appends a coordinator message to a subagent inbox — body from stdin, stamp from the clock | Yes — it encodes two failures, not a convenience |
| `transitions.md` (skill root) | How the page moves — the ONLY source; every transition obeys it, and CLAUDE.md says so | Yes — extracted from watch-design.md so there is one description, not two |
| `igc-method.md` / `igc-concepts.md` (skill root) | The IGC method + its Critical-Fallibilism conceptual grounding, **vendored** from the `use-igcs` skill so an install without it still has the method; each file carries the upstream sha it was synced from | Yes while vendored — re-sync on the docs-freshness rotation if the upstream *application rules* change (decision + matrix: `igc-bundling.md`) |
| `CLAUDE.md` (skill root) | Rules for agents working ON this repo (not for the loop running elsewhere) | Yes |
| `lint.py` | Checks a target's `.dreamwork/` against the shapes its readers require, by calling the real readers | Yes — a reader change lands here in the same commit |
| `deployed.py` | Which revision a target's dashboard is ACTUALLY serving, by byte-comparing the deploy snapshot against history. `python3 deployed.py --target .` | Yes — the deploy snapshot's identity is recorded nowhere else |
| `dev/ledger.py` | The one supported way to fold a ledger entry and count open/landed ids (#440): reuses `watch.parse_ledger` and the anchored heading patterns, asserts the two headings are unique and ordered before AND after every write. `python3 dev/ledger.py counts`, `python3 dev/ledger.py fold <id> --note <text>` | Yes — the anti-corruption invariant it enforces lives in it, not in a linter reading the aftermath |
| `.dreamwork/docs/reload-signal-design.md` | #426's design: the identity signal a running agent reads to tell its own tree moved; the per-surface reload actions; the `#263` lane-H "shared mechanism?" decision (no); what is not worth building | Keep while its recommendations are unspent; the one increment that landed (`watch.skill_identity()`) is documented in `watch.py`'s docstring |
| `.dreamwork/docs/migrate-watch-symlink.md` | The procedure (and per-step checks) for #368's first increment flipping `watch.py` to a symlink to `deprecated/watch.py`; the #425 safety net it depends on, and the `serving_report`/`deployed.py` interactions #368 must close | Yes while #368's symlink has not landed; prune when it does |
| `.dreamwork/docs/plans/hub-ssh-auth.md` | #360's design + docs (ssh-rooted self-hosted hub auth). SUPERSEDES `hub-public-auth.md`'s identity recommendation (Cloudflare Access/Tailscale as the boundary); EXTENDS its threat model, TLS analysis and `/data.json`-leak (C2), which are inherited not re-derived. Supersedes `#276`'s LAN bearer token if option 2 (session key over ssh) lands. Four options compared — ssh tunnel (document now), session-key-over-ssh (build first, behind a local Caddy per his Q2 ruling), user/pw (fallback, not worth building standalone), SQRL (no — dormant + stdlib-blocked) | Prune when the chosen option fully lands; the ssh-tunnel recipe (§6) is documentation of what works today and outlives the decision |
| `.dreamwork/docs/igc-bundling.md` | #447's decision to bundle IGC by vendoring (option D) — its IGC matrix (A/B/C/D × six goals), the staleness story, the SKILL.md placement at the four judgement sites, the lint-check decline reasoning, and the downstream effect on ud-dreamtask | Keep while the bundling decision stands; the matrix records why D over A/B/C |
| `.dreamwork/docs/open-task-census.md` | #420 inventory of the open ledger: derived open/landed counts, blocking posture, stale blockers, duplicates; coordinator working doc, not a proposal | Refresh when the dispatch question is inventory again; superseded for *selection* by dispatch-shortlist |
| `.dreamwork/docs/dispatch-shortlist.md` | #437 ranked 8–12 startable tasks with ownership sets, live-lane conflicts, size, and parallel-safe groupings — the dispatch view on top of the census | Yes while used for selection; overwrite on each re-run; prune when a standing tool replaces it |
| `.dreamwork/docs/mitigation-audit.md` | #416 dated re-check of the four unchecked `~/CLAUDE.md` system-mitigation records (Brave ozone, sccache-server, pi-powerline-footer patch, ntp-force-sync.timer): one-line command + verbatim output + holds/drifted/gone per claim; reword proposals only (does not edit `~/CLAUDE.md`) | Refresh when a mitigation is claimed or after package upgrades that overwrite local patches; prune when the four claims are folded into a standing check |
| `.dreamwork/docs/containment-deficiency.md` | #450 boundary statement for the containment the loop does not have: a per-harness capability table over what it actually dispatches (`ccc @grok`/`ccc @glm52` — tool calls not interceptable today, whole-harness containable but self-defeating), the trusted-nodes precondition stated where dispatch acts on it, the three seams that keep later isolation possible (the prototype, the positive PID/health invariants, the dispatch point), and the warning copy for a harness row. Implements the 2026-07-29 ruling on `#288`; the design + prototype live in `plans/subagent-containment.md` | Keep while the wall stays prototyped-not-wired; revise when a lane wires the wall, when a runner's interception seam gets investigated, or when the trusted-nodes precondition changes |
| `.dreamwork/docs/draft-durability-status.md` | #269 empirical status: what draft durability actually guarantees (process restart, write trigger/debounce, per-box coverage, clear-on-success, localStorage vs IndexedDB) with cited lines and Playwright observations — not the design (`plans/draft-durability-design`) | Keep while #269's remaining scope is open; fold or prune when the ledger entry closes |
| `dreamhub-design.md` | dreamhub standing design: the stage-1 boundary and its checks, the origin-per-project deviation, and the exact status.json / watch-port / `/mtime` / `/data.json` fields the hub depends on (guards: `dev/hub/README.md`) | Yes — shipped beside the tool it documents |
| `roll.py` / `watch.py` / `heartbeat.py` / `dreamhub.py` docstrings | Tool contracts (advisory dice; dashboard; the wake tick; the multi-project hub) | Yes — contracts live in the docstrings |
| `test_watch.py` / `test_roll.py` / `test_heartbeat.py` / `test_lint.py` / `test_relay.py` / `test_deployed.py` | The Python half of verification — asserts on generated source, cannot see what renders | Yes — a behaviour change ships with its test |
| `dev/capture/` | The structural half: browser guards (exit non-zero, gated by `just test`) plus print-only capture scripts | Yes — a guard joins `GUARDS` when its feature lands |
| `dev/capture/fixture/` | Frozen miniature target the guards run against, so a red light means the code broke | Yes — extend it when the parser learns a new input shape |
| `justfile` | Common tasks: test (both halves), pytest, guards, watch, audit-styleguide | Yes — a new routine worth repeating becomes a recipe |
| `DREAMWORK.md` (repo root) | This target's own goals, philosophy, preferences, plugin decisions | Yes — folded whenever the human reveals a durable preference |
| `../ud-dreamtask/SKILL.md` (sibling repo) | The bounded one-errand loop; inherits this skill's Guardrails, Subagents and Durable-state sections **by reference** | Yes — a change to those sections changes dreamtask's behaviour too, and a rename orphans a live pointer |

**Routing rule — a finding lands where its trigger lives.** Behaviour
that must fire unprompted goes in SKILL.md; the shape of a file goes in
`file-formats.md`; a procedure with a nameable trigger (init,
compaction, plugins) goes in that trigger's reference file; and **craft
— how to write a good ENTRY in something — goes in that file's own
header**, which is the best trigger available because the writer is
already looking at it (#145). `lessons.md` and `tasks.md` both work this
way already. SKILL.md is
re-read on every reload and fires on nothing in particular, so it is the
default destination only for things with no better trigger — it grew 246
to 433 lines in one day by being everyone's default (#120, #145).

SKILL.md is the entry point for the harness; README.md is the entry
point for a human browsing the forge. The README stays minimal on
purpose — what this is, how to install it, where to look — and every
fact in it has its home in a doc above.
