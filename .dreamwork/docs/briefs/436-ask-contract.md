# Brief — #436: `#ask` is a criterion naming a selector most of the corpus lacks

Repo: `ud-dreamwork`. Worktree: **`.worktrees/askcontract`**, branch **`wt/askcontract`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

Lane-owns: review-artifact.template.html, .dreamwork/review/, review_artifact.py

## The defect

Read `#436` in `.dreamwork/tasks.md`. The `#ask` criterion and its checker exist (`1dd973f`) and **three**
artifacts carry the element: `421`, `417`, `263`. **The other 19 have none**, so `above_fold.mjs` reports
`#ask MISSING` and gates nothing about them. A criterion naming a selector most of the corpus lacks is a wish,
not a standard — which is why `above_fold` sits in `lint.NOT_GUARDS` today with that reason written down.

## The two traps, both named in the entry

1. **Do not retrofit by adding an empty `#ask` to each page.** The id must wrap the **actual decision**, or the
   check passes on a page whose ask is still buried — the same hollowness in a new place.
2. **Pages with no decision to make** (a design note, a schema) must be **exempt by declaration**, not by
   carrying a decoy element. Design that declaration: where it lives, and how the checker reads it.

## The cost that shapes the order of work

**Touching `review-artifact.template.html` re-stamps every built artifact, and 12 of 23 have no `src/`** and
cannot be rebuilt by `review_artifact.py`. So:

- **Measure first.** List which artifacts have `src/`, which do not, and which of each carry a real decision.
  Report the table. That inventory is most of the value here and it does not exist yet.
- **Retrofit only what has `src/`** and a genuine decision. For a page with no `src/`, say what the options are
  (leave unmeasured and declared-exempt, or reconstruct a `src/`) — **do not hand-edit a built artifact**;
  it is generated and the next build would silently overwrite it.
- **Register the walking guard only after the retrofit**, or the suite reds over 19 pre-contract artifacts.
  If you cannot finish the retrofit, **do not register the guard** — say so and leave it.

## Done means

1. The inventory table exists in your report (and in the doc if you write one).
2. The `#ask` requirement and the exemption declaration are **documented**, and every artifact that has `src/`
   and a real decision carries a **meaningful** `#ask` wrapping that decision.
3. If and only if the corpus is now consistent: the walking guard is registered in `DEFAULT_GUARDS` and
   `above_fold`'s `lint.NOT_GUARDS` reason is updated or removed. Otherwise both stay as they are, stated.
4. **Red-first**: an artifact with a decoy/empty `#ask` must fail your check. **A green red-run is a finding,
   never a relief.** Name the production line whose change reds it.
5. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1078). **Do not run the full
   `just test`.** Do not touch :35110, the heartbeat, the monitors, or the loop.
6. `node dev/capture/above_fold.mjs <artifact>` still passes for `421`, `417`, `263` — their asks sit at
   `top=218/266`, `246`, `188`. The tool now **derives** the fold from the live route (`#432`); trust and print
   its number.

## Files

Yours: `review-artifact.template.html`, `.dreamwork/review/src/**`, `.dreamwork/review/**` (built output only
via `python3 review_artifact.py build`), `review_artifact.py`, and a new `dev/capture/<name>.mjs` **only if**
you register it.

**Not yours:** `file-formats.md` (**a live lane holds it for `#402a`** — report the exact lines you want added
instead), `watch.py` and `justfile`'s composer/guard areas (**a live lane holds both for `#177`**; you may add
a `DEFAULT_GUARDS` line only if the `#177` lane has landed by then — check `git log` and say what you found),
`dev/capture/dom.mjs`/`confirmation.mjs` (**held for `#444`**), `lint.py` except its `NOT_GUARDS` entry,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`.

## Practical

2 threads. `git add <newfiles>` then `git commit --only <paths>` — **never `git add -A`**. **Commit before you
finish.** **This is bigger than one increment**: land the inventory plus the documented contract plus the
`src/`-having retrofits, and leave the guard registration to a follow-up if the corpus is not consistent. Say
what you left.

## Report

Which model you are; the inventory table; the exemption mechanism you designed; which artifacts you retrofitted
and which you could not and why; whether you registered the guard and why; the production line whose change
reds your check; the exact `file-formats.md` lines you want added; and confirmation you did not hand-edit a
built artifact, run the full `just test`, or touch :35110.
