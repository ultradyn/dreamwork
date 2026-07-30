# #397 — should the dashboard's client be extracted from `watch.py`?

**Tasks:** #397 (this plan). Related: #264 (the evidence that filed it), #368
(the human's own "break up the large Python files" ask), #124 (an older
"break up watch.py" ledger entry).
**Status:** ~~design; no implementation authority~~ → **IMPLEMENTED
2026-07-31.** The extraction below was built as designed: eight files under
`client/`, `__file__`-relative loading, the boot preamble left as a generated
string. Proven by capturing the served page before and after and requiring
byte equality (576,217 bytes, sha256 `08d4e0bf33cb02cb…`, `--dev` variant
too).

**Two of this plan's three reasons to decline had expired, and one of its
four costs turned out not to exist:**

- *"no build step is a constraint"* — lifted by him on 2026-07-30 (`#505` Q2).
- *"`just deploy` BREAKS and must become a directory snapshot"* — already
  paid by `#480`/`#425`. `ship_siblings` walks the transitive import closure
  plus `DATA_SIBLINGS`, makes subdirectories, and writes atomically. Adding
  the eight paths to that tuple was the whole change; the recipe was not
  touched.
- *"the `serving` guard BREAKS (needs one `cpSync`)"* — **it does not.**
  `serveVerified` spawns `watch.py` from the repo root and only the TARGET is
  the temp copy, so `client/` resolves normally. The guard passes unchanged;
  this plan's prediction was wrong.
- Still true and still paid: `--autoreload` needed the assets in its watched
  set, and `dev/styleguide_audit.py` needed re-pointing. One more the plan
  did not name: `dev/capture/bdinput.mjs` reads `BURN_LIMIT_CAP` out of
  watch.py source, which now lives in `client/views.js`.

The remaining reason to decline — that this does not unblock `#331`/`#352`,
which are Python parser work needing the separate `#368` split — still
stands, and is not what this was done for.
**Date:** 2026-07-28. Every line number and count below was re-grounded against
the tree in this session, and the method for each is stated so it can be
re-derived.

---

## The recommendation (first, because it decides the rest)

**Lean: do not extract now — but it is closer than the brief's framing makes it
look, and the decision is genuinely his.** The mechanics are cheap: the
interpolation count inside the client assets is **1** (a single `/*DEV*/false`
marker), so the HTML/CSS/JS can become static files with almost no templating.
What stops me recommending it is not the cost of doing it — it is that **client
extraction would not unblock the queue's hardest items** (`#331` and `#352` are
Python parser work, not client source; they need the separate `#368` Python
split), **it multiplies the registry-coupling damage class that actually bit
today** (`markrail`, the artifact-staleness warnings — `#264` evidence Q5 item
5), and **the throughput win it buys is already captured more cheaply and
reversibly by a worktree** (`#264` evidence Q3). The four concrete breaks it
introduces (deploy, the `serving` guard, autoreload, the styleguide audit) are
small and named below, not fatal — so if throughput is the binding constraint
for him, the full-client extraction is mechanically ready. "Leave it" is a
legitimate answer he may prefer, and the do-nothing column (§5) is real rather
than a straw man.

> The brief's framing — "is extracting it worth breaking the one-file deploy?"
> — is the right question. The answer this plan lands on is: **the one-file
> deploy is the smaller of the costs; the larger one is that this extraction
> does not hit the items actually blocking the queue, and it adds the damage
> class that hurt us today.**

---

## 1. What is actually in there (and the interpolation count)

### Structure correction — `server_class` is 10 lines, not 6,798

The brief inherits a measurement that names "`server_class` (`:262`) as 6,798
lines." That attribution does not hold against the tree. Verified three ways:

```
def server_class(family):                      # watch.py:262
    if family == socket.AF_INET:
        return http.server.ThreadingHTTPServer
    ...
    return IPv6ThreadingHTTPServer             # :271  — 10 lines total
```

`ast` reports `server_class` at **:262–:271 = 10 lines**; the largest `def` in
the file is `make_handler` at **434 lines** (`:8988–:9421`), and the largest
`class` is `Handler` at 429 (nested inside `make_handler`). **There is no
6,798-line function.** The bulk the brief attributed to one function is
actually **eight module-level constants** that hold the client source — the
names the `justfile`'s own styleguide audit already uses (`:350–388`: "the UI
lives in line-bounded module constants `STYLE`, `APP_BODY`, the `*_JS`
blocks"). This matters because it changes the picture from "one giant function"
to "eight named constants" — the code is already partly modularised; extraction
moves constants to files, it does not cleave a monolith.

