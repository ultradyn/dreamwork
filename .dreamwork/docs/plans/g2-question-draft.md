# Draft questions.md entry — #591 (G2 × claude design) — for the coordinator to file

The coordinator is `questions.md`'s single writer; this file is the text to place, verbatim or
trimmed. Timestamp is the coordinator's to set. Priority P1 proposed: this is the one open call on
the critical path of his 2026-07-31 focus (the bundle step must not decide it by accident).

---

- **P1 · 2026-07-31 — #591: claude-design compatibility does NOT cost the single render authority — one ruling makes it official.**
  **Sub-decisions:** `Q1`, `Q2`, `Q3`
  Analysis: `.dreamwork/review/505-g2-render-authority.html` (artifact, IGC inside) +
  `.dreamwork/docs/plans/render-architecture.md` (§Status 2026-07-31 — also records that #505's G4
  "no build step" goal is retired per your 2026-07-30 ruling, `0f97df03`). Your 2026-07-31 focus
  makes *"compatible with claude design"* a goal, and #505 G2 (one render authority) looked like
  the casualty: a design tool needs components, this dashboard renders through string builders, and
  the standing rule — *"two renderers only agree on the day they are written"*
  (`dreamhub-design.md:197`) — refuses a second renderer. **Verified against claude design's own
  ingestion spec** (the `design-sync` skill Anthropic bundles in Claude Code 2.1.220, read this
  session; public support docs corroborate): it imports a compiled **React** bundle of your *real*
  components (`window.<globalName>` + per-component `.d.ts` + usage docs), its component path is
  React-only (*"a non-React DS has nothing for the claude.ai/design agent to build with"*), a
  tokens-only fallback exists (CSS/tokens/fonts skin its *generic* components), and its core
  principle is your rule in the tool's voice: *"ship what the customer already built — the bundle
  is their compiled dist/, **never a reimplementation**."* Your 16:38 submission (receipt
  `a71d1105…`) added two independent goals — the component-native session view (*"only be available
  via that"*) and the WS/RPC state-delta model — which refute "no component system" **on their own**
  but do not move the survivor. The IGC (6 ideas × 8 goals) has **one All-✔ survivor**: a
  **derived component surface + born-native new surfaces** — the bundle step compiles the same
  `client/*.js` files watch.py serves into a React package of thin delegating wrappers (no markup
  restated, so nothing can diverge) plus the real `style.css`/tokens; new surfaces like the session
  view are written as components from their first line, with no builder twin, in the same system.
  Refuted: a parallel hand-maintained component library (✘ G2 — and ✘ the tool's own principle);
  wholesale migration (✘ incremental/reversible: `qaCard` renders on every surface, so per-view
  migration forks it and the alternative is a flag day; gestures re-proven from scratch); web
  components (✘ verified: the runtime is React-only); no component system (✘ three ways now).

  - **`Q1` — ratify the per-surface reading: one render authority *per surface*, and a derived
    surface is not a second authority?** **`rec: yes.`** G2 refuses two *maintained* truths about
    the *same* surface (the rule was coined refusing a JS row renderer beside the Python one
    rendering *the same rows*). Under this reading the builders stay the one authority for every
    surface they own; wrappers delegate; native surfaces have no builder counterpart; shared
    primitives (ages, `label`, expand) keep one truth via delegation in whichever direction. Alt:
    rule that G2 refuses even a derived surface — then claude-design compatibility caps at
    tokens-only and the session view's component system re-derives the page's primitives, which is
    the drift shape the rule exists to prevent.
  - **`Q2` — the claude-design breakpoint: component-level, or tokens-level?**
    **`rec: component-level, staged`** — tokens+CSS ship first (nearly free: `client/style.css` is
    a real 1,844-line file today; the design-sync artifact set carries it regardless), delegating
    wrappers follow as the bundle step's second stage. Alt: tokens-only ceiling — cheapest, but the
    tool then designs with *its* generic components wearing your skin: a reimplementation of your
    UI at the tool's end, stale from the day it is made.
  - **`Q3` — the component system's framework?** **`rec: React.`** Not preference — the only
    immovable constraint in sight: claude design's runtime is React, and running one system for
    both the design bundle and on-page native surfaces (session view) is one vocabulary. Alt: a
    lighter on-page runtime (preact/lit) + React only for the bundle — defensible if the page must
    not carry React's weight, at the price of two component idioms, which is the two-truths smell
    one level up.
  - **What would reopen this:** if you want the design tool (or the page) to *recompose component
    interiors* — the pieces inside a question card as first-class parts — only a real migration
    delivers that, at the price its row shows. Say so and #591 reopens with that goal on the board.
    Nothing in your stated focus asks for it, so it is priced, not asked. The session view's own
    UI/UX design (your "ask clarifying questions early" + mockups) is deliberately a separate,
    later ask — this ruling only fixes *where* that surface lives.

  **If you say nothing:** nothing is built — the analysis authorises no code. The recs stand as the
  framing the bundle step is planned against, and the bundle step still cannot decide G2 by
  accident: that is what this ruling exists to prevent.
  Accepted answers: `rec` (takes all three) · per-question (`Q1: …`) · free text.
