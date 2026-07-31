# #750 check design — hash the parsed value tree, not JSON text

## Decision — `struct-sha256-v1` (option B, with its hidden premise exposed)

Change `check` to a SHA-256 over a small, language-neutral **structural
preimage** of the document as the browser understands it after `JSON.parse`.
Keep the existing exclusion of top-level `generated`. Prefix the wire value
with its algorithm, for example `s1:<64 lowercase hex digits>`. The browser
must build the preimage for the reconstructed document, compare its bytes with
Python's bytes in the cross-language harness **before Web Crypto is wired in**,
then hash it. Only a matching check may advance `lastDataV`; a mismatch or any
encoding/hash error takes #741's existing one-full-fetch-without-`since` path.

This is option B, but it does **not** “sidestep serialisation entirely.” SHA-256
accepts bytes. A structural digest must still specify how values become bytes;
otherwise “computed identically” is only the property being wished for. The
reason to choose B is narrower and stronger: its byte grammar can encode the
six value kinds plus finite IEEE-754 numbers directly, without making Python
reimplement JavaScript's decimal number formatting, JSON escaping and
whitespace. It changes what `check` means without changing the `/data.json`
document representation.

Do not implement an encoder in this design task. The first future landing is
the parity proof described below; no browser acceptance path should exist
until that proof is red-capable and green.

## Context and current evidence

`watch.py:3934-3940` currently hashes the exact output of Python
`json.dumps(core, sort_keys=True, default=str)`. `watch.py:3999-4013` puts that
hex digest into the delta. `client/router.js:2508-2527` validates the requested
and held base, applies whole top-level changes and removals, then advances the
version without reading `check`.

#741 correctly closed the reachable stale-response path, but a base identity
is a causality proof, not a content proof. The existing production harness
already constructs a held document with the right version and an extra
`survivor` key; `applyDataResponse` accepts the delta, advances the version,
and leaves the wrong key in the reconstruction. This is the residual `check`
would catch.

The client also has two ordinary same-version mutation sites today:
`client/router.js:235` updates `data.tint` and `client/router.js:638-646`
updates `data.posture` after successful writes, without changing `lastDataV`.
The following server delta currently overwrites those same fields and
converges, so this is not a present bug. It does prove that “version matches”
cannot be promoted into “held bytes/values match” as an invariant of this
client. Removing `check` would leave future local mutations, an applier defect,
or an incomplete server delta silent when the version still matches.

