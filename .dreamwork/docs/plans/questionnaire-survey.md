# Questionnaire survey — what pag-server's question form does, and what dreamwork should keep

**Task:** #448 (survey half) · **Status:** survey only — no build, no SQLite, no prototype
**Date:** 2026-07-29 · **Source tree:** `~/src/pag-server/` (read-only)
**Sequencing:** feature blocked on `#294`; this document is the unblocked half.

Context used for relevance: `#445` (four question/attention levels), `#421` (how we ask),
`#254` (note/reply threading design), `#294` / `.dreamwork/docs/plans/task-store-schema.md`
(planned store), and `file-formats.md` on `questions.md`.

---

## 1. What `~/src/pag-server/` actually does

There are **three related surfaces**, not one. The human's "question form" is the
workspace-chat `ask_user` form. The mail plugin has a second questionnaire product
with a different type set and response lifecycle, and workspace templates carry a
third, birth-time questionnaire (§1.3). All are cited so a later design
does not mix their contracts.

### 1.1 Workspace chat form (`ask_user`) — the feature-rich reference

| Layer | Path | Symbol |
|---|---|---|
| LiveView form component | `lib/pag_server_web/live/workspace_chat/question_form.ex` | `PagServerWeb.Live.WorkspaceChat.QuestionForm.question_form/1` |
| Builtin tool | `lib/pag_server/tools/builtin/ask_user.ex` | `PagServer.Tools.Builtin.AskUser` (`name/0` → `"ask_user"`) |
| Pending-state GenServer | `lib/pag_server/tools/question_manager.ex` | `PagServer.Tools.QuestionManager` |
| Shared validation | `lib/pag_server/questionnaire/validator.ex` | `PagServer.Questionnaire.Validator` |
| Payload normalize (inject Other, modes) | `lib/pag_server/questionnaire/payload_normalizer.ex` | `PagServer.Questionnaire.PayloadNormalizer` |
| Answer + notes normalize | `lib/pag_server/questionnaire/answer_normalizer.ex` | `PagServer.Questionnaire.AnswerNormalizer` |
| Adapter seam + lifecycle map | `lib/pag_server/questionnaire/adapter_contract.ex` | `PagServer.Questionnaire.AdapterContract` |
| Audit Ecto schema | `lib/pag_server/schema/question_record.ex` | `PagServer.Schema.QuestionRecord` |
| Unanswered-question notifier | `lib/pag_server/tools/question_notifier.ex` | `PagServer.Tools.QuestionNotifier` (+ `LoggerBackend`, `EmailBackend`) |
| Migration | `priv/repo/migrations/20260227130000_create_question_records.exs` | `CreateQuestionRecords` |
| UX guide (behaviour, not code) | `docs/guides/questionnaire-ux-v2.md` | — |
| Adapter contract doc | `docs/architecture/questionnaire-adapter-contract.md` | — |

**Question types / `input_mode`** (`Validator.resolve_input_mode/2`, `AskUser` schema):

- `single_select` (default when options present)
- `multi_select` (also via legacy `multi_select: true`)
- `text` (free text; no first-class list type — list-like content is plain text)

Per select question: options require `label` + `description`; count bounds are
`length(options) >= 2` and `length(options) <= 8` for select modes. Header max
length is `Validator.max_header_length()` (20).

**Other / free text:** `PayloadNormalizer.ensure_other_option/1` **appends** an
`{"label" => "Other", "description" => "Provide a custom answer"}` option to every
non-empty select question that does not already have one. The form shows a free-text
"Other answer" field only when Other is selected (`show_other_input?/3`). Secrets use
`is_secret` → password input for Other (`question_secret?/1`).

**Per-question notes:** optional textarea `answers[i][notes]`; normalized separately
from answers via `AnswerNormalizer.normalize_notes/1` → response shape
`{"answers" => …, "notes" => …}`.

**Required vs optional:** `AnswerNormalizer.question_required?/1` — a question is
required unless `required == false`. Submit is gated by
`required_questions_answered?/2`. Defaults: not found as rich default values on
options; default is mode/`multi_select`/`is_secret`/`async`/`timeout` defaults on the
tool schema only.

**Validation UX** (`docs/guides/questionnaire-ux-v2.md` + form): progressive — quiet
while editing; inline + summary errors after invalid submit; summary is `role="alert"`
and focused; live region for status; `aria-label` / `aria-describedby` / keyboard-help
details; focus restored to composer when the form unmounts (guide).

