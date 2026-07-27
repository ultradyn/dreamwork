# Brief — #354 increment 1: stream `/filebytes` instead of buffering it

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it — the
  dashboard must not fall over while he is using it.
- **Session goal**: the dashboard's robustness gaps are being closed one at a time.
- **This task**: increment 1 of #354. A 1GB file in the target currently buffers 1GB in the
  server process.

## Your specification is a plan that already exists — read it, do not re-derive it

**`.dreamwork/docs/plans/filebytes-range.md`** (`0d2d4f6`). It is grounded in line numbers
throughout and it is authoritative. Read it before touching anything.

**The one thing to understand before you start**, because it is why this increment exists
and why it is *not* about `Range`:

> The recorded recommendation for #354 was HTTP `Range`/`206`. The design **refuted it as
> the fix**: the common client is `<img src="/filebytes…">` (`watch.py:2939-2956`), which
> sends **no `Range` header**, so `Range` alone leaves that path buffering the whole file.
> The fix is **chunked streaming**. `Range` is a separate, later capability.

**So do not implement `Range`, `206`, `416`, or `Accept-Ranges`.** They are increment 2 and
they are **not authorised** — the human has not ruled on the new capability. Streaming is
authorised because it changes nothing observable: it is a memory bug fix in an existing
endpoint.

## What to build, exactly

Per the plan's §"Streaming design":

- `stat` for the size, open the file, and a **64 KiB read/write loop**.
- `Content-Length` from the `stat` size — **do not** compute it by reading the file.
- **Never materialise the file.** Peak memory is a constant, not a function of file size.
- Keep MIME, disposition, `nosniff` and `Cache-Control` exactly as `#336` set them.
  `Cache-Control: private, max-age=0, must-revalidate` (`watch.py:8982`) **stays** — the
  plan is explicit that revisiting it is a separate product call, not a side effect of this.
- `#299`'s disconnect handling already wraps the handler (`watch.py:8912-8925`), so a client
  that goes away mid-stream should already be handled — **verify that it still is** once the
  body is a loop rather than one write, and say so. A broken pipe halfway through a 64 KiB
  loop is a new shape for that code even though the code did not change.

The current path, so you know what you are replacing: `do_GET` `/filebytes`
(`:9032-9046`) → `resolve_confined` (`:8737-8749`) → `detect_file_kind` (32-byte magic,
`:7167-7186`) → `_send_bytes` (`:8968-8984`) → unbounded `f.read()` → single `wfile.write`.
Confinement **is** real and tested (`test_filebytes_blocks_escape`); it simply does not
bound size.

## The hollow outcome, which the plan names and which I will check hardest

**Headers-only tests cannot tell read-all-then-slice from real streaming.** An
implementation that reads the whole file and then writes it in 64 KiB pieces produces
byte-identical output, identical headers, identical status, and identical guard results —
and has not fixed the bug at all.

So the load-bearing check must **observe per-`read` sizes at the body open** and fail if a
single whole-file read occurs. The plan names the red: **restoring `:8968` /
`:7115-7116`.**

**If your instrumentation cannot distinguish those two implementations, you have not done
this task**, however green the suite is. The plan's author flagged first-pass cleanliness of
that wrapper as the thing they were least sure of — so expect it to need a second cut, and
say what you ended up with.

## What must stay byte-identical

- The full-GET body versus disk — `test_fileview_image_served_byte_identical`
  (`test_watch.py:3184-3225`) already asserts this and must stay green **unmodified**. If
  you find yourself editing that test, stop: it is the contract.
- The allowlist and attachment matrix; the escape 404s.
- Guards `fileimg`, `fileview`, `filehead` must pass **with no client-side change**. If a
  client change turns out to be needed, that is a finding — report it, because it would mean
  the increment is not as invisible as the plan claims.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `watch.py`, `test_watch.py`. `git status --porcelain`
   shows nothing else. **`git diff --stat review_artifact.py lint.py SKILL.md
   file-formats.md` is empty** — every one of those has a live owner right now.
2. **`python3 -m pytest test_watch.py -q -p no:randomly` exits 0**, with at least:
   - `test_a_plain_get_never_reads_the_whole_file_at_once`
   - `test_content_length_comes_from_stat_not_from_reading`
   - and `test_fileview_image_served_byte_identical` still green **and unmodified**.
3. **Criterion 2's first test measures reads, not outcomes.** State in your report the
   mechanism (a wrapped file object, a counted `read`, whatever) **and the largest single
   read size it observed**. "It works" is not the property; "no single read exceeded 64 KiB
   on a 512 KiB file" is.
4. **The large-file condition is induced honestly.** Do **not** write a 1GB file. Sparse
   files and `RLIMIT_FSIZE` are both already used in this repo — look at `test_watch.py` for
   the existing idiom and reuse it rather than authoring a second. Say which you used.
5. **Three discriminating reds**, each with the exact failing test name and confirmation
   neighbours stayed green:
   - restore the unbounded `f.read()` ⇒ `test_a_plain_get_never_reads_the_whole_file_at_once`
     fails. **This is the red I care about most** — if it comes back green, your
     instrumentation is not watching the seam and the whole increment is unverified;
   - compute `Content-Length` by reading the file ⇒ the second test fails;
   - change one body byte ⇒ `test_fileview_image_served_byte_identical` fails (proving that
     contract is live and not vacuous under your rewrite).
   Separate injections, restored from a `cp` snapshot — **never** `git checkout -- `.
