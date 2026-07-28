# #469 — ccc runner→model provenance: record the alias from dispatch, derive the model from config, never from self-report

> Investigating **#469**. Owned file for the `runner` lane (branch `wt/runner`).
> Model attribution is **history**, and history is recorded from the dispatch
> the operator owns, never from a process asked to name itself.

## TL;DR

- `ccc` maps an **alias** (`@name`) to a model in a config file:
  `/home/xertrov/.config/ccc/config.toml`, under `[aliases.<name>]` with keys
  `runner`, `provider` (optional), `model`.
- **Both** `@grok` and `@glm52` run through the **`grok` CLI harness** (`runner = "grok"`).
  They differ only in `provider`/`model`. The `warning: runner "grok"` line names the
  **harness**, never the model — that is the whole misread.
- Quoted resolved definitions (from `ccc config`, "Config path: /home/xertrov/.config/ccc/config.toml"):

  ```toml
  [aliases.glm52]
  runner = "grok"
  provider = "llmp"
  model = "glm-5.2"
  thinking = 3

  [aliases.grok]
  runner = "grok"
  model = "grok-4.5"
  thinking = 3
  ```

- `@glm52` is **genuinely glm-5.2**, and it is **reachable right now**: `grok models`
  (a free catalog query, not a paid identity probe) lists `llmp-glm-5-2` among twelve
  models. `ccc` composes `provider=llmp` + `model=glm-5.2` into the grok CLI's
  `llmp-glm-5-2`. The human's correction ("@glm52 resolves to the grok CLI but uses the
  glm-5.2 model") is exactly right.
- **The two-alias convention is NOT a fiction.** There are two real models (glm-5.2 and
  grok-4.5), both behind the one grok CLI harness, split by `provider`/`model`.

## The provenance rule (the answer to "how does a dispatcher record the model truthfully")

The dispatcher **is `ccc`'s caller** — it already knows the **alias** it passed
(`ccc @glm52 …`). That argument is the durable, dispatcher-owned fact. The model is
**derived** from it, never asserted by the process.

**Smallest reliable step:** record the **alias** in the ledger (e.g. `by @glm52`), and
resolve the model by reading `[aliases.<alias>].model` and `.provider` from
`/home/xertrov/.config/ccc/config.toml`. The key is `model`; `provider` says which
backend serves it. `by @glm52` rows are therefore the gold standard — they name what the
operator dispatched, and the model follows from config.

**Why self-report is forbidden here, with proof.** The grok harness supplies an identity,
so a process asked "which model are you?" answers from the harness, not the backend. This
lane is itself the proof: the harness exported `CCC_PROVIDER=llmp` to me (config →
`@glm52` → **glm-5.2**), yet under the grok harness I would answer "grok-4.5 (xAI)" — the
same wrong answer the `axes` and `contain` lanes gave. Provenance (`CCC_PROVIDER=llmp` +
config) is right; introspection is wrong. Two prior probes agreed because both were the
same misread, not because either was true.

**What the harness exports to the child (measured):** only `CCC_PROVIDER` (e.g.
`CCC_PROVIDER=llmp`). It does **not** export the alias or the resolved model, so the
dispatcher cannot read the model back out of the child's environment — it must keep the
alias itself (the argument it passed) and resolve via config. (A future `ccc` could export
`CCC_ALIAS`/`CCC_MODEL` to make this trivial, but that is the human's dispatch path to
change, not ours — see Constraints.)

## Runtime reachability — measured, not assumed