**Conditional / branching logic:** **not found** in `Validator`, `QuestionManager`, or
`QuestionForm`. Multi-question is a tabbed wizard (Q1…Qn + Review), not skip-logic.

**RHS previews:** option `preview: {type, content}` with types `markdown | mermaid |
svg | code`; legacy `option.markdown` still accepted. Safe fallbacks for bad SVG /
unsupported types. No arbitrary HTML (`questionnaire-ux-v2.md`).

**Multi-question UI:** tab rail, Prev/Next, final Review panel with per-question Edit,
Submit only when `can_submit`. Single-question: Submit + Dismiss.

**Keyboard** (`keyboard_help/1`, guide): A–H option hotkeys, arrows, N/P and Tab
between questions when multi, Enter / Ctrl-Enter submit rules, IME composition
respected; hotkeys off inside text fields. Hook name on the form: `QuestionFormKeys`.

**Timeout / dismiss / extend:** `QuestionManager.request_input/3` with `timeout_ms`;
tool docs say prefer `timeout_s: 0` (persist until answered). UI shows remaining ms and
`extend_question_timeout` (+10 minutes button). Outcomes on the audit record:
`:answered | :dismissed | :timed_out`.

**Sync / async / scale:** tool supports `async: true` (pending batch id); sync blocks
the agent call. Large batches chunked (`ask_user_question_chunk_size` default 25,
`ask_user_max_questions_total` default 250). Cap on concurrent pending per agent:
`@default_max_pending_per_agent` (8) in `QuestionManager`.

**Fork clone:** `QuestionManager.clone_for_fork/3` — clones pending questions into a
forked thread with new ids; answering one does not answer the other.

**Partial save:** **not found** as a durable draft of incomplete answers. LiveView
holds `selected_options` / `other_values` / `notes_values` in assigns while the
question is pending; resolution writes the audit record. No mid-edit server-side draft
table was found.

**Edit after submit (chat path):** **not found** as revise-on-answered. Once
`submit_response` resolves, the question is in `resolved_ids`. Re-ask is a new
request.

**Persistence:** in-memory pending in `QuestionManager`; on resolution,
`QuestionAuditLog` / `question_records` (see §2). Events via `EventPersistence` /
PubSub topic prefix `"workspace_questions:"`.

**Unanswered nudge:** `QuestionNotifier` subscribes to each watched workspace's
question topic and schedules a notification after a configurable delay
(`@default_notify_after_ms` 30_000); resolution before the delay cancels the
timer. Backend is pluggable via a `Backend` behaviour — `LoggerBackend` logs,
`EmailBackend` sends mail. The transferable shape is *delay-then-nudge, cancel
on resolution*, independent of the email transport.

### 1.2 Mail questionnaire (second product)

| Layer | Path | Symbol |
|---|---|---|
| Schema + lifecycle | `plugins/mail/lib/questionnaire.ex` | `PagServer.Plugins.Mail.Questionnaire` |
| Card UI | `lib/pag_server_web/live/mail_live/questionnaire_card.ex` | mail LiveView card |
| Templates | `plugins/mail/lib/questionnaire/templates.ex` | templates module |
| Message type | `plugins/mail/lib/schema/workspace_message.ex` | `message_type` includes `:questionnaire` |

**Types** (`@valid_question_types`): `text`, `choice`, `number`, `boolean`, `scale`
— a longer set than `ask_user`'s three modes. Schema lives in
`metadata.questionnaire` on a mail message; responses in `metadata.responses`.

**Revise after submit:** yes — `transition_response/5` with `:submit | :revise`.
Revise supersedes the prior active response (`state: "superseded"`) and appends a
`revised` entry with `previous_response_id` and incrementing `revision`. Duplicate
same-answer transitions map to lifecycle `:duplicate` via `AdapterContract`.

**Planner use:** `plugins/backlog/lib/planner_questionnaire.ex` builds progressive
Q&A over mail for plan generation — product-specific orchestration, not the chat form.

### 1.3 Setup-wizard template questionnaire (third surface — not the model)

Distinct from both chat `ask_user` and mail: workspace **templates** may declare
`questionnaire_sections` (`lib/pag_server/templates/workspace_template.ex`,
`@question_types ~w(free_text single_select multi_select yes_no scale)`), edited
via `PagServerWeb.Live.WorkspaceTemplateEditor.QuestionnaireEditor`
(section/question CRUD, reordering, per-question `variable` binding) and run by
the setup wizard (`lib/pag_server_web/live/setup_wizard.ex`) at workspace
creation; answers substitute into file templates and prompts through each
question's bound variable, and `metadata.no_questionnaire` skips the step
(auto-set when no sections exist — `lib/pag_server_web/live/workspace_template_editor_live.ex`).
It is a **birth-time variable collector for an agent-template product**, not a
model for asking him things mid-loop, so it is recorded here for completeness
and excluded from the mapping except as a cut (§3).

