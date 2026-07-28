# #421 research — how `i-have-adhd` instructs, and what our questions cost him

**Date:** 2026-07-28  
**Lane:** wt/421 (research only; no instruction text proposed)  
**Scope:** Half A reads the instruction files in a shallow clone of
`https://github.com/ayghri/i-have-adhd`. Half B measures
`.dreamwork/questions.md` with the production parsers in `watch.py`.  
**Not this doc:** new dreamwork question-writing instructions (coordinator),
HTML rendering of research (gap `#422`).

---

## Half A — how `i-have-adhd` actually instructs

### Clone and sources

```text
git clone --depth 1 https://github.com/ayghri/i-have-adhd /tmp/iha-421
# HEAD: c784dcb56b07c8c103323f308b25f7b055008baa
```

Instruction files read (not the README alone):

| Path in clone | Role |
|---|---|
| `skills/i-have-adhd/SKILL.md` | Canonical ruleset (142 lines). Session-persistent skill body. |
| `skills/i-have-adhd/agents/openai.yaml` | Codex/OpenAI agent metadata + default invoke prompt. |
| `skills/i-have-adhd/agents/gemini.toml` | Gemini command: compact restatement of the 10 rules + break cases. |
| `hooks/always-on.sh` + `hooks/hooks.json` | SessionStart injects the full SKILL body when `~/.claude/.i-have-adhd-always` exists. |
| `GEMINI.md` | One-line import of the skill (`@./skills/i-have-adhd/SKILL.md`). |
| `evals/rubric.md`, `evals/cases.jsonl` | What the authors score (autonomy, actionability, one clarifying question). |
| `.cursor/skills/i-have-adhd/SKILL.md` | Byte-identical to `skills/i-have-adhd/SKILL.md` (checked with `diff -q`). |

**README was not used as a source of rules** — only as install surface confirmation.

### 1. Mechanism: when / what / how much

This skill is **not a question-asking protocol for a development loop**. It is an
**output-style ruleset** for every assistant response once activated. It decides
almost nothing about *whether to open a durable human question*; it shapes *how
each reply is written*.

**When it applies (persistence):**

> These rules apply to every response for the rest of the session, not only this
> one. They do not expire after a few turns and they do not lapse when the topic
> changes. If you are unsure whether they still apply, they do.
>
> Turn them off only when the reader says "stop adhd mode" or "normal mode".
> Confirm in one line, then return to your default style.
>
> — `skills/i-have-adhd/SKILL.md` § Persistence

**When to ask the reader at all (the only ask-gating rules):**

> 3. Debug spiral. If the last three turns have been "still broken," stop
>    iterating on code. Name the assumption that might be wrong. **Ask one
>    diagnostic question.**
> 4. Real ambiguity in the request. **One short clarifying question** beats
>    guessing and rewriting.
>
> — § When to break the rules

> 4. Suppress tangents
> …
> A question that comes up mid-work is not a tangent: answer it yourself if you
> can and fold the result in. **If it still needs the reader, surface it once, at
> the end.**
>
> — § Rules · 4

The eval suite pins the same gating:

```json
{"id":"real-ambiguity","criteria":["Asks one concise blocking question rather than guessing."]}
{"id":"agent-owned-edit","criteria":["Acts on the repository instead of delegating the edit back to the user."]}
```

— `evals/cases.jsonl`

**What to put first (how much in front of the person):**

> The first line is something the reader can do. Not context. Not a plan. The action.
>
> — § Rules · 1

> Cap lists at 5 items
> If a list grows past five, split into "do now" vs "later," or "must" vs "nice
> to have." Five items ranked beats ten unranked.
>
> — § Rules · 9

> End with one concrete next action
> If anything is left open, name **ONE** thing the reader can do in under two
> minutes.
>
> — § Rules · 3

> Pre-send check
> … Then verify: if the reader reads only the first line and the last line, do
> they know (a) what to do next, and (b) what just happened?
>
> — § Pre-send check

**Options, when the task is options:**

> Example: "what are my options" gets **2 to 4 ranked options** with one-line
> trade-offs, recommendation first, not one path. The options are the answer.
>
> — § When to break the rules · 5

### 2. Prohibitions, bounds, defaults