The repo's one-renderer argument is relevant but not absolute. `DREAMWORK.md:
14-25` prefers extraction because a port makes every behaviour exist twice.
The current `dreamhub-design.md:193-210` explicitly narrows that to a live cost,
not a prohibition, after the React ruling. Here extraction across a Python
server and a dependency-free browser would require adding a runtime or making
one side trust the other, which defeats independent reconstruction checking.
The right response is therefore to minimize and bind the duplicated protocol,
not pretend there is only one implementation.

## IGC decision

**Context:** a local dashboard, a Python producer and classic browser client,
zero new dependency, #741's base/sequence recovery already shipped, and an
approximately 1.11 MiB current `collect()` document. The question is whether a
runtime content proof adds enough to justify its cross-language boundary.

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| A. Canonical JSON/wire encoding | ✘ | ✔ | ✔ | ✘ | ? | ✔ |
| B. Parsed-value structural preimage | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| C. Remove `check` | ✘ | ✘ | ✔ | ✔ | ✔ | ✔ |
| Naive sorted `JSON.stringify` | ✘ | ✔ | ✘ | ✔ | ✔ | ✘ |

- **G1:** rejects a wrong reconstructed parsed document before version advance.
- **G2:** never refetches merely because Python and JavaScript spell the same
  parsed value differently.
- **G3:** needs neither a dependency nor an ECMAScript number-to-decimal / JSON
  text serializer implemented in Python.
- **G4:** preserves current `collect()` field types and client-visible values.
- **G5:** can prove the cross-language boundary red before any Web Crypto call.

### Decisive errors

**A — canonical JSON/wire encoding fails G3.** Strict RFC 8785/JCS is not a
drop-in answer: its interoperable input model assumes IEEE-754 JSON numbers,
while the live document contains nanosecond integers beyond `2^53`. Turning
those fields into strings would change the wire schema. Normalising them to
the browser's `Number` value while retaining their existing wire spelling can
work, but then Python still has to reproduce ECMAScript's decimal rendering,
escaping and ordering. That is B's parsed-value semantics plus an unnecessary
text formatter. The extra formatter detects no additional reconstruction
error and is precisely where a false-refetch bug would live.

The two-descriptions objection therefore bites A as an engineering cost, not
as a metaphysical ban on protocols. Cross-language endpoints necessarily have
two implementations of their agreement. A chooses a larger agreement than the
goal requires. B keeps the duplicated surface to tags, lengths, UTF-8, key
order and binary64, then makes disagreement a test failure.

**C — removal fails G1.** #741's existing same-version-corruption case is the
counterexample: matching `base` and `lastDataV` coexist with a wrong held
document, and the browser accepts the reconstruction. The two live optimistic
mutation sites show that content-changing-without-version-changing is part of
the architecture, even though today's two instances converge. The residual
risk is not TCP bit rot; HTTP/JSON already makes that negligible. It is a
browser state or delta-composition error that preserves the version identity,
which is exactly the class the independent content check is for. CI exercises
the known applier, but cannot prove the state of a long-lived tab at runtime.

**Naive `JSON.stringify` fails G2 and G5.** Sorting keys does not recover
numeric type/spelling or exact integers already lost by `JSON.parse`, and it
does not align Python's spacing or Unicode escaping. It would turn every valid
delta containing one of those shapes into a full refetch and train maintainers
to ignore the guard. It must not land even temporarily.

G4 for A remains `?` rather than being waved green: a new canonical *wire*
encoding might preserve the public value types, but no concrete zero-dependency
proposal has shown that against the unsafe integers. Resolving it cannot save
A because G3 already refutes it.

## The actual `collect()` value domain

I inspected the production `collect()` return tree (`watch.py:3770-3907`) with
its question-signature writer disabled so the read-only probe did not mutate
the target. The live tree contained only JSON-native values:

| Python value | Observed shape | Consequence for `check` |
|---|---|---|
| `dict` | root and nested records; string keys | object tag, count, deterministic key order |
| `list` | paths, dreams, reviews, Q&A threads, git/burndown series | array tag, count, order preserved |
| `str` | paths, Markdown bodies, labels; two live strings contained non-BMP code points | valid Unicode scalar values encoded as UTF-8, with no normalization |
| `bool` | review flags and health/status facts | distinct true/false tags; handle before Python `int` |
| `None` | absent decisions, timestamps and optional status | distinct null tag |
| `int` | 135 values; 68 observed values exceeded `2^53` | encode the browser-parsed binary64 value, not Python's arbitrary-precision integer |
| `float` | 106 finite values: mtimes/created times and burndown facts | encode binary64 bits directly |

No non-JSON object reached the live tree, despite today's `default=str`
fallback. A future non-native value should make check construction fail closed,
not silently gain a string meaning. The measured core document was 1,166,969
Python-JSON bytes (1.113 MiB), so the browser work is a real full-tree pass but
not an unbounded theoretical object.

### Numbers: the information-loss cases

1. **Integral floats are live, not hypothetical.** The measured document had
   `burndown.median = 6179.0`. Python serialises that as `6179.0`; after parsing,
   JavaScript serialises the same `Number` as `6179`. The task's `1.0` versus
   `1` example is the minimal form. Both must map to binary64
   `40b8230000000000` for the live value (`3ff0000000000000` for `1`).

2. **Unsafe integers are live too.** `list_reviews()` emits `mtime_ns` and
   `created_ns` (`watch.py:3493-3501`). One observed value was
   `1785517576390236765`; `JSON.parse` rounds it to the binary64 value whose
   exact integer is `1785517576390236672` (bits `43b8c76ec690f4da`; JavaScript's
   shortest decimal display is `1785517576390236700`). A check over browser
   values must deliberately hash those binary64 bits. It verifies the document
   the browser can hold, not Python's lost low bits. This is also an explicit
   remaining limitation below.

3. **`-0` needs a rule.** None was observed in the live sample, but `float` is
   an existing producer type and Python can emit `-0.0`; JavaScript preserves
   negative zero through `JSON.parse` even though `JSON.stringify` writes `0`.
   Preserve the sign bit (`8000000000000000`) in the structural preimage.

4. **NaN and infinities must be rejected.** None was observed; all 106 live
   floats were finite. Python's default JSON writer nevertheless spells these
   non-standard tokens while `JSON.parse` rejects them. The structural builder
   must refuse them before a delta is emitted. A full response containing one
   is already unusable, so stringifying it for `check` would hide the producer
   defect rather than improve compatibility.

### Strings and containers

Python's current bytes escape `café ☕ 😀` as ASCII, including a UTF-16
surrogate pair for the emoji; straightforward JavaScript emits the characters.
The live tree did contain non-BMP text and no lone surrogate. Encode valid
Unicode scalar values as UTF-8, reject lone surrogates on both sides (do not let
`TextEncoder` silently replace one), and do not NFC/NFD-normalize: normalization
would make distinct parsed strings hash alike.

Recursive key sorting, whitespace and integer-like JavaScript enumeration are
not semantic document properties. Domain tags and explicit lengths make them
irrelevant and keep `null`, `false`, `0`, `""`, `[]` and `{}` collision-distinct.
Python booleans require the bool check before the integer check because `bool`
is an `int` subclass.

## Proposed `struct-sha256-v1` preimage

The specification should be this small and no larger. `u64` is unsigned
big-endian; string length is the UTF-8 byte length; number is an IEEE-754
binary64 big-endian payload.

| Value | Preimage |
|---|---|
| `null` | `00` |
| `false` / `true` | `01` / `02` |
| number | `03 || float64` |
| string | `04 || u64(length) || utf8` |
| array | `05 || u64(count) || value…` in array order |
| object | `06 || u64(count) || key-string || value…`, pairs sorted by the key's UTF-8 bytes |

Python `int` and `float` values are converted to the same binary64 value that
the emitted JSON token produces in JavaScript. Booleans are dispatched first;
non-finite and overflow values are errors. `-0.0` retains its sign. Object keys
must be strings. Cycles and non-native values are errors (the normal JSON wire
already cannot carry them).

Hash exactly one preimage with exactly one Web Crypto call per candidate delta.
Do not hash subtree-by-subtree: that adds asynchronous crypto calls without
removing the byte grammar. An encoder may append chunks internally, but the
parity seam exposes the final bytes before hashing.

## The parity proof and red-proof

Extend the existing path rather than creating a browser or a third applier:

1. Add raw JSON-literal golden vectors for every observed kind and the edge
   shapes above. Each vector carries the expected preimage hex (or `reject`).
   Include the actual `6179.0`, actual unsafe `created_ns`, `-0.0`, non-BMP
   text, nested/sorted objects, booleans/null, empty containers, and rejection
   vectors for NaN/infinity and lone surrogates.
2. `test_watch.py` feeds the existing Python-derived delta envelopes plus those
   vectors to `dev/data-delta.test.mjs`. Python and the production JS byte
   builder must each equal the fixed golden bytes, and must equal each other.
   The VM context for this phase supplies no `crypto`; an accidental Web Crypto
   call makes the parity phase fail.
3. Only after byte parity is green, hash those bytes and bind the current
   same-version-corruption and invalid-check cases to the existing recovery:
   one full request without `since`, no version advance, no corrupt document
   committed.
4. Because Web Crypto introduces an `await`, check `dataResponseSequence`
   **again after the digest completes**. Otherwise an older response could win
   during hashing and reopen the race #741 just closed.

### Direction 1 — demonstrate today's gap

A direct probe hashed Python's current sorted JSON and a recursively-key-sorted
`JSON.stringify` of the same parsed value. It failed before any browser hash
integration existed:

```text
Python bytes: {"n": 1.0}
JS bytes:     {"n":1}
Python SHA:   98f25079e96d74247de4854223c8c4175e719fac20753f81cfcaca00d59e9d23
JS SHA:       2bfd14f43d17fc7cea24e0917a8879b4b2f880b8baeec1b9d90fbaad655e71bd
equal: false
```

The actual review-row shape disagreed too: Python retained
`created_ns: 1785517576390236765` and ASCII-escaped the Unicode label; the JS
side held `created_ns: 1785517576390236700` and emitted the characters. The
hashes were respectively
`8891792512df2c473d0b265935cf4eac644fca7b1b71ab6280ac06e955d86100`
and
`c62f89cabadf80427cbab7882d466c0078729c1951e4916b3728dc88057dc17a`.

The existing Node VM harness supplies the complementary behavioural proof:
with a matching base version but corrupt held content, production
`applyDataResponse` advances successfully while its output is not the Python
target. A content guard has something concrete to reject.

For the future implementation's direction-1 red-proof, reverse the JS float
endianness (or omit the object tag) and require the parity test to fail with the
vector label, path and differing hex **before SHA-256**. Separately disable the
runtime comparison and require the same-version-corruption case to fail on
“wrong reconstruction committed / version advanced,” not merely a red count.

### Direction 2 — the false-green to keep named

Two implementations can share the same wrong rule. Byte parity alone would be
green if both normalized a lone surrogate to U+FFFD, both forgot to distinguish
boolean from number, or both chose the wrong unsafe-integer rounding. Fixed
golden bytes close those named cases; they do not prove the grammar for every
future producer value. The type-domain rejection and golden-vector corpus are
therefore part of the proof, not optional test decoration.

## Cost in this repo

Estimated gross addition, before normal review compression:

| Surface | Estimated lines |
|---|---:|
| Python structural byte builder and validation | 35–50 |
| production JavaScript byte builder plus async check/recovery wiring | 65–85 |
| golden vectors and Python/Node parity + recovery assertions | 70–100 |
| `file-formats.md` contract update | 15–25 |
| **Total** | **185–260** |

Production logic is about 100–135 of those lines; the rest buys the boundary
proof and born-red cases. New dependencies: **none**. Python already has
`hashlib` and `struct`; the browser has `TextEncoder`, `DataView` and
`crypto.subtle`; Node's standard library covers the harness.

The current core is about 1.11 MiB, so an accepted delta adds one O(document)
tree walk, one roughly document-sized preimage and one Web Crypto digest. That
cost occurs only when a delta is returned, not on unchanged polls. It should be
measured in the implementation lane, but it does not justify an npm package or
a browser guard.

This can be red-proofed without a browser: the current `node:vm` seam executes
production functions and Python already derives the envelopes. A real browser
guard remains forbidden by load #666 and is unnecessary for byte parity.

## Build order

1. **Parity proof first.** Land the versioned grammar, production byte builders
   (still unused by the wire), fixed golden vectors, and Python/Node byte-parity
   tests. Make an injected endian/tag defect go red. No Web Crypto call and no
   `check` behaviour change yet.
2. Switch the server's `derived_check` to `s1:<hex>` and make server tests bind
   the parsed-value normalization and rejection domain. The old client ignores
   both old and new checks, so this intermediate commit does not add a false
   rejection path.
3. Wire browser verification before version advance, reuse #741's full-refetch
   recovery, and re-check response sequence after the async digest. Make the
   same-version-corruption and bad-check tests go from named false-greens to
   discriminating rejections.
4. In that same behavioural increment, update `file-formats.md`, rebuild the
   client bundle, and run the targeted Python/Node checks. The branch should be
   merged only with all four steps present; the commit order exists to make the
   proof reviewable, not to deploy a new half-state.

## What remains unverified under this recommendation

- The check verifies the browser's **parsed projection**, not exact Python
  values. Low bits of current nanosecond integers are already lost in the JSON
  wire and remain unverified; changing those fields to strings is a separate
  schema decision.
- Full responses remain the source of truth and are not self-checked. So do the
  initial full fetch and the full recovery fetch; `check` proves only delta
  reconstruction relative to the held base.
- The unchanged sentinel still trusts version identity. It does not re-hash the
  held document on every poll.
- Golden vectors cannot prove that two implementations will never share an
  unimagined bug for a future value. The explicit accepted type domain makes a
  new type fail closed, but additions to that domain require new vectors.
- This does not prove that `collect()` describes the right project state, that
  `watched_mtime` invalidates every producer input, or that SHA-256 is
  collision-free. Those are outside reconstruction equivalence.
- The design measured current document size but did not measure worst-case
  browser latency or allocation. That performance remains owed in the
  implementation lane.
- No real browser/Web Crypto integration was run here. The Node seam can bind
  bytes, async sequencing and recovery, but actual browser availability/error
  behaviour remains unverified until implementation (where hash failure must
  fail safe to a full fetch).

## Verification performed for this recommendation

- `python3 -m pytest -q test_watch.py -k delta`: **7 passed, 477 deselected,
  6 subtests passed**. This invokes `node --test dev/data-delta.test.mjs`
  through the Python-derived-envelope harness and retains the two deliberately
  named base-only false-greens.
- Read-only live `collect()` type/size probes, with its question-signature
  writer disabled: seven JSON-native shapes only, 241 numbers, 68 unsafe
  integers, 106 finite floats, two strings containing non-BMP code points, no
  lone surrogate, no negative zero, no non-finite number, 1.113 MiB core.
- Direct Python-versus-straightforward-JS hash probe: both cases above differed
  on exact bytes and digest.
- No browser, server or port was started. In particular, neither `:35110` nor
  `:35113` was touched.

## DOGFOOD REPORT

Two pieces of lane friction were material:

1. The cited `dreamhub-design.md` is absent from this worktree's tracked
   `.dreamwork/docs/`; the current copy was only discoverable at the main skill
   checkout root. Its former one-renderer ruling has also been explicitly
   relaxed in the file itself. A design brief relying on it should give the
   absolute path or quote the relied-on current paragraph, as the ledger rule
   already requires for issues.
2. `collect()` is not a read-only inspector: it calls
   `track_question_updates`, which can write the signature store and emit an
   event. Measuring the actual output domain for this read-only design required
   replacing that call with a no-op in-process. A documented read-only/schema
   probe would make future wire-format investigations safer; none was added
   here because it is outside #750.

The existing Python-to-Node harness otherwise did exactly what the brief said:
it exposed the production browser applier without a browser, dependency or
port, and its already-named same-base false-green made option C decidable.