### 1.4 Looked for and not found

| Capability | Result |
|---|---|
| Conditional show/skip branching between questions | not found |
| Durable partial-save / draft answers before submit (chat) | not found |
| Re-edit after chat `ask_user` resolution | not found (mail has revise) |
| First-class list input mode | explicitly deferred (`questionnaire-ux-v2.md`) |
| Authorship of the *question* as human vs agent (dreamwork sense) | not found — only `agent_instance_id` on the request |
| Link from a question batch to a review-artifact / `#ask` document | not found (pag has no dreamwork review surface) |
| Threaded follow-ups under an answered question | not found as a first-class model; chat is request/resolve |

---

## 2. The data model, as it really is

### 2.1 Chat path — `question_records`

From `CreateQuestionRecords` / `QuestionRecord`:

```text
question_records
  id                 binary_id PK
  workspace_id       binary_id FK workspaces NOT NULL
  thread_id          binary_id FK threads NULL
  agent_instance_id  string NULL
  question_spec      map/jsonb NOT NULL   -- full submitted questions payload
  answer             map/jsonb NULL       -- answers (+ notes when present)
  outcome            string enum answered|dismissed|timed_out
  requested_at       utc_datetime_usec NOT NULL
  resolved_at        utc_datetime_usec NOT NULL
  inserted_at / updated_at
indexes: workspace_id, thread_id, agent_instance_id, requested_at, outcome
```

Pending questions are **not** rows here; they live in `QuestionManager` state until
resolved. The table is an **audit / compliance** record of finished interactions,
with the full question blob and answer blob rather than a normalized option table.

Canonical answer map after `AdapterContract.normalize_answers/1`:

```json
{ "0": "Staging", "1": ["A", "B"], "2": "free text" }
```

Optional notes: parallel map of string index → note string.

### 2.2 Mail path — embedded in message metadata

```text
workspace_messages.message_type = "questionnaire"
metadata.questionnaire = {
  title, description?,
  questions: [ { id, text, type, required?, options? | scale_min/max? } ]
}
metadata.responses = [
  {
    response_id, respondent_id, respondent_name, submitted_at,
    answers: { "<qid>": <value> },
    state: submitted|revised|superseded,
    revision, previous_response_id?, superseded_by?, superseded_at?
  }
]
```

No separate SQL tables for questionnaire definition or answers beyond the message
row's JSON metadata (as of the modules read).

### 2.3 Can `#294`'s planned schema carry this?

**No — not as planned today.** `.dreamwork/docs/plans/task-store-schema.md` (the
entity half split as `#346` from `#294`) defines:

- `entry` / `task` / `related` / `depends` (and earlier `dependency`)
- `review_decision(artifact PK, question_id INTEGER NOT NULL, decision, decided_at)`

That is the **task ledger** plus a review-decision link that *names* a
`question_id`. It does **not** define a `question` / `questionnaire` /
`answer` / `contribution` table, and it does not store option sets, answer
payloads, notes, or thread bullets.

What `#294` already does that a questionnaire can *hook*:

- `review_decision.question_id` assumes questions have stable integer ids — same
  direction dreamwork's `questions.md` titles already use for task cross-refs.
- Review artifacts stay files; the store only records decision + owning question.

What it must **add** (or a later store plan must add) before a structured
questionnaire can replace markdown parse:

| Need | Why |
|---|---|
| `question` entity (id, state open/answered, title, body, priority, opened_at, …) | today `questions.md` is the durable ask channel |
| authorship on every contribution (human \| loop + channel + ts) | load-bearing in `file-formats.md`; silent if wrong (`NOTE_TAGS` / `ANSWER_TAGS`) |
| answer / note / follow-up contributions with closed tag vocabulary | `#254` threading; `#446` multi-answer retention |
| optional structured fields: options[], input_mode, selected, other_text, notes, validation rules | only if the questionnaire UI is first-class; free-text-only can stay in body |
| link `review_decision` ↔ question already planned — keep it | `#289` integrity: one artifact, one owning question |

Until those exist, a questionnaire built only on markdown `questions.md` is exactly
what `#448` says is the wrong early build. The survey still informs the **shape**
those tables should eventually hold.