### The 7,142 figure — holds, within method variance

Re-measured with Python's `tokenize` (which handles triple-quotes correctly,
unlike line-scanning): **80 triple-quoted blocks, totalling 7,222 lines.** The
brief's 7,142 is within method variance (the gap is ~80 lines, plausibly a
slightly earlier tree or a different tokeniser boundary). **The conclusion —
~75% of the file is string literals — holds.** This is not a re-derivation of
`#264`'s zero-concurrent-writes finding or the 75% claim; it is a precision
pass on one number, and the headline survives.

### The breakdown (grounded)

The 8 client-source constants, measured by `tokenize`:

| constant | span | lines | type | what it is |
|---|---|---|---|---|
| `STYLE` | `:333–:1585` | 1,253 | CSS | the `<style>` block |
| `APP_BODY` | `:1587–:1655` | 69 | HTML | the app shell (`<canvas>`, `.wrap`) |
| `COMPONENTS_JS` | `:1657–:2274` | 618 | JS | shared components |
| `VIEWS_JS` | `:2276–:3374` | 1,099 | JS | the route views |
| `FAVICON_JS` | `:3376–:3524` | 149 | JS | the favicon state machine |
| `ROUTER_JS` | `:3526–:5818` | 2,293 | JS | router + a little CSS |
| `COMMAND_JS` | `:5820–:6535` | 716 | JS | the composer / command path |
| `SHADER_JS` | `:6537–:7058` | 522 | JS | the persistent background |

**Totals:** CSS **1,253** (1 block) · HTML **69** (1 block) · JS **5,397** (6
blocks) · **client source 6,719 lines.** The remaining ~503 triple-quoted lines
are docstrings (27 small blocks, the largest 30 lines).

### THE INTERPOLATION COUNT (the number the brief asked for)

**Method:** (a) Python `tokenize` over `watch.py`, checking each triple-quoted
token's prefix for `f`/`fr`; (b) `grep -E "(STYLE|APP_BODY|..._JS)\.(replace|format)"`
for post-assignment mutation; (c) `grep "/*DEV*/"` for replace-target markers;
(d) count `json.dumps` in the `PAGE` assembly block (`:7085–:7098`).

**Result:**

| class | count | where |
|---|---|---|
| f-string interpolation **inside** the 8 client literals | **0** | none of the 8 carry an `f` prefix — all plain `"""` |
| `.format()` / `%` calls **on** any of the 8 constants | **0** | grep exit 1 (no matches) |
| replace-target markers **inside** the assets | **1** | `/*DEV*/false` at `COMPONENTS_JS:1658` (`window.DEV=/*DEV*/false;`), swapped once at server start, `PAGE.replace("/*DEV*/false","true")` at `:8989` |
| dynamic values injected **at assembly** (a preamble, not inside the assets) | **8** | `json.dumps` of `CORE_COMMANDS`, `TINTS`, `TINT_DEFAULT`, `RUN_MODES`, `RUN_MODE_DEFAULT`, `RUN_MODES_PLANNED`, `RUN_ARM_MS`, `RUN_MODE_DESC`, concatenated ahead of the JS at `:7085–:7097` |
| f-string in the shell (not a client asset) | **1** | `f'<title>{title}</title>'` in `page_shell` (`:7070`) |

**The headline number, stated plainly: there is exactly 1 non-static token
inside the client assets themselves — the `/*DEV*/false` marker.** The CSS,
HTML and JS bodies are otherwise verbatim static text. The 8 dynamic constants
are not interpolated *into* the assets; they are a separate Python-built
preamble concatenated in front of them at assembly. So the templating decision
extraction forces is tiny: one marker, and a boot preamble that can stay a
generated string or ride `/data.json` (the plugin-command half already does —
`justfile:7076`-ish / `watch.py` comment: "the plugin half rides /data.json").

**This is the cheapest possible extraction shape.** It is also, honestly, the
temptation: "it's almost free, so why not." §3–§5 are why not, or why maybe.

---

## 2. What extraction would look like (concretely enough to cost)

- **8 files under `client/`** (e.g. `client/style.css`, `client/app_body.html`,
  `client/components.js`, … `client/shader.js`). Names mirror the constants.
