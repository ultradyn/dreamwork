# Questions-to-Dreamer Answers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a simple `/answers` page where the human can durably ask the dreamer questions and read the loop's answers.

**Architecture:** Introduce `.dreamwork/answers.md` as a distinct two-section ledger (`## Open`, `## Answered`) using the existing entry grammar but new author semantics: open entries are human-authored questions; answered entries begin with a loop-authored resolution. `watch.py` collects and renders the channel, accepts new questions through `/ask` (already witnessed by the one `do_POST` submissions-log seam), and emits a wake event so the coordinator answers and folds entries. The MVP deliberately does not create agent sessions or threads; #229 owns that larger model.

**Tech Stack:** Python 3 stdlib HTTP server/parser, inline HTML/CSS/JS app shell, pytest, Playwright guard.

## Global Constraints

- `watch.py` remains a single stdlib-only server and offline-clean app shell.
- Every human submission is recorded by `do_POST` before parse, validation, or dispatch.
- `.dreamwork/answers.md` is documented and linted in the same increment that teaches the loop to write/read it.
- Route/view changes obey `transitions.md`; drafts survive live re-renders.
- The human-supplied governance question is the first real open entry in this repo.

---

### Task 1: Define and parse the answers channel

**Files:**
- Modify: `watch.py`
- Modify: `test_watch.py`
- Modify: `file-formats.md`
- Modify: `lint.py`
- Create: `.dreamwork/answers.md`
- Modify: `SKILL.md`

**Interfaces:**
- Produces: `parse_open_answers(text)`, `parse_answered_answers(text)`, `answers_health(text, entries)`, `append_human_question(text, question, stamp)`, `collect(...)[answers_*]`.

- [ ] Write failing parser/collector/writer/lint tests.
- [ ] Run focused pytest and observe the missing-interface red.
- [ ] Implement the minimal two-section channel using the shared entry parser.
- [ ] Document exact format and tick folding contract.
- [ ] Seed the human's supplied question.
- [ ] Run focused pytest and lint green.

### Task 2: Add `/answers` and `/ask`

**Files:**
- Modify: `watch.py`
- Modify: `test_watch.py`
- Create: `dev/capture/answers.mjs`
- Modify: `justfile`
- Modify: `watch-design.md`

**Interfaces:**
- Consumes: `data.answers_open`, `data.answers_answered`, `data.answers_health`.
- Produces: client route `answers`, view `buildAnswers(d)`, POST `/ask` body `{question, from}`.

- [ ] Write a failing static route test and browser guard for submit → durable open entry → live card.
- [ ] Run focused pytest/guard and observe red.
- [ ] Add persistent chrome route/title/crumb and compact ask form; render open/answered entries read-only.
- [ ] Add `_handle_ask`, using the existing pre-dispatch submission witness and writing a wake event only after success.
- [ ] Preserve in-progress textarea/focus across `/mtime` renders and surface 404/409/unreachable failures without clearing words.
- [ ] Verify transition/reduced-motion behavior in the browser guard.
- [ ] Run focused pytest/guard green.

### Task 3: Verify and land

**Files:** all above.

- [ ] Re-read diff against the human request and exclude threaded-chat scope.
- [ ] Run `pytest -q test_watch.py`, `python3 lint.py --target .`, focused browser guard, and `git diff --check` (full guard only if host load permits).
- [ ] Commit in the worktree, merge to master, deploy `watch.py`, and verify with `deployed.py`.
- [ ] Update `.dreamwork/tasks.md` and status in the coordinator checkout.

--- SUMMARY ---

- Add a separate, durable human-to-dreamer question channel at `.dreamwork/answers.md`.
- Reuse the proven entry grammar while keeping authorship and direction explicit.
- Add `/answers` plus a witnessed `/ask` write path; the loop answers by folding entries.
- Seed the requested governance question, document/lint the format, and red-prove browser behavior.
- Keep threaded agents, queues, and chat lifecycle out of this MVP; #229 remains the design lane for them.