| Bound | Quote (SKILL.md) |
|---|---|
| No preamble / closers | "Forbidden openers: \"Great question,\" \"Let me…\" … Forbidden closers: \"Let me know if you need anything else,\" …" (§ 10) |
| No tangents mid-answer | "If a second issue exists, finish the first, then offer the second as a separate question." (§ 4) |
| One next action | "name ONE thing … under two minutes" (§ 3) |
| List cap 5 | "Cap lists at 5 items" (§ 9) |
| One clarifying question | "One short clarifying question beats guessing" (break rules · 4) |
| One diagnostic question in a spiral | "Ask one diagnostic question." (break rules · 3) |
| Do not invent work for the user | Eval autonomy weight 25%; case `agent-owned-edit` refuses "push avoidable work to the user" |
| Harness wins | "Inside an agent harness, the system prompt outranks this skill" (break rules · 6) |
| Off only on explicit phrase | "stop adhd mode" / "normal mode" (§ Persistence) |

There is **no** default for "if the person does not answer a clarifying question
within N minutes, do X." Silence is outside the skill's model: it assumes a
conversational turn stream, not a durable queue that may sit for hours.

### 3. Non-response / partial response / late response

**Not specified.** Searching the instruction body for silence, partial answers,
or "came back later" yields nothing. The closest related rules are:

- Restate state every turn so the reader need not remember step N (§ 5) — this
  helps *continuity of a live thread*, not *partial completion of a multi-call
  durable ask*.
- Surface reader-needed questions once at the end (§ 4) — still assumes the next
  turn will arrive.
- Eval case `casual-message` ("Thanks, that solved it") scores: do not manufacture
  a task — but that is about *over-asking*, not about *under-closed multi-part
  asks*.

**Implication for our problem (marked as implication, not their claim):** our
failure mode — he answers Q2 of a six-call entry and leaves Q3/Q5/Q6 open, and
nothing in *our* instructions notices — is a **channel and state machine**
problem. `i-have-adhd` has no analog of `questions.md`, no partial-answer status,
and no re-prompt rule for unfinished multi-call bundles.

### 4. Stated theory

Yes, and it is explicit. Five facts drive the rules:

> 1. Working memory is small. Anything not on screen is forgotten. Do not ask the
>    reader to "keep in mind X."
> 2. Knowing the answer is not doing the answer. The friction between "got it" and
>    "done it" is where work dies.
> 3. Starting is the hardest step. The first action must be obvious, small, and
>    doable now.
> 4. Time estimates feel uniform. "A bit of work" and "a few hours" register the
>    same. Vague estimates fail.
> 5. Dopamine is scarce. Visible progress matters. Buried wins do not register.
>
> — § What ADHD changes about reading

That is a theory of **reading and acting on assistant output**, not a theory of
**async expert decisions about a codebase**.

### What does NOT transfer

Named boundaries (not soft caveats):

1. **Audience and channel.** `i-have-adhd` shapes replies *to* a reader who is
   also the person doing the next coding action. Dreamwork questions are durable
   *asks of an expert about his own project*, often while he is not mid-session.
   "Lead with the next action" maps cleanly to *one-word consent* asks
   (`apply` / `yes`) and poorly to *multi-axis design ratification* that needs
   evidence, not a shell command.

2. **One clarifying question ≠ one open entry.** Their unit is a *chat turn*.
   Ours is a *ledger entry* that can legally carry seven numbered calls. Cap-5
   and "one question" are about **presentation density in a reply**, not about
   whether a plan may need several human decisions. Porting "one question only"
   without a place for the other decisions invents a second failure mode
   (undeclared assumptions).

3. **No durable partial state.** Their rules never say what to do when the
   reader answers part of a multi-part prompt later. We have that exact case
   (`#275`). A straight port of style rules will not create the missing
   partial-answer machine.

4. **Autonomy bias is opposite to our ask channel.** Their evals punish pushing
   agent-owned work to the user. Our `questions.md` exists *because* some work
   is deliberately his (authority, deployment, taste). Suppressing asks is
   already our direction (`DREAMWORK.md` 05:35: ask less); their autonomy rule
   does not tell us *how to format the remaining asks*.

5. **Working-memory facts still apply to the card.** Speculation marked:
   principles 1, 3, and 9 (small working memory; first action obvious; list cap)
   are the parts most likely to improve our *card body*, independent of ADHD
   branding — but only as density and ordering constraints, not as a substitute
   for measuring whether multi-sub entries actually cost him.

---

## Half B — what our questions currently cost him

### Method and parser cross-check

Corpus: `.dreamwork/questions.md` at worktree HEAD when measured.