- **Loaded once at import, not per request.** Today `PAGE` is built at module
  load (`:7083`) and served verbatim (`:9096`); the only per-serve mutation is
  the one-time `/*DEV*/false` swap in `make_handler` (`:8989`), captured in the
  closure. Extraction keeps that exactly: read the 8 files at import, assemble
  `PAGE`, cache. Serve path unchanged.
- **Path resolution is load-bearing:** watch.py must resolve `client/` by
  `pathlib.Path(__file__).parent / "client"` — **not** by cwd, and **not** by
  `--target` (which points at a temp fixture copy). This single decision is what
  makes `just guards` survive (§3).
- **The 8-`json.dumps` preamble** stays a Python-built string concatenated
  ahead of the JS, exactly as today (`:7085–:7097`); or moves to `/data.json`
  so the JS becomes fully static. Either is a one-paragraph change, not a build
  step.
- **No bundler, no npm, no dependency.** Reading 8 files and concatenating is
  stdlib `pathlib` + `str`. This repo is offline-clean by contract; the plan
  introduces nothing that breaks that.

---

## 3. What it breaks — and these are the load-bearing ones

### `just deploy` — BREAKS, and must become a directory snapshot

Today (`justfile:329–344`):

```
git show {{rev}}:watch.py > "$snap"     # snapshots watch.py ALONE
python3 -c "ast.parse…" "$snap"          # validates it parses
nohup python3 "$snap" --target "$PWD" --dev
```

The deployed thing is a **single file** at `~/.cache/dreamwork/deployed/`. A
watch.py that resolves `client/` by `__file__` would look for it in that cache
dir — it isn't there — and **the live dashboard would serve a blank page**,
exactly the failure the brief named.

**What deploy must become:** snapshot `watch.py` **and** the `client/` files
from the rev into the deployed dir:

```
git show {{rev}}:watch.py      > "$dir/watch.py"
git show {{rev}}:client/style.css > "$dir/client/style.css"   # …one line per file
```

The deployed thing becomes a **small directory (~9 files)**, not a single file.
The property that actually matters — *"committed state only, never the working
tree; a dreamer's half-finished edit must not reach him"* (`justfile:325–327`)
— is **preserved**, because every file comes from `git show {{rev}}:`. The
single-file property that is lost is convenience, not correctness.

(Alternative that keeps single-file: a deploy-time concatenation that inlines
the client back into one watch.py. That is stdlib-only so it is not "dead on
arrival," but it is a **build step** — two code paths doing the same assembly
(import-time and deploy-time), which is a drift hazard. **Recommend the
directory snapshot; do not recommend the concatenation.**)

### `just guards` (the main recipe) — SURVIVES, with one rule

The recipe (`justfile:184–272`) runs `python3 watch.py --target "$OUT/target"`
**from the repo root** — it does not copy watch.py. The client files would be in
the repo, and `__file__`-relative resolution finds them. **It works unchanged,
provided watch.py resolves `client/` by `__file__` not cwd.** That rule is the
whole of what guards need from the main recipe.

### The `serving` guard — BREAKS (the one guard that copies watch.py)

`dev/capture/serving.mjs:64–95` is the **only** guard that writes watch.py into
a temp location and runs the copy:

```js
writeFileSync(join(DIR, 'watch.py'), bytes);          // :72 — watch.py only
const srv = spawn('python3', ['watch.py', '--target', DIR, …]);   // :86
```

It builds a temp git repo, drops watch.py into it, and runs it — **without any
client files.** Importing watch builds `PAGE` at module load (`:7083`); if
`page_shell` reads client files by `__file__`, serving's temp repo has no
`client/` → import fails or serves blank. **What serving needs:** one line —
`cpSync('client', join(DIR, 'client'), {recursive:true})` — beside the existing
`writeFileSync`. Named, not done: `serving.mjs` is a guard and off-limits to
this task. (No other guard copies watch.py — `grep writeFileSync.*watch.py`
across `dev/capture/` returns only `serving.mjs`.)

### `--autoreload` — REGRESSES unless the watcher gains the asset paths

`_watch_source_and_restart` (`:9425–9441`) watches **only** `os.path.getmtime(__file__)`
— watch.py's own mtime — and re-execs on change. Today, editing CSS *inside*
watch.py changes watch.py's mtime and triggers the re-exec, so the hot-reload
loop works. After extraction, editing `client/style.css` does **not** change
watch.py's mtime → **no re-exec → stale CSS until a manual restart.**

