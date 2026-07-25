# A rendering is not a record

dreamer-qsec, 2026-07-25 18:00. Task: #199, `fd3ae3b` (handler half; the
contract half is the coordinator's, written in parallel against a shape agreed
before either was built).

## What landed

Every POST to the watch server writes its body to `.dreamwork/submissions.log`
as the **first act of `do_POST`** — before dispatch, before parse, before
validation. One call site rather than four, so a handler added later gets the
guarantee by existing. Guard: `dev/capture/submitlog.mjs`.

## The thing worth carrying: the guard found the best argument for the feature by failing

The guard submits an answer and then checks it landed. It reported that an
**accepted** answer had not — and it was right about what it saw. `append_answer`
hard-wraps what he wrote, so the file held

```
  - **Answer (via watch, 2026-07-25 17:47):** an answer that lands
    3160481
```

His string was never in questions.md. Nobody had noticed, because nobody had
ever searched that file for his exact words — every reader reads it rendered.

So the claim this feature was built against ("his answers live in exactly one
place") was understated. They lived in **no** place verbatim. questions.md is a
*rendering*: wrapped, prefixed, timestamped, section-placed. `submissions.log`
is the first copy of what he actually typed. That distinction is the difference
between a backup and a duplicate, and it is the reason the log stores `req`
parsed rather than a prose summary.

The general form: **before trusting "it is saved in X", check that X holds the
bytes and not a presentation of them.** A file that is written *for* a reader
has almost always transformed what it stored.

## Design notes that were not obvious

- **Unvalidated on purpose.** The payload that fails validation is precisely
  the one worth keeping, so a body that is not JSON — or not UTF-8 — is stored
  verbatim as `raw`, with `why` saying which way it was unusable. A design that
  logged only the parsed request drops exactly the cases the file exists for.
- **`req` parsed, not an escaped string.** `json.loads` → `json.dumps`
  round-trips every value, so nothing is lost, and the line stays greppable
  rather than turning every newline in his answer into a literal `\n`.
- **413 changed meaning deliberately.** It used to mean nothing was read and
  nothing was kept. It now reads the cap, keeps it with `truncated: true`, and
  then refuses — a too-long answer loses its tail rather than all of it.
- **It cannot raise.** A logging failure must never be the reason his answer
  was refused.

## And the vacuous-loop trap caught me inside an hour of reading about it

My line-shape test read GREEN against a `watch.py` that wrote no log at all: a
per-line loop over an empty file passes every assertion inside it. That is the
guard README's *"ask what your own check does when the subject is absent"*,
verbatim, and I had read that page the same afternoon. Knowing the trap is not
the same as running the check against nothing and seeing what it says — which
takes ten seconds and is the only reliable form.

## Verification

Nine unit tests, red first, covering both 409 paths, a non-JSON body, a
non-UTF-8 body, the oversize case, the ordering claim (no questions.md at all →
404, still logged), an unroutable path, and the line shape. The guard forces a
real 409 the way #116 caused them — the page holding a title the file will not
match — driven through the real box, the real send button and the client's own
fetch. Shown red against the pre-#199 server, with the refusals and the accepted
write both passing as positive controls. `just test`: 347 passed at the time of
the commit, lint clean, 22/22 guards.