```bash
python3 -c "
import watch, re
from pathlib import Path
text = Path('.dreamwork/questions.md').read_text()
open_q = watch.parse_open_questions(text)
answered = watch.parse_answered(text)
print(len(open_q), len(answered))
assert len(list(re.finditer(r'^## Open[ \t]*$', text, re.M))) == 1
assert len(list(re.finditer(r'^## Answered[ \t]*$', text, re.M))) == 1
open_sec = text[re.search(r'^## Open[ \t]*$', text, re.M).end():
                re.search(r'^## Answered[ \t]*$', text, re.M).start()]
ans_sec = text[re.search(r'^## Answered[ \t]*$', text, re.M).end():]
assert len(re.findall(r'(?m)^- \*\*', open_sec)) == len(open_q)
assert len(re.findall(r'(?m)^- \*\*', ans_sec)) == len(answered)
"
# → open=4 answered=52; hand bullet counts match; headings unique.
```

**Parser cross-check: no disagreement.** Production `parse_open_questions` /
`parse_answered` count matches a heading-anchored top-level `- **` bullet count
(4 / 52). Sub-bullets (`Note` / `Answer` / `Follow-up`) are parsed into
`follows` (and Open `answer` when lifted), not as separate entries.

**Size of an entry** = `title + body` as returned by the parser (follows
excluded from body size; follows called out separately where relevant).

### 1. Size distribution

| Population | n | words min / med / mean / max | lines min / med / mean / max |
|---|---:|---|---|
| Open | 4 | 208 / **480** / 428 / 545 | 23 / 39.5 / 37.5 / 48 |
| Answered | 52 | 29 / **300.5** / 333 / 1121 | 5 / 28.5 / 34 / 102 |
| All | 56 | 29 / **301.5** / 340 / 1121 | 5 / 30.5 / 34 / 102 |

Largest by words (title+body):

1. **1121w / 102L** — `#346` task-store schema (S1–S4)  
2. **1009w / 94L** — `#264` task-transition boundary (T1–T4)  
3. **897w / 83L** — `#281` `/tasks` seven taste calls  
4. **738w / 70L** — implementation authority (G1 + Q2–Q4)  
5. **709w / 56L** — `ccc @grok` 401 / three options  

Open entries are **heavier than the answered median** (med 480 vs 301 words):
today's open set is almost all multi-call design gates.

