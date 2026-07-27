# Brief — `/filebytes` buffers a whole file with no cap (#354). Design only.

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.

**This task writes a PLAN and nothing else.** You must not implement it. Do not
edit `watch.py`. The human has not authorised this feature, and question 3 below may
show that the ledger's own recommendation does not fix the bug — either reason alone
makes implementing first the wrong order. Your deliverable is a document he can rule
on.

*(Refreshed 2026-07-28 08:05: `watch.py` is no longer held by another agent — that
line was written when it was. It is still yours to **read only**, because this task is
design. Two lanes are live elsewhere: `review_artifact.py` + the review frame +
`watch-design.md`, and `user_events/apply.py`.)*

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it;
  the dashboard is that surface, and `/file` / `/filebytes` are how he reads a file
  from it.
- **Session goal**: the dashboard's robustness gaps are being closed one at a time.
- **This task**: #354, filed P2 from a review by another agent that correctly
  declined to fix it in scope.

## What is established — inherit it, do not re-derive it

Quoting the ledger entry, which is itself quoting the agent that found it:

> `read_text` caps at 200_000 characters; `/filebytes` deliberately does not cap,
> and the agent's reasoning is right and worth keeping: **a cap on a byte stream
> corrupts an image rather than truncating readable text**, so the text cap's idiom
> does not transfer. Consequence: a 1GB PNG in the target buffers 1GB in the server
> process. Mitigated by confinement (only files inside the target are reachable) and
> by the dashboard being loopback-only today, which is exactly the mitigation
> `#275`/`#276` would remove.

The recorded recommendation is **HTTP `Range` / `206 Partial Content`**, on the
grounds that it is the only cap that does not corrupt — which makes this a real
feature rather than a one-line guard, and is why it was not smuggled into #336.

The entry also parks a second question: `Cache-Control: private, max-age=0,
must-revalidate` was chosen conservatively because `--autoreload` re-execs on source
mtime and a stale image mid-edit would confuse. Revisit it; do not assume it is
wrong.

## What the plan must answer

Read the actual code first — `/filebytes` and `/file` in `watch.py`, and how
`read_text`'s cap is applied — and ground every claim in what is there. State line
numbers.

1. **The exact current behaviour.** How is the body produced and sent today? Where
   would a 1GB file be held, and in how many copies? Is the confinement claim
   ("only files inside the target are reachable") actually true — name the check.
2. **The `Range` design**, concretely enough to implement without a second design
   pass: single-range only or multi-range; `Accept-Ranges`; `Content-Range`;
   `416 Range Not Satisfiable` and when; unsatisfiable-vs-malformed handling; how
   a range interacts with `If-Range`/`ETag` if at all. **Recommend the smallest
   thing that is correct** and say explicitly what you are leaving out.
   Four things the plan must **decide rather than leave to the implementer**, because
   each has a defensible wrong answer: an unsatisfiable range (start past EOF) should be
   `416` with `Content-Range: bytes */<total>`; a *syntactically invalid* `Range` is
   **ignored** per RFC 9110 — serve `200`, and note that this is deliberately not an
   error, which is the rule an implementer is most likely to get backwards; suffix
   (`bytes=-500`) and open-ended (`bytes=500-`) ranges both work; and multi-range
   (`bytes=0-9,20-29`) may be **refused** with a plain `200`, because
   `multipart/byteranges` is real work for no local benefit — but say so explicitly
   rather than omitting it.
3. **Streaming, which may matter more than ranges.** A browser fetching an `<img>`
   does not send `Range` — so ranges alone do not fix the 1GB buffer for the common
   case. Say whether the real fix is chunked streaming from disk with a bounded
   buffer, with `Range` as a second, separate capability. If you conclude the entry's
   own recommendation is incomplete, **say so plainly**; that is a valuable result,
   not a contradiction of your brief.
4. **What breaks.** Which existing guards, tests, or dashboard code paths touch
   `/filebytes` (`fileimg`, `fileview`, `filehead` are the guards to check)? What
   would have to change, and what must stay byte-identical?