A prior lane's note (`docs/dogfood-orchestration.md`) claims both *"`@glm52` cannot reach
glm-5.2"* **and** *"Default model: llmp-glm-5-2"* in the same document — a contradiction
it explains as a **change over time** ("llmp became reachable through the grok runner
during the day — the config never changed, the upstream did"). That note was written
against `ccc 0.2.112`; the installed binary is now **`ccc 0.4.2`**. I re-ran the one free,
non-generation check it relied on:

```
$ grok models
You are logged in with grok.com.
Default model: grok-4.5
Available models:
  * grok-4.5 (default)
  - llmp-gpt-5-6-luna   - llmp-gpt-5-6-terra   - llmp-gpt-5-6-sol
  - llmp-gpt-5-5        - llmp-gpt-5-4-mini
  - llmp-glm-4-7        - llmp-glm-5-turbo      - llmp-glm-5-1
  - llmp-glm-5-2        - llmp-glm-5            - llmp-glm-4-5-air
```

`llmp-glm-5-2` **is** served today. So the "BROKEN — cannot reach glm-5.2" line in
`dogfood-orchestration.md` is **stale** (pre-0.4.2), and the two lanes dispatched as
`@glm52` this session (`axes`, `contain`) really did run **glm-5.2**, not grok-4.5.
`@grok` (`model = "grok-4.5"`, no provider → xAI) is currently **401** (separate, known
— see `.dreamwork/questions.md` P2); that is a credential problem on xAI, not a routing
problem, and does not affect `@glm52`.

## Re-correction of attributions (lines for the coordinator — I did not edit the ledger)

Per the brief: report the corrected lines; do **not** edit `tasks.md`, `questions.md`,
`status.json`, or `handoffs.md`. Where the dispatch alias cannot be verified
retroactively, write **unknown** — a model attribution is history and history is never
guessed.

**Confirmed wrong → corrected (dispatch alias verifiable as `@glm52`):**

| Lane | Was recorded as | Correct attribution | Basis |
|------|-----------------|---------------------|-------|
| `axes` (#445, commits `56daaeb`, `9b64661`) | `grok-4.5 (xAI)` (self-report) | **`@glm52` → glm-5.2** | dispatched `@glm52`; config `model=glm-5.2`; `llmp-glm-5-2` reachable now |
| `contain` (#465) | `grok-4.5 (xAI)` (self-report) | **`@glm52` → glm-5.2** | same |

Suggested ledger form (so the alias — the durable fact — is what is recorded, model
derived): `by @glm52 (glm-5.2 via llmp, grok harness)`. This matches the existing
`by glm52` row already in `handoffs.md` (#450).

**Flagged, not asserted — retroactive dispatch alias is not verifiable from inside a lane:**
`handoffs.md` carries several recent rows written `by grok` (#411, #367, #402a, #441,
#447, #455, #456, #263g, #269v, #436b). The recurring note across briefs 405/426/431/437/447
— *"a lane report today was labelled `grok` when `glm52` was dispatched"* — strongly
suggests these are the same mislabel and should read `by @glm52`. **But I cannot recover
each lane's dispatch alias now** (the process env is gone), so I do not assert it. The
coordinator, who owns the dispatch, can confirm each; until then the honest row is
`by @glm52?` or, where truly unknown, **unknown**. (For #450 the ledger already correctly
says `by glm52`.)

**Stale finding to retire:** `docs/dogfood-orchestration.md` lines 40 / 82–86 ("`@glm52`
cannot reach glm-5.2 … `grok models` → only grok-4.5") are superseded by the live
`grok models` output above (ccc 0.4.2). The doc's own later lines (54–56, 46) already say
llmp became reachable / "Default model: llmp-glm-5-2"; the "BROKEN" half should be struck.

## Verification

- **Red-proof of the central claim (self-report ≠ model), non-circular, derived at runtime:**
  my own process env carries `CCC_PROVIDER=llmp`; config maps the only `runner="grok"` +
  `provider="llmp"` alias (`@glm52`) to `model="glm-5.2"`; and the live `grok models`
  catalog independently lists `llmp-glm-5-2`. Three independent sources agree on
  glm-5.2, while the harness-supplied self-report would say grok-4.5. The failure mode
  this checks — "operator records the self-report" — is the exact bug, observed twice
  before and once here.
- **No code changed**, so no test regression is possible from this increment.
  `python3 lint.py --target .` — run clean (static; binds no ports). The full
  `pytest -q` guard suite was **not** run: it binds the shared watch/hub port ranges
  (39880–39899) and eight lanes share this machine (`#428` load sensitivity); a doc-only
  change touches nothing it could regress.
- Nothing bound in 39880–39899; :35110, the heartbeat, monitors and the loop untouched;
  no `attn`; no `pkill`.

## Constraints honored

- **Investigation only — no dispatch machinery, config, or alias changed.** The config
  file is `/home/xertrov/.config/ccc/config.toml` and is the human's dispatch path; any
  change to it is his. No `Migration:`/`Feature:` trailer applies (doc-only, no install
  behaviour change). `Needs: consent` would apply *if* a config edit were proposed — none
  is; the only proposal is "record the alias, derive the model."
- Touched only `.dreamwork/docs/plans/ccc-runner-routing.md` (lane-owns). No edits to
  `tasks.md`, `questions.md`, `status.json`, `handoffs.md` — corrections reported as
  lines above.
- One free catalog query (`grok models`); **zero** paid model-identity probes. The
  brief's prohibition on probing models for identity was observed.

## Open / for the coordinator

1. Confirm the dispatch alias for each `by grok` handoffs row (I cannot — it's the
   operator's history); correct to `by @glm52` where confirmed, else **unknown**.
2. Optionally propose (for the human, not us) that `ccc` export `CCC_ALIAS`/`CCC_MODEL`
   to the child, so a dispatcher can read provenance back without parsing config. Today
   only `CCC_PROVIDER` is exported.
3. Retire the stale "BROKEN" half of `docs/dogfood-orchestration.md` per the live
   `grok models` output.
