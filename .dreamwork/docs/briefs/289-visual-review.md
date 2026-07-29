# Brief — #289 visual review: the review-decision token on the dashboard's review list

Lane: `lane-289viz` · READ-ONLY against the repo · screenshots to `/tmp/289viz/`.

Context: #289 landed (read path LEFT JOIN, `.rdecision` token + `/question`
link, `/decide` handler, #463-idiom arrival) and is deployed on :35110 — but
the **live store's `review_decision` table is empty**, so the deployed page
shows every row `unlinked` (no marker, correct by contract). The pixels that
need judgement only exist against a store with decisions. You will build that
fixture and LOOK at it.

## What to build (throwaway, in /tmp — never in the repo)

1. A temp target dir with a `.dreamwork/` containing: a store-mode ledger
   (`ledger_store.open_store` + the cutover watermark — copy the shape from
   `test_watch.py`'s `_store_target` helper), a `review/` dir with 4–5 real
   artifact HTML files (copy any from `.dreamwork/review/`), and
   `review_decision` rows planted via the REAL
   `ledger_write.record_review_decision`: one `accepted`, one `rejected`,
   one `pending` (each with a plausible question_title), one artifact left
   with NO row (unlinked).
2. Serve it: `python3 watch.py <tmptarget> --port 39895` (guard port range;
   check it's free first, `ss -tln | grep 3989`). Auth: loopback is trusted
   by default.
3. Screenshot the dashboard's review list at desktop (~1280px) and mobile
   (~390px) widths with headless Chromium (the
   `headless-browser-screenshots` skill's idiom, or the repo's
   `dev/capture/` playwright setup). Full-page and a cropped close-up of the
   four rows.

## What to judge (the acceptance bar is EXCEPTIONAL — watch-design.md)

Load `watch-design.md` and `transitions.md` before judging. Verdicts:

- **The ramp, not the colour, carries done.** accepted ✔ / rejected ✘ read
  as *settled* (dim like a folded entry); pending reads as *in flight* (one
  step brighter); unlinked shows NO marker and the row looks identical to a
  pre-#289 row. If pending and accepted are indistinguishable at a glance,
  or unlinked shows any glyph, that is a FAIL.
- **Glyph legibility** at the real rendered size (.7rem): ✔ vs ✘ must be
  unmistakable at desktop AND mobile. Check against the page's type ramp —
  a token that reads as noise at 390px is a finding.
- **The question link** (`/question?qid=…`): hover state uses `--accent`
  (`.rqlink:hover .rdecision`) and nothing underlines (the design's
  no-underline rule). Click-through lands on the question.
- **Spacing/alignment:** `.6ch` margin, no wrap, the token does not shove
  the age/pip cells — the row's rhythm matches its undecorated siblings.
- **Reduced motion / arrival:** inspect, don't trace — the `.rdecision`
  carries the standing `.55s` transition and `revealReviewDecisions` uses
  the #463 one-shot `.dreamin`; confirm in source that reduced-motion skips
  the pose (the lane's pytest already pins the end state).

## Report

PASS / FINDINGS with the screenshots' paths, one line per verdict above,
and anything your eye catches that the list did not. If FINDINGS: severity
(blocker / polish) and the exact pixel evidence. Do not edit the repo.
Hand-off obligation (#398): if you cannot finish, append your state to
`.dreamwork/handoffs.md` (main checkout) before stopping.