---

## 3. Keep / cut / open

Reasons are in **dreamwork's** terms. "It was there in pag" is never a keep.

| Capability (pag) | Verdict | One-line reason (dreamwork) |
|---|---|---|
| `single_select` options with label + short description | **keep** | Structured choice is what level-1 `#445` asks him to make; description reduces ambiguity without a second question |
| Auto `Other` + free-text refinement of a choice | **keep** | His answers often need a label *and* a caveat; `#445` also wants free-text beside numeric-ish fields |
| Optional per-question notes | **keep** | Separate "answer" vs "context" matches how `Answer` vs `Note` already work; cheap insurance against underspecified picks |
| Progressive validation (quiet until submit; summary + inline) | **keep** | Dashboard already fights silent parse failures; noisy mid-type errors cost attention he is rationing |
| Required vs optional per question | **keep** | Some asks are hard gates (P1); some are advisory — the format must say which |
| Persist until answered (timeout default 0) | **keep** | Matches `questions.md` open until fold; wall-clock pressure is the wrong default for async loop work |
| Multi-answer retention / amend semantics | **open → lean keep** | Pag chat is one-shot; dreamwork already retains every `Answer` (`#446`) and needs explicit reopen/amend — design, don't copy pag's one-shot |
| Mail-style revise with revision chain | **open** | Useful model for *structured* re-answer; may map to append-only contributions rather than supersede-in-place |
| Multi-question tab wizard + Review panel | **cut** | Dreamwork batches are small and sit next to a review artifact; a second wizard UI is another surface to maintain |
| A–H hotkeys / QuestionFormKeys / N-P tab nav | **cut** | Nice on a full agent chat; the dashboard composer and card already own keyboard attention |
| RHS mermaid / svg / code previews | **cut** | Comparison material belongs in the **review artifact** (already rich); duplicating typed preview renderers is superfluous |
| Legacy `option.markdown` + dual preview paths | **cut** | Compatibility layer for pag's old callers; we have no such callers |
| `is_secret` password masking | **cut** | Dreamwork does not ask for secrets in the dashboard channel |
| `number` / `boolean` / `scale` mail types | **cut** | Form-builder surface area; `#445`'s numeric-ish rule is validation on free text (`>=1`, warn on 0, hard-invalid below 0), not a type zoo |
| Mail questionnaire product + `message_type` transport | **cut** | Different product (cross-workspace mail); dreamwork's channel is the dashboard + `questions.md` |
| Setup-wizard `questionnaire_sections` with variable binding into file templates/prompts | **cut** | Birth-time variable collector for pag's workspace-template product; dreamwork has no agent-template wizard and its ask surface is mid-loop, not creation-time |
| Planner progressive mail Q&A orchestration | **cut** | Backlog planner workflow; not the human↔loop ask surface |
| GenServer-blocked sync `ask_user` | **cut** | Loop must keep working while he is unanswered (`#445` level-4 cooperation); blocking is anti-pattern here |
| Async pending with agent-batch chunking to hundreds | **cut** | Wrong scale; one open question set is enough |
| Timeout countdown + extend-by-10-minutes UI | **cut** | Open questions already age on the card; a second clock competes with title age (`#392b`) |
| Delayed notifier while a question stays unanswered (30 s default, pluggable backend, cancel-on-resolve) | **open → lean keep** | `#445` fixes *what happens if he never replies* per level; delay-then-nudge is a candidate mechanism for that — the transport (email) is not the point |
| Dismiss without answer as first-class outcome | **open** | Sometimes he should decline; today that is a Note or silence — needs a deliberate tag, not a quiet dismiss |
| `clone_for_fork` independent pending clones | **cut** | Thread-fork product of multi-agent workspaces; no analogue in single-dashboard dreamwork |
| Audit blob `question_spec` + `answer` jsonb only | **open** | Fine as an event snapshot; insufficient alone as the *live* store for open questions |
| Authorship (human vs loop) on each turn | **dreamwork-only keep** | Pag lacks it; `file-formats.md` makes wrong tags delete contributions in silence |
| Threaded Note / Follow-up under one question (`#254`) | **dreamwork-only keep** | Pag has no equivalent model; approved design already exists |
| Questionnaire ↔ review artifact `#ask` | **dreamwork-only keep** | Level-1 `#445` produces a review doc he chooses through; the form is the decision rail, not a substitute for the artifact |
| Subagent target count + free-text policy validation (`#445`) | **dreamwork-only keep** | Pag has no equivalent; rules are `>=1` valid, warn on 0, hard-invalid below 0 |