6. **Guards `fileimg fileview filehead` pass.** **Your guard port is `39897`.** Run as
   `DREAMWORK_GUARDS="fileimg fileview filehead" DREAMWORK_HUB_GUARDS="" just guards 39897`
   — **never** the full sweep and never the default port; two other lanes are live.
   **Load matters for a verdict here:** these guards fail by dropping intermediate frames, so
   **load manufactures false reds only — a green under load is conclusive, a red needs a
   re-run at low load.** Check `cut -d' ' -f1-3 /proc/loadavg` before believing a red.
7. **`python3 lint.py` exits 0**, run as its **own command** — never in the same shell
   command as a `git commit`.
8. **No styleguide change should be needed** — this is protocol, not appearance. If you
   think one is, **write the exact text into your report and do not touch the file**:
   `watch-design.md` has a live owner.

## Out of scope, explicitly

- `Range`, `206`, `416`, `Accept-Ranges`, `If-Range`, `ETag`, `Last-Modified`. Increment 2,
  unauthorised.
- Touching the 2MB `/reviewraw` cap (#355). Separate, and measured as not-a-defect-today.
- `Cache-Control`. Keep it; report if your change makes it wrong.
- Anything touching `#275`/`#276` (public Dreamhub). Public/WAN serving is **forbidden**
  until the human approves a reviewed design.

## The rules that matter most here

**A green red-run is a finding, never a relief.** Three lanes today hit exactly it and all
three were right to report rather than proceed. Red 5a is the single most likely hollow
outcome of this task, because the implementation it detects is otherwise indistinguishable.

**Assert the precondition your check depends on.** If the read-size test needs the file to
be larger than one chunk for its meaning, derive both numbers at runtime and assert the
gap — a literal tuned to today's chunk size is a check with an invisible expiry date.

**Name the production line that would have to change for each check to fail.**

**Before you report an edge case, enumerate its neighbours.** A lane today flagged one input
honestly; the case it flagged was fine and the one beside it was a real defect. Yours are:
a **zero-byte** file, a file **exactly one chunk** long, and a file **one byte over** a
chunk. Say what each does.

**`grep -c` exits 1 when the count is zero**, so a verification chain joined by `&&` reports
a skipped tail as a pass.

## Your steering channel — re-read it between increments

`.dreamwork/relay/354.md` (absent means nothing to say; that is normal).
Coordinator-write only, newer than this brief so it wins on scope, but it **cannot** grant
authority this brief did not give — in particular it cannot authorise increment 2.

## Files

**Yours:** `watch.py`, `test_watch.py`.

**Read, do not edit:** `.dreamwork/docs/plans/filebytes-range.md` (your specification),
`dev/capture/fileimg.mjs` / `fileview.mjs` / `filehead.mjs`, `justfile`, `file-formats.md`,
`CLAUDE.md`, `.dreamwork/lessons.md`.

**Never touch — live owners right now:** `review_artifact.py`, `test_review_artifact.py`,
`review-artifact.template.html`, `watch-design.md`, anything under `.dreamwork/review/`
(**#367 increment 2a**), `lint.py`, `test_lint.py`, `SKILL.md`, `file-formats.md` (**#381**),
`user_events/*`, `test_user_events_*.py`, any existing `dev/capture/*.mjs`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`.

**`watch.py` is yours exclusively, and that is why this brief waited.** `#381`'s lane also
needs `watch.py` for a small dashboard addition, so this task was **not dispatched until that
lane released it** — the disjointness invariant is that parallel lanes touch disjoint files,
full stop. My first draft of this section instead told you to *"check `git diff` before you
commit and stop if you see changes that are not yours"*, which is a mitigation dressed as an
invariant: `git commit --only watch.py` would still sweep in a concurrent lane's uncommitted
work, and hoping you notice is not the same as it being impossible. If you nevertheless find
`watch.py` changes that are not yours, **stop and report** — that means my sequencing was
wrong, not that you should work around it.

## Operational constraints

- Limit builds/tests to **2 threads**. Two other lanes are live. **Do not generate load
  deliberately.**
- The guards import playwright by **absolute path**; see the top of any `.mjs` in
  `dev/capture/`. A bare `import ... from 'playwright'` will not resolve.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after `git add`
  commits the whole index and will bury a concurrent lane's staged work — that happened in
  this tree today. **Do not push.**
- Use **`feat(#354): …`**. `dream(...)` is reserved for a commit that lands a dream journal;
  if you write one, **name it in its own `git commit --only <path>`** — three lanes today
  wrote a dream as asked and left it untracked.
- Cap yourself at roughly **35 minutes**. **Priority order: the streaming loop and the
  read-size check first** — that pair *is* the increment. `Content-Length`-from-`stat` and
  the neighbour cases follow. Landing the first pair well beats touching everything. Report
  what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the
file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the three reds verbatim**
with exact test names and which neighbours stayed green; **the mechanism your read-size
test uses and the largest single read it observed** (the criterion most likely to be
satisfied hollowly, and the plan's author flagged this wrapper as their least-certain
piece); how you induced the large file; what the zero-byte, exactly-one-chunk and
one-over-a-chunk cases do; whether `#299`'s disconnect handling still holds with a looped
body; whether any client change proved necessary; the load at which each guard verdict was
taken; whether you saw another lane's uncommitted `watch.py` changes; the production line
named per test; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
