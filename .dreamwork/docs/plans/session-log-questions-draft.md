# #613 — draft questions.md entry (lane-sessionlog)

> Draft only. The coordinator is `questions.md`'s single writer; the block
> between the markers is the exact text to place under `## Open`. The
> mockup artifact carries its own three visual calls (Ind/Guides/Marker)
> with recs inside the artifact itself — deliberately kept out of this
> entry so the ask here stays three questions, not six.

<!-- BEGIN questions.md entry -->

- **P1 · 2026-07-31 — #613: the live session-log view — three calls before the design locks.**
  **Sub-decisions:** `Q1`, `Q2`, `Q3`
  Design: `.dreamwork/docs/plans/session-log-view.md` (design only; no code authorised). Mockups,
  which you asked to see before the component design locks: `.dreamwork/review/session-log-view.html`
  — the tree at rest and mid-stream, plus live alternatives for the three visual calls (indicator
  motion, indent guides, marker glyphs), each with a rec you can take with one word. Everything
  below was measured against the real 82 MB session file: compaction pages ARE derivable
  (`compact_boundary` records), turn/step boundaries are derivable, the file is append-only under
  growth (so line+byte bookmarks are stable, as you assumed), a full rescan costs 1.0 s, and
  `system_prompt` is the one slot in your hierarchy Claude Code never writes to the transcript —
  the tree will honestly have no such child rather than inventing one.

  - **`Q1` — your sentence "should use new component system and only be available via that": may I
    read it as "never a second hand-rolled rendering path" rather than "wait for #591"?** The
    component system it presupposes does not exist yet — whether one should is exactly `#591`/`#505`
    G2, open and explicitly not to be decided by accident. The design keeps everything
    (data model, API, scan path, visuals) ruling-independent; only the mount binding changes with
    the ruling. **`rec: build the interim now`** — one `SessionLog` component with a narrow
    props/events contract, living under the existing single render authority, exactly your "make 1
    simple component now but let us swap it out later"; when `#591` rules, the same contract is the
    new system's first citizen. Alt: block the view until `#591` is ruled — serialises this P1
    behind an open ruling and buys nothing the declared seam doesn't already.
  - **`Q2` — the file watcher: there is no inotify in the Python stdlib, and the stdlib-only
    constraint stands. Which mechanism?** **`rec: real inotify via ~70 lines of ctypes against
    libc, behind one `SessionWatcher` seam, with an automatic bounded stat-poll (0.5–1 s) degrade`**
    (non-Linux, or inotify init failure) — your no-polling design where the platform supports it,
    and the fallback is the same code path with worse latency, not a quiet substitution. Alt:
    stat-poll only for v1 — ~15 lines, cannot break, and behaviourally indistinguishable while the
    browser still ticks at 2 s; the server-side watcher only becomes the latency floor after
    `#614`'s push transport lands. Costs of the rec: ctypes struct-parsing, Linux-only primary, a
    real test for the fd lifecycle.
  - **`Q3` — which session IS the running agent? Nothing records it today (measured: no session
    identity in status.json, heartbeat, or any loop file).** **`rec: infer for v1`** — newest
    live-mtime `*.jsonl` in the client's project dir for the target cwd, with a visible "which
    session" switcher as the correction affordance — **`and fold self-reporting into per-client
    onboarding`** (the loop writes `{client, session_id}` into `status.json` at orient), which is
    the same per-client seam `#615`'s subagent tasks need anyway. Alt: self-report only (blocks the
    view on a loop-side change landing first); infer only (ambiguous under multiple sessions
    forever).

  **If you say nothing:** nothing is built — the design authorises no code; the recs (and the
  mockup's A + G1 + M1) stand as defaults when the implementation is planned.
  Accepted answers: `rec` (takes all three + the mockup's three) · per-question (`Q1: …`) · free text.

<!-- END questions.md entry -->