### IGC — how rich should the first structured form be?

**Context:** dreamwork already has a working markdown ask channel (`questions.md`)
and review artifacts; SQLite (`#294`) is not landed; the human pre-constrained
the design with *"cut back on any superfluous elements."*

**Goals (binary):**

- **G1** He can answer a material multi-option design ask without a follow-up for
  "which option?" when the options were already in the review doc.
- **G2** Authorship, thread order, and multi-answer retention cannot go silent
  (no path that drops a contribution the way a wrong tag does today).
- **G3** Surface area is small enough to ship after `#294` without a second product
  (breakpoint: one card in the dashboard, not a wizard + mail + preview stack).
- **G4** Works with async loop behaviour — never blocks the agent on his reply.

| Idea | All | G1 | G2 | G3 | G4 |
|---|:---:|:---:|:---:|:---:|:---:|
| A. Faithful port of pag chat form (+ previews, wizard, timeouts) | ✘ | ✔ | ✘ | ✘ | ✘ |
| B. Cut-down: single/multi select + Other + notes on a dashboard card, linked to review artifact; contributions stay append-only with closed tags | ✔ | ✔ | ✔ | ✔ | ✔ |
| C. Stay markdown-only forever (no structured options) | ✘ | ✘ | ✔ | ✔ | ✔ |
| D. Full mail-style type set (number/boolean/scale) + revise chain UI | ✘ | ✔ | ? | ✘ | ✔ |

**Decisive errors:**

- **A ✘ G2:** porting without re-implementing author tags and thread grammar reintroduces silent drops; pag's model has no author vocabulary.
- **A ✘ G3:** wizard + typed previews + timeout chrome is the "superfluous" set he already named.
- **A ✘ G4:** sync GenServer wait is the wrong control flow for dreamwork.
- **C ✘ G1:** free prose answers to multi-option reviews are exactly the cost `#421`/`#445` are trying to reduce; structure is the point of waiting on SQLite.
- **D ✘ G3:** type zoo exceeds the breakpoint; **?** on G2 until revise maps cleanly onto append-only contributions.

**Survivor:** **B**. Hold tentatively — reopen if a later `#445` level needs richer
previews *inside* the form (then prefer linking harder to the artifact, not
rebuilding mermaid in the card).

---

## 4. What dreamwork needs that pag has no equivalent for

1. **Who authored the question and each contribution.**  
   `questions.md` deliberately tags human vs loop (`Note (human, …)`,
   `Follow-up (loop, …)`, `Answer (via watch, …)`). Wrong spellings fall into
   body prose and vanish from the thread UI. Any questionnaire must make the
   closed tag set (or its store equivalent) impossible to mis-type, not optional.

2. **Threaded follow-ups on an already-answered question.**  
   `#254` design (`.dreamwork/docs/plans/note-reply-threading-254.md`): loop Answer
   is the root response; later human Notes + loop Follow-ups are one discussion
   branch at a single inset depth. Pag's form is request→resolve, not a thread.

3. **Reopen / amend / second answer.**  
   `#446` keeps every `Answer` bullet; fold reconciles semantics. Pag chat is
   one-shot; mail revise supersedes. Dreamwork wants **history-preserving** amend,
   not silent overwrite.

4. **Free-text alongside choices, with field-level validity rules.**  
   `#445` subagent policy: free text for type/rules; count validation `>= 1` valid,
   **warn on 0**, **hard-invalid below 0**. Pag has Other + notes, but not this
   validation policy language.

5. **Questionnaire ↔ review artifact.**  
   Level-1 `#445`: material choices produce a review document; he chooses among
   options. Today that link is the `#ask` block and a `questions.md` entry. The
   form should be the **decision instrument for an existing artifact**, not a
   second place to dump the full IGC table. `#294`'s `review_decision` already
   points that way (artifact PK → owning `question_id`).

6. **Attention mode (#445) as policy over the same surface.**  
   Levels 1–4 change *whether and how* something is asked, not the existence of a
   second form product. Pag has no "keep me informed vs ask everything" axis.

---

## Summary for the implementer (after `#294`)

Ship **B**: a small structured card — select modes, Other, notes, progressive
validation — over a store that already understands **questions + authored
contributions + review_decision**. Cut previews, wizard chrome, timeouts, mail
types, and blocking waits. Do not treat pag's audit blob as the live schema;
design question/contribution tables (or their equivalent) as explicit `#294`
follow-on scope.