**Answer to the brief's question — yes, asset mtime should trigger autoreload:**
the watcher must add the 8 client files to its watched set (a few lines:
`max(os.path.getmtime(p) for p in client_files)`). Without it, the `just watch
--autoreload --dev` edit loop regresses for every CSS/JS change — which is
precisely the surface a design lane lives in. Small fix, but a real one to ship
in the same commit, or extraction trades a serialization cost for a
developer-experience cost.

### The styleguide audit — needs rework, not a break

`dev/styleguide_audit.py` (per `justfile:350–388`) decides "did this commit
touch presentation?" by resolving the boundaries of `STYLE` / `APP_BODY` /
the `*_JS` constants **inside watch.py at the audited commit** (`git show
<sha>:watch.py`). If those constants leave watch.py, the audit's diff filter
has nothing to find in watch.py — every client change would read as
"non-UI commit" and silently pass, which is the `#314` failure mode inverted
(false negatives instead of false positives). **What the audit needs:** resolve
boundaries against the `client/` files instead. Named; not done (`lint.py` /
`dev/styleguide_audit.py` are not this task's to edit).

---

## 4. The counter-argument, stated rather than buried

Extraction **multiplies the registry-coupling failure** — and that class is the
one that caused actual damage today, not the file-contention extraction would
fix. From `#264`'s evidence (Q5 item 5; incident #7):

- `markrail` was unregistered — a new file in `dev/capture/` reddened other
  lanes' `lint.py` baselines until it was added to `DEFAULT_GUARDS`
  (`justfile:188`). The lesson recorded it plainly: *"Nothing collided only
  because no other lane needed the `justfile` — that was luck, not design."*
- The artifact-staleness warnings came from the same shape: one lane's new file
  shifting baselines for lanes that never touched it.
- `#336`'s close cycle, `#396`'s flag geometry, the `review/` rebuild churn —
  all registry/baseline coupling.

Eight new files under `client/` means eight more things that: must be carried
by `deploy` (§3) and `serving`; must be excluded from or re-pointed in the
styleguide audit; and are a new ownership surface. **More files means more of
the coupling class.** This is not hypothetical — it is the documented shape of
this session's hardest coordination failures.

**Weighed honestly:** the registry-coupling class is real and bit today, but its
worst instance was caught and ratified (not silent corruption). The
file-contention extraction addresses caused a **throughput** cost (a shelved
brief, six queued tasks) — a real cost, but not the *damage* the registry class
inflicted. So the counter-argument narrows the scope (extract the minimum that
buys throughput; don't extract gratuitously) more than it defeats extraction —
but it is the reason this plan does **not** recommend "modularity for its own
sake."

---

## 5. What it costs to do nothing (the six tasks)

`#264`'s evidence captured the queue in `status.json`'s
`coordinator_next` ("six tasks queued behind one file"); cross-checked against
`.dreamwork/tasks.md` today, **all six are still under `## Open`** (lines
< 2702):

| id | line | what | why it queues on watch.py |
|---|---|---|---|
| **#352** | :793 | standardize the duplicated ledger parsing | "blocked on `watch.py` for the import change" |
| **#351** | :820 | `/file` highlight / wider / no-wrap | "blocked on `watch.py` being free" |
| **#337** | :1134 | `do next` falls back to `add idea` | "blocked on `watch.py` being free; sequence after #336" |
| **#331** | :1157 | one shared ids-only bold-span notion | edits the ledger parser **in watch.py** |
| **#322** | :1213 | paste images into the composer | "touches `watch.py` … filed not started" |
| **#295** | :1338 | subtle dithering on the background shaders | edits `SHADER_JS` **in watch.py** |

**Two honest qualifications, because "find them rather than trust the count":**
(a) `#371` (`do_POST` interrupted body) was the sixth at filing and has since
been **freed** — its entry reads *"no longer on `watch.py`, which is free."*
(b) `#319` (guards bind port 0) also *"needs `watch.py` to report the port"* —
so today the count is 5–7 depending on whether you count `#319` and the freed
`#371`. The headline — **~6 tasks serialize on one file** — is real and
dynamic. And `#354` increment 1 was **deliberately not dispatched** while
watch.py was held (`a6c0732`, *"brief written and deliberately NOT dispatched —
watch.py is contended"*): a correct, ready brief sat idle for no reason except
one file.

**Do-nothing is legitimate, and here is its real cost:** every dashboard feature
serializes against every request-path fix; ~6 tasks wait; a ready brief can be
shelved. It is a **throughput** cost, not a correctness one — nothing corrupts,
nothing is lost, the loop just goes one-watch.py-lane-at-a-time. If he prefers
the simplicity of one self-contained file over the throughput, "leave it" is a
defensible ruling. The cost is measured here so he can price it.

---

## 6. The smallest useful version — and which collisions it would have prevented

### This session's actual `watch.py` collisions (with shas)

From `#264`'s evidence Q4: watch.py was touched by **four parties,
sequentially** — `#277` (dreamfade), `#300` (rundesc), `#385` (age), `#391`
(prominence) — each merged before the next began; and `#354` inc 1 (request
path) was **shelved** (`a6c0732`) purely because the file was contended. The
collision extraction prevents is specific: **a client-source lane (CSS/JS)
serialized against a request-path lane** (`do_GET` / `make_handler` /
`collect`). `#354` (request path: `/filebytes` streaming) sat idle while
`#300`/`#385`/`#391` (client JS/CSS) held the file.

### CSS-only is a false economy here

The brief floats *"only the CSS, which is what a design lane touches and a
request-path lane never does."* Against this session's actual collisions that is
**insufficient**: three of the four client parties (`#277`, `#300`, `#385`)
touched **JS**, not just CSS. CSS-only extraction would separate `#391` /
`#295` (CSS/shader-via-CSS) from `#354` (request path), but leave `#277` /
`#300` / `#385` still colliding with each other and with request-path work on
the JS. **CSS-only prevents ~1 of this session's collisions for the same fixed
cost (deploy, serving, autoreload, audit) as the full extraction.**

### Smallest version that prevents this session's client-vs-request-path collisions

**Extract the JS constants** (the 6 JS blocks, ~5,397 lines) — because every
client task this session touched JS, and no request-path task does. That alone
separates the client lane from the request-path lane. CSS (1,253 lines) should
come with it because the extraction mechanism and its four fixed costs are
identical whether you move 1 file or 8 — so the marginal cost of CSS is ~zero
and it prevents the `#391`/`#295` collisions too.

**Net:** if extraction is approved at all, extract **the full client (all 8
constants)**. The fixed costs (§3) are paid once; partial extraction buys fewer
collisions for the same price. There is no cheaper "smallest useful version"
than the whole client, because the cost is dominated by the four breaks
(deploy, serving, autoreload, audit), not by the file count.

### What extraction would NOT have prevented (be honest)

`#264`'s evidence is explicit that the **majority of today's damage was not
file-contention**: shared CPU (load 125–161 starved motion guards; `#391`
dismissed as a flake, `b5d541a`), a shared registry (the `markrail` /
artifact-staleness class), and one overloaded single-writer (the coordinator).
Extraction fixes the *throughput* serialization (the shelved `#354`, the six
queued tasks); it would have prevented **none** of the CPU/registry
damage. Anyone selling extraction as the answer to "what went wrong today" is
answering the wrong question — and the brief is precise that the wrong question
is "how should watch.py be partitioned."

---

## What approval of this does not authorise

Nothing is built. Approving this plan accepts only the **analysis and the
trade-off**, not any code. It does **not** authorise:

- creating `client/` or moving any constant out of `watch.py`;
- editing `watch.py`, any test, any guard (`serving.mjs` included), the
  `justfile`, `dev/styleguide_audit.py`, or `lint.py`;
- changing `deploy` from single-file to directory, or touching autoreload.

If he rules extraction **in**, the implementing task (not this one) must ship,
in one coordinated commit: the 8 files + the `__file__`-relative loader + the
`deploy` directory snapshot + the `serving` `cpSync` + the autoreload watcher
extension + the styleguide-audit re-point. Splitting those invites a half-done
extraction that deploys blank.

If he rules extraction **out** (my lean), the throughput cost is owned by the
worktree path (`#264` Q3) and by sequencing — and `#368` (the Python split,
blocked on the CLI) remains the real modularisation question for a later day.

---

## Uncertainties (honest)

1. **The 7,142 vs 7,222 triple-quote gap.** I report 7,222 from `tokenize`; the
   brief's 7,142 is within method variance and the 75% conclusion holds. I did
   not chase the ~80-line gap; it does not affect any decision here. Settling
   it: agree on one tokeniser (Python `tokenize` is the natural choice).
2. **Whether the 8 `json.dumps` constants should ride `/data.json`** after
   extraction, making the JS fully static. Today only the *plugin* half rides
   `/data.json`; the core half is "baked in because it is a property of THIS
   FILE" (`watch.py` comment near `:7076`). Moving them is a one-paragraph
   change but changes the boot contract (a blank `/data.json` would break the
   page). I recommend keeping them as a generated preamble for v1; flagged
   because it is the one place extraction could *add* a request dependency.
3. **The styleguide-audit rework is unscoped.** I am confident the audit breaks
   (its filter targets constants that would leave watch.py) but I did not read
   `dev/styleguide_audit.py` end-to-end to cost the re-point. It is a real line
   item, not a hand-wave, but its size is unmeasured here.
4. **`server_class` misattribution.** I am confident it is 10 lines, not 6,798
   (verified by `ast` and by reading `:262–:271`). The brief asked me to inherit
   the measurement rather than re-derive it; I corrected this one because it
   misframes the structure as "one giant function" when it is "eight constants,"
   which changes how one pictures extraction. If the original measurement used a
   tool that attributes the constants' span to the nearest preceding `def`, that
   would explain the 6,798 — but `server_class` genuinely returns in 10 lines.

---

--- SUMMARY ---

- **Lean: do not extract now.** The mechanics are cheap (interpolation count
  **1**: only `/*DEV*/false` at `COMPONENTS_JS:1658`; the 8 `json.dumps` values
  are a concatenated preamble, not interpolated into the assets). What stops the
  recommendation is that client extraction **does not unblock the queue's
  hardest items** (`#331`, `#352` are Python parser work needing the separate
  `#368` split), **multiplies the registry-coupling class that caused today's
  actual damage**, and **the throughput win is captured more cheaply by a
  worktree** (`#264` Q3). If throughput is binding for him, the full-client
  extraction is mechanically ready.
- **Structure correction:** `server_class` is **10 lines** (`:262–:271`), not
  6,798; the largest `def` is `make_handler` at 434. The client source lives in
  **8 module-level constants** (6,719 lines: CSS 1,253, HTML 69, JS 5,397).
  Triple-quote total re-measured at **7,222** (brief's 7,142 holds within
  variance; ~75% conclusion survives).
- **Interpolation count = 1** inside the assets (`/*DEV*/false`, swapped once
  at `:8989`). Method: `tokenize` prefix check (0 f-strings), `grep
  (CONST)\.(replace|format)` (0), `grep /*DEV*/` (1), count `json.dumps` in the
  `PAGE` block (8, preamble not asset).
- **Q3 — what breaks (load-bearing, not hand-waving):** `just deploy` BREAKS
  (snapshots watch.py alone → blank page) and **must become a directory
  snapshot** (`git show rev:` per file; single-file-deploy convenience lost,
  committed-only property preserved); the `serving` guard BREAKS (the one guard
  that copies watch.py into a temp repo — needs one `cpSync`); `--autoreload`
  REGRESSES (watches only `__file__` mtime — asset edits won't hot-reload unless
  the watcher gains the 8 paths); the styleguide audit needs re-pointing (its
  filter targets the constants that would leave watch.py). The main `just
  guards` recipe SURVIVES unchanged if watch.py resolves `client/` by `__file__`.
- **Q4 — counter-argument:** extraction multiplies the registry-coupling damage
  class (`markrail`, artifact-staleness — `#264` Q5 item 5); that class bit
  today, file-contention didn't corrupt. Weighed: narrows scope, doesn't defeat
  extraction.
- **Q5 — do-nothing:** six tasks queue on watch.py — **#352, #351, #337, #331,
  #322, #295** (all `## Open`); `#371` was freed since filing, `#319` also
  needs it; `#354` inc1 was shelved (`a6c0732`). Cost is **throughput** (one
  watch.py lane at a time), not correctness. "Leave it" is defensible.
- **Q6 — smallest useful version:** CSS-only is a false economy (3 of 4 client
  parties this session touched JS). Extract the **full client (all 8)** — the
  four fixed costs (deploy/serving/autoreload/audit) are paid once regardless of
  file count. It prevents the client-vs-request-path serialization (shelved
  `#354` vs `#300`/`#385`/`#391`) but **none** of today's CPU/registry damage.
- **Not confident about:** the 7,142-vs-7,222 gap (doesn't affect the decision);
  whether the 8 boot constants should ride `/data.json`; the unscoped size of
  the styleguide-audit re-point; the `server_class` misattribution's origin.