With `follows` text included (actual card reading cost), open median rises to
**540** words and max to **903** (`#275` with two human notes + two loop
follow-ups); answered max becomes **2287** (`#346`'s long note thread).

Command used for sizes: `watch.parse_*` then
`len((title+"\n"+body).split())` / `splitlines()` over each item.

### 2. Sub-questions per entry

**Pattern derived from the corpus** (not assumed a priori):

1. **Letter+number decision markers** in the body:
   `\*\*([A-Z])\s*(\d+)\s*(?:—|–|:|\s|\*\*)` with labels observed as decision
   bundles: `Q R S G N T M D H P B V A E L` (examples: `**Q1 —`, `**S1:`,
   `**R1 —`, `**G1`, `**T1 ·`, `**M1`, `**N1`, `**D1`, `**H1`, `**B1`, `**V1`,
   `**P1`, `**E1`, `**A1`).
2. Else **numbered decision lists**: `(?m)^\s{0,4}(\d+)\.\s+\*\*` (e.g. `#275`
   and `#281`).
3. Else **implicit single** if the body contains `?`.
4. Else **none**.

**Distribution (n=56):**

| n_sub | count |
|---:|---:|
| 0 | 29 |
| 1 | 8 |
| 2 | 1 |
| 3 | 11 |
| 4 | 5 |
| 6 | 1 |
| 7 | 1 |

- **median n_sub = 1** if counting only labeled multi-call markers plus
  implicit singles on the multi side of the table; treating the 29 "none" as
  non-asks-or-folded-early gives a corpus where **19 / 56 (34%) carry ≥2
  sub-decisions**.
- **max = 7** (`#281`).
- Multi-sub open right now: `#263` (Q1–Q3), `#264` (Q1–Q2), `#275` (1–6).

### 3. Partial answers — highest-value measurement

Definition used (strict, evidence-based):

- **Durable partial:** human engaged some labeled subs of a multi-sub entry,
  and either (a) the entry is still open with named remaining subs, or (b) the
  fold summary explicitly records an unanswered sub that was split off.

**Found:**

| Entry | Subs | What he did | What remained | Evidence |
|---|---|---|---|---|
| **`#275` (open)** | 6 numbered | Note 01:39 splits SaaS vs self-hosted (dissolves Q1 dichotomy; Q4 → `#359`). Note 14:53: **"Q2: yes a reverse proxy component is acceptable"**. | Loop follow-ups (01:44, 14:57) still name **Q3, Q5, Q6 open**. Entry remains in `## Open`. | `parse_open_questions` → `follows` on that title; body still lists 1–6. |
| **`#281` (answered)** | 7 numbered | One answer at 21:47 covering most. Fold head: **"ruled — six of seven … (6) not answered"** — *"you'll need to explain what this means sorry"*. | Q6 re-filed as its own open-then-answered entry (`#281 Q6, asked again in plain terms`, answered 23:39). | `parse_answered` body `→ answered (2026-07-27 21:55)` text. |

**Not counted as durable partials (false friends):**

- **`#346`:** mid-thread loop line *"Still open for you: S1–S4"* sat *before*
  the 01:23 answer that resolved them. Final state is fully folded. Multi-round
  engagement ≠ incomplete close.
- **`#254` R1/R2/R3:** human `rec` = complete choice of one option. Prose
  containing "have not answered" is about the *design scenario*, not a missing
  sub-answer.
- **`#263` implementation authority (05:43):** brief's "answered across four
  calls at once" is **complete** — fold head `rec — all four` with G1/Q2/Q3/Q4
  all ruled. That is the *success* shape of multi-sub, opposite of `#275`.

**Count to take to the coordinator:**

- **Durable partial multi-sub entries in the live corpus: 2** (`#275`, and
  `#281` at fold time with a sibling re-ask).
- **Multi-sub entries total: 19.** So partials are **2 / 19 ≈ 11%** of
  multi-sub, not the common path.
- **But `#275` is still open ~19+ hours after first engagement** (see times
  below), and **nothing in our instruction surface auto-notices** remaining
  Q3/Q5/Q6 — that matches the brief's problem statement even though the
  *rate* is low.

### 4. Time from filing to answer

**Title dates are date-only** (no time) — that is `#392`. Calendar-day delta is
reported only as a coarse signal; **it is not an age**.

```text
# answered entries with both title date and when (parser):
# n=38 with both; calendar-day (answer_date − title_date):
#   min=0 med=0 mean=0.39 max=3
#   same day: 28; next day+: 10; negative: 0
```

Sub-day precision via
`git log --format=%cI -1 -S'<headline substring>' -- .dreamwork/questions.md`
(filing commit) vs parser `when` / first human `follows[].when`:

| Entry | Filing (`git log -S`, +10) | First human engagement | Fold / last answer | Rough span |
|---|---|---|---|---|
| `#275` six calls | 2026-07-27T19:44 | 2026-07-28 01:39 note | still open (Q3/Q5/Q6) | ~6h to first note; **still partial ~19h later** (14:53 Q2) |
| `#281` seven calls | 2026-07-27T16:19 | 2026-07-27 21:47 answer | 21:55 fold (Q6 incomplete) | ~5.5h; Q6 re-ask closed 23:39 |
| impl authority (G1+Q2–4) | 2026-07-28T03:04 | 05:43 answer | complete same window | ~2.5h |
| `#346` S1–S4 | 2026-07-28T00:45 | notes from 01:05; answer 01:23 | complete | ~0.5–0.75h multi-turn |
| one-word `install.py --apply` | 2026-07-28T03:16 | 05:38 | complete | ~2.5h |
| one-word `GIT_OPTIONAL_LOCKS` | 2026-07-28T10:11 | 14:48 | complete | ~4.5h |

**No midnight-derived ages reported.** Filing times are commit committer dates;
answer times are the stamps the loop wrote into the ledger.

### 5. Do more sub-questions take longer or finish less completely?

Population: **n=56 total**, **n=19 multi-sub**, **n=16 multi-sub answered**,
**n=2 durable partials**.

| n_sub | count | med words (title+body) | durable partials |
|---:|---:|---:|---:|
| 0 | 29 | 127 | 0 |
| 1 | 8 | 406 | 0 |
| 2 | 1 | 545 | 0 |
| 3 | 11 | 413 | 0 durable (see false friends) |
| 4 | 5 | 738 | 0 durable |
| 6 | 1 | 425 | **1** (`#275`) |
| 7 | 1 | 897 | **1** (`#281` at fold) |

**Size tracks n_sub** in the obvious way (4-sub med ~738w, 7-sub 897w). That is
composition cost, not proof of human cost.

**Latency vs n_sub:** calendar-day lag medians are **0** at every n_sub bucket
with data; multi-sub answers are often *same-day*. **No signal that higher
n_sub delays the calendar day of answer** at this corpus size.

**Completeness:** of 16 multi-sub answered entries, **15 closed as a complete
ruling** (usually `rec` / pick one of N / "all four"). **One** (`#281`) required
a split re-ask. **One open multi-sub** (`#275`) is the standing partial.

**Honest verdict: "No clean trend at n=19 multi-sub / n=2 partials."** The
corpus **does** show that multi-sub format *can* leave remainder work
(`#275`, `#281` Q6), and that he often **answers multi-sub successfully in one
go** (`#263` 05:43, `#264` T1–T4, `#367` M1–M4). Format cost is **real but not
dominant**; vocabulary cost (`#281` Q6: "explain what this means sorry") and
**whether remaining subs are tracked** are separately load-bearing.

**Contradicts a strong "multi-sub always costs him" premise:** most multi-sub
entries close complete, often same day, often with a one-word `rec`. What the
numbers support is narrower: **(a)** multi-sub entries are the long ones; **(b)**
partial completion is rare but sticky when it happens; **(c)** nothing
instructional notices (b).

### Existing human preferences already in `DREAMWORK.md` (context only)

Not measurements, but already decided by him and relevant when the coordinator
writes options:

- Ask less; one clearly superior answer is not an ask (05:35 / `#367`).
- Ask in plain terms — jargon cost hours (`#281` Q6) (21:47).
- A blocker that is his must always have a question he can answer (`#419`, 15:19).
- When a number decides, measure before asking (`#367` previews).

These already encode part of what Half A would suggest; the gap is **format +
partial-state**, not "never ask multi-part."

---

## What the material does and does not support

| Claim | Supported? |
|---|---|
| `i-have-adhd` has transferable *density* rules (one next action, cap lists, no preamble) | **Yes**, from quoted SKILL.md |
| `i-have-adhd` tells us when a dreamwork agent should open a ledger question | **No** — out of scope of that skill |
| `i-have-adhd` handles partial multi-call answers | **No** — silent |
| Our multi-sub entries are usually unfinished | **No** — 15/16 answered multi-sub closed complete |
| Partial multi-sub is a real failure mode we have | **Yes** — `#275` live; `#281` Q6 historical |
| Higher n_sub → slower answer (days) | **No signal at this n** |
| Higher n_sub → longer cards | **Yes** (composition) |
| Jargon / non-plain wording costs completion | **Yes** — `#281` Q6, already in DREAMWORK.md |
| We should rewrite instructions as a straight port of i-have-adhd | **Not supported** — § What does NOT transfer |

---

## For the coordinator (findings only — not options)

Ranked; each traces to a quote or number above.

1. **`i-have-adhd`'s load-bearing move is density and one-thing-at-a-time
   presentation (lead with action, cap lists at 5, one clarifying question, one
   end action), driven by an explicit working-memory theory — not a durable
   multi-call ask protocol** (SKILL.md §§ 1–5, 9, Persistence, "What ADHD
   changes").

2. **That skill has no rule for silence, partial answers, or late replies; our
   highest-cost live case (`#275`: Q2 answered, Q3/Q5/Q6 still open after two
   human notes) is exactly the gap** (Half A §3; Half B §3; `follows` on `#275`).

3. **Multi-sub format is common (19/56) and usually succeeds (15/16 answered
   multi-sub closed complete, often with bare `rec`); partials are rare (~2)
   but sticky — so "ban multi-sub" is not forced by the corpus, while "track
   remainder subs" is** (Half B §§2–3, 5).

4. **Card length is the measurable tax of multi-sub: med words jump from ~127
   (n_sub=0) to ~738 (n_sub=4) to 897 (n_sub=7); open cards today med 480 words**
   (Half B §1–2) — density rules from Half A address this even if multi-sub
   remains legal.

5. **A finding against changing everything: same-day multi-sub completion is
   normal (e.g. G1+Q2–Q4 in ~2.5h; T1–T4 in one answer; `#367` four decisions
   with two overrides), so the coordinator should not treat "he cannot handle
   multi-call" as established — the supported problems are remainder-tracking,
   plain language, and not asking non-questions** (Half B §§3–5; DREAMWORK.md
   05:35 / 21:47).

---

## Trust ranking of this doc's halves

- **Half A is higher trust:** single shallow clone, quoted instruction files,
  commit `c784dcb`, no reconstruction from web search.
- **Half B is slightly lower trust on three edges:** (1) sub-question regex is
  corpus-derived and will miss unmarked multi-asks; (2) durable-partial
  classification is hand-judged on top of parser fields; (3) latency sample is
  a handful of `git log -S` lookups, not a full 56-entry filing-time table.
  Headline counts (4 open / 52 answered / size medians) are high trust.

---

## Verification

- `python3 lint.py` — run after write; must be clean for this path class.
- `just test` — **skipped**: binds guard ports 39890–39899; another lane holds
  them per brief. No ports in 39880–39899 bound by this work.
- Deliverable: this file only under `.dreamwork/docs/research/`.