5. **The red-first test plan.** For each behaviour, name the check and **the
   production line that would have to change for it to fail**. This repo's rule is
   that a check is not verification until it has been red, and that a check whose
   own scaffolding stands in front of the code cannot fail — so for anything needing
   a fake or a patch, name the real seam instead. A large-file test must not
   actually write 1GB; say how you would induce the condition honestly (sparse
   files and `RLIMIT_FSIZE` are both used elsewhere in this repo — look at
   `test_watch.py` for the existing idiom).
6. **Cost and staging.** Which increments, in what order, each landable and
   verifiable on its own.
7. **`#355`, the same question one door along**, because a plan that fixes
   `/filebytes` and leaves `/reviewraw`'s `read_text(limit=2_000_000)` unexamined will be
   read as an oversight. **I measured it so you do not have to guess:** the largest of the
   18 artifacts is **84,987 B — 4.2% of the cap, 23.5x headroom**, so it is **not a defect
   today** and the plan must not dress it up as one. But the growth vector is now
   demonstrated rather than hypothetical: the *second*-largest artifact was built today and
   got there almost entirely from **one 40 KB base64-embedded screenshot**. Artifacts must
   be offline-clean, so every image is inlined at ~1.33x its bytes — meaning the cap gets
   reached by embedded evidence at roughly 25 screenshots' worth. Two recommendations
   wanted, both small: **make truncation loud** (an artifact over the cap currently renders
   as a **blank frame with no error**, which is the worst failure shape available), and
   **record the answer to "what about `/reviewraw`'s `Content-Type`?"** in a comment beside
   the code, since the trust story genuinely differs — a self-contained artifact the loop
   itself built, confined to `.dreamwork/review/`, is not an arbitrary file. **Do not
   recommend raising or removing the cap**; recommend noticing it.

## The hollow outcome this plan should pre-empt

When this is eventually built, the most likely wrong implementation **keeps every status
code and header correct**: it reads the whole file and slices in memory. Ranges look
perfect, the bug is untouched. So the plan's test section must name a check that
**distinguishes those two implementations** — how many bytes are requested per read call,
or how many reads happen — rather than one that only inspects the response. If your test
plan cannot tell them apart, say so plainly; that is the most useful sentence you could
write here.

## Deliverable, and the format

Write **`.dreamwork/docs/plans/filebytes-range.md`**. Follow the shape of the
existing plans in that directory — read one first, e.g.
`review-essential-marks.md` or `task-transition-boundary.md`.

End the document with, literally:

```
--- SUMMARY ---
```

followed by a concise, explanation-focused dot-point summary covering the major
parts, decisions, and open questions. That is the human's house style and he reads
the summary first.

Where you are uncertain, **say you are uncertain and why** — do not smooth it over.
An honest "not confident about X, and here is what would settle it" is worth more
than a confident guess, and this repo has a documented habit of paying for the
latter.

## Files

**Yours:** `.dreamwork/docs/plans/filebytes-range.md` (new).

**Read freely, do not edit:** `watch.py`, `dev/capture/file*.mjs`, `test_watch.py`,
`justfile`, `file-formats.md`.

**Never touch:** anything under `dev/capture/`, `watch.py`, `test_watch.py`,
`review_artifact.py`, `test_review_artifact.py`, `review-artifact.template.html`,
`watch-design.md`, anything under `.dreamwork/review/`, `user_events/*`,
`test_user_events_*.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single append below),
`bin/ud-dw-generate`. You are writing one new plan file and nothing else.

**You need no server and no port.** Do not run `just guards` — another lane is using
that port range, and nothing in a design task renders.

## Operational constraints

- Limit any builds/tests to 2 threads. You should not need to run tests at all.
- Commit your plan, **`git commit --only <paths> -m …`** (`git add <path>` alone does NOT isolate it —
  `git commit` commits the whole index and will bury other agents' staged work — several lanes are live in this tree). Do not push.
- Cap yourself at roughly 25 minutes.

## How to report

Append **once**, at the end, using a single shell append (`cat >> …` or `>>`),
never by rewriting the file, because other agents append to the same file
concurrently:

`.dreamwork/inbox.md`

State: the path you wrote; your answer to question 3 in one sentence, because it is
the one that decides whether the ledger's recommendation survives; anything you found
that is out of scope (I will file it); and what you are not confident about.
