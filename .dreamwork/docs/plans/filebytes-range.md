# #354 — `/filebytes` must not buffer a whole file

**Tasks:** #354 (this plan); #355 noted as adjacent, not a defect today.
**Status:** design; **no implementation authority**. Nothing is changed in
`watch.py`, no test is added, no header is sent under this id.
**Date:** 2026-07-28 (line numbers and code claims re-grounded against the
tree as of this writing).
**Depends on:** #336 (landed — the endpoint and the security contract exist).
Related but out of scope for implementation here: #355 (`/reviewraw` text
cap), #275/#276 (LAN/public exposure that removes today's loopback mitigation).

---

## The recommendation (question 3 first, because it decides everything else)

His ledger entry recommended HTTP `Range` / `206 Partial Content` as "the only
cap that does not corrupt." That reasoning about **capping** is right — a hard
byte-count truncate would turn a PNG into mojibake's cousin, which is exactly
why `read_bytes` refused `read_text`'s idiom. But it is **incomplete as the fix
for the bug as stated**.

> **The primary fix is streaming the response from disk with a bounded read
> buffer, never materialising the whole file in the process. `Range` / `206` is
> a second, separate capability: useful for resumable downloads and for clients
> that ask, but not what an ordinary `<img src="/filebytes…">` sends. Ship
> streaming first; add single-range only after.**

| layer | what it does | does it fix a 1GB `<img>`? |
|---|---|---|
| stream full GET with fixed-size chunks | peak memory ≈ chunk size, not file size | **yes** |
| single-range `206` | client may fetch a slice | **no**, unless the client sends `Range` |
| hard cap on `read_bytes` | corrupt binary / break byte-identical proofs | deliberately rejected by #336 |

The ledger's "only cap that does not corrupt" still holds for *limits on what
is returned*. Streaming is not a cap; it is *how* an uncapped response is
emitted. Both are needed; streaming is the one that matches the common path.

**That is a valuable result, not a contradiction of the brief.** The ledger
recommendation survives as the correct *partial-response* design; it does not
survive as the *sole* fix for the 1GB buffer.

---

## 1. Exact current behaviour (grounded)

### Body production and send path

`/filebytes` is handled in `do_GET` at `watch.py:5190`. It resolves the
path, branches on `detect_file_kind`, and calls `_send_bytes`:

```
rel = parse_qs … p
full = resolve_confined(target, rel)          # :9042
if not full or detect_file_kind(full) != "image":
    self._send_bytes(full, rel, inline=False)
else:
    self._send_bytes(full, rel, inline=True)
```

`_send_bytes` (`watch.py:5139`):

1. `data = read_bytes(full)` at **:8968** — **entire file into one `bytes` object**.
2. `send_response(200)` plus headers from the **length of that object** (`:8971-8983`).
3. `self.wfile.write(data)` at **:8984** — one write of the whole buffer.

`read_bytes` (`watch.py:909`):

```python
with open(path, "rb") as f:
    return f.read()   # no limit; deliberate, commented at :7108-7112
```

Contrast `read_text` (`watch.py:804`): `f.read(limit)` with default
`limit=200_000` characters. That idiom is for **text** that can be truncated
honestly; the comment on `read_bytes` correctly refuses to transfer it.

### Where a 1GB file is held, and in how many copies

For a 1GB target-rooted file served once:

| place | size | notes |
|---|---|---|
| Python heap (`data` in `_send_bytes`) | ~1GB | one contiguous `bytes` from `read_bytes` |
| OS page cache | up to ~1GB | after `read(2)` |
| socket send buffer | small / kernel | not the problem |

There is **one deliberate full copy in the process** (the return value of
`read_bytes`). There is not a second Python copy from encoding — the body is
raw bytes, not UTF-8 (`_send` at `:8949-8955` encodes text; `_send_bytes` does
not). The response is not chunked: `Content-Length` is set to `len(data)`
before any write, so the handler already knows the size from the buffer, not
from `stat`.

`detect_file_kind` (`watch.py:974`) only reads **32 bytes** of head for
magic, then closes. That path is fine; it is not the leak.

### Client paths that hit `/filebytes`

- **Image view** (`buildFile`, `watch.py:2936-2956`):
  `<img class="fileimg …" src="/filebytes?p=…">` — a normal navigation GET
  with **no `Range` header**. Browsers do not send `Range` for ordinary image
  display; they may for media seeking (audio/video) or when a download manager
  implements speculative partial fetches (not something this page relies on).
- **Binary panel** (`watch.py:2962-2969`):
  `<a class="filebin-dl" href="…" download>` — full GET download, again no
  `Range` unless the browser or a download manager adds one.
- **Guards**: `dev/capture/fileimg.mjs` asserts a network hit to `/filebytes`
  for the right path and that the `<img>` draws; it does not send `Range`
  (confirmed: no `Range` string in that guard).

So for the path that motivated #336 (evidence PNGs in `/file`), the request is
a full GET. **A pure Range implementation leaves that path buffering the whole
file.**

### Confinement — the claim is true, and here is the check

Every file-serving route is supposed to go through `resolve_confined`
(`watch.py:4606`):

```python
def resolve_confined(target, rel):
    if not rel or rel.startswith(("/", "~")):
        return None
    full = os.path.realpath(os.path.join(target, rel))
    root = os.path.realpath(target)
    if full == root or not full.startswith(root + os.sep):
        return None
    return full
```

`/filebytes` calls it at **:9042** before any open of the body. The confinement
proof is behavioural, not "we imported the helper":
`test_filebytes_blocks_escape` (`test_watch.py:3347-3380`) hits `/filebytes`
with parent traversal, absolute path, tilde, empty, `.`, and a **symlink that
resolves outside the target**, expecting 404 each time. That is the named
production line for escape — `resolve_confined` returning `None` so
`_send_bytes` 404s at `:8966-8967` (or earlier when `full` is falsy).

**Honest limit of the mitigation:** confinement means "only files inside the
target," not "only small files." A dreamer (or a committed evidence dump) can
place a 1GB file under the target; the gate will serve it. Loopback-only
reduces *who* can ask; it does not reduce *what* is held when someone does.
`#275`/`#276` shrink that second mitigation, which is why #354 is filed as
robustness rather than as a hypothetical.

### Headers today (must stay or be extended carefully)

From `_send_bytes` `:8971-8983`:

| header | value |
|---|---|
| status | always `200` |
| `Content-Type` | allowlisted raster MIME **or** `application/octet-stream` |
| `Content-Length` | `len(data)` |
| `Content-Disposition` | `inline` **or** `attachment; filename="…"` |
| `X-Content-Type-Options` | `nosniff` |
| `Cache-Control` | `private, max-age=0, must-revalidate` |

No `Accept-Ranges`, no `Content-Range`, no `ETag`, no `Last-Modified`. No
HTTP `Range` parsing anywhere in `watch.py` (the string `Content-Range` does
not appear; the few `Range` hits are JS selection / scroll helpers, not HTTP).

### Security contract that must not move

Inherited from #336 / `watch-design.md` (file view image and binary surfaces):

- Inline MIME comes only from `INLINE_IMAGE_EXTS` / `_INLINE_IMAGE_MIME`
  (`watch.py:947`) and matching magic — **never** from the client.
- SVG/HTML/scriptable types stay out of the inline allowlist.
- Non-inline is always `application/octet-stream` + `attachment` + `nosniff`.
- `safe_attachment_filename` (`:7205-7215`) keeps `filename=` ASCII-safe.

Streaming and Range are **transport**. They must not change kind detection,
disposition, or MIME selection.

---

## 2. The `Range` design (smallest correct thing)

RFC 9110 §14. Spec below is implementable without a second design pass.
Four decisions are fixed rather than left to the implementer (each has a
defensible wrong answer):

### What to implement

| piece | decision |
|---|---|
| unit | `bytes` only |
| multi-range | **refused by ignoring** — if `Range` contains a comma (`bytes=0-9,20-29`), respond **`200` full body**, not `multipart/byteranges`. Explicit: multi-range is real work for no local benefit; do not "finish" it later without a design. |
| `Accept-Ranges` | always `bytes` on successful `/filebytes` responses (200 and 206), **once 206 exists** — do not advertise before Range works |
| satisfiable single range | `206 Partial Content`, body = that slice only |
| `Content-Range` | `bytes <first>-<last>/<complete>` on 206 |
| `Content-Length` | length of the **selected representation** (the slice on 206, full size on 200) |
| unsatisfiable (start past EOF) | **`416 Range Not Satisfiable`** with `Content-Range: bytes */<complete>` and **empty body** |
| *syntactically invalid* `Range` | **ignored** — serve full `200` (RFC 9110). Deliberately **not** an error. This is the rule an implementer is most likely to get backwards. |
| open-ended | `bytes=N-` → from N to end — **works** |
| suffix | `bytes=-N` → last N bytes — **works** |
| empty file | size 0: `bytes=0-0` is unsatisfiable → 416; no Range → 200 empty |
| `If-Range` / `ETag` / `Last-Modified` | **leave out** |
| `If-Match` / conditional GET | **leave out** |

### Parsing rules (concrete)

1. Read `Range` header. Absent → full 200 stream.
2. If value does not start with `bytes=` (case-sensitive unit token per common
   practice; be liberal with surrounding whitespace) → ignore, full 200.
3. If multiple ranges (`,`) → ignore, full 200.
4. Parse one `first-last` / `first-` / `-suffix`.
5. Against `size = os.path.getsize(full)` (or `stat` once):
   - suffix: `first = max(0, size - suffix)`, `last = size - 1`
   - open end: `last = size - 1`
   - if `first >= size` (or size 0 with a non-empty range request) → 416
   - clamp `last = min(last, size - 1)` when last was given past EOF (RFC:
     satisfiable ranges may be truncated to the representation)
   - if after clamp `last < first` → 416
6. Seek to `first`, read/write `(last - first + 1)` bytes **in chunks** — never
   `f.read()` the slice into one buffer when the slice itself could be huge.

**Production home:** pure helpers, not buried in `do_GET`:

- `parse_byte_range(header, size) -> None | ("full",) | ("partial", first, last) | ("unsat",)`
  (or a small named result the handler switches on)

Pure + unit-tested matches `resolve_confined` / `detect_file_kind` style.

### What is explicitly left out (and why)

| left out | why |
|---|---|
| multi-range / `multipart/byteranges` | browsers almost never need it for `<img>`/download; response framing is easy to get wrong; security surface for a stdlib dashboard |
| `If-Range` | no validators today; without `ETag`/`Last-Modified` it cannot fire correctly |
| `ETag` / weak validators | separate feature; interacts with `Cache-Control` and autoreload |
| `Last-Modified` + `If-Modified-Since` | same; nice later, not required for memory safety |
| `sendfile(2)` / zero-copy | platform-specific; optimisation after streaming is correct |
| hard maximum representation size | re-introduces the "cap corrupts" problem for intentional large assets; confinement + streaming is the chosen pair |
| applying Range to `/filedata` or `/reviewraw` | different contracts (JSON text / HTML text); #355 owns reviewraw's cap shape |

### Interaction with existing headers

- **Disposition / MIME / nosniff:** unchanged on 206 and 200.
- **`Cache-Control`:** still sent on 206 (same policy as full body).
- **`Accept-Ranges: bytes`:** **new**, on 200 and 206 for `/filebytes` only
  (not on the app shell or JSON routes).

---

## 3. Streaming — the incomplete ledger recommendation, stated plainly

**One sentence answer to the brief's question 3:**
Range alone does **not** fix the 1GB buffer for the common `<img>` / full
download path; the real fix is chunked streaming from disk with a bounded
buffer, with single-range support as a second capability.

### Why

1. `buildFile` sets `img.src = '/filebytes?p=…'` (`:2939, :2954`) with no client Range logic.
2. Chromium/Firefox/WebKit issue a normal GET for that URL.
3. A server that only implements Range still does `f.read()` for that GET at `:7115-7116`.

### Streaming design (primary increment)

After confinement + kind + headers:

1. `stat` the file once → `size`, and open `rb`.
2. Send headers with `Content-Length: size` (full) or slice length (206).
   Prefer known length over `Transfer-Encoding: chunked` — simpler clients,
   matches today's contract, and the tests assert lengths.
3. Loop: `chunk = f.read(CHUNK)` (recommend **64 KiB**, named constant
   `FILEBYTES_CHUNK = 65536`), `wfile.write(chunk)`, until done or client
   disconnects.
4. **Never** assign the whole file (or a multi-hundred-MB range) to a local
   `bytes` in this path.

`read_bytes` as a "return all bytes" helper becomes either:

- deleted from the hot path and kept only if something else needs it (today:
  only `_send_bytes` at `:8968` calls it — grep confirms), or
- reimplemented as a generator / left as a test-only footgun that production
  stops calling.

**Client disconnect:** `_expected_disconnect` already exists (`watch.py:4860`)
and `Handler.handle` already quiets pipe errors for the whole request
(`:8912-8925`, #299). Streaming large bodies makes mid-stream navigations more
visible; the existing wrapper should already cover `wfile.write` raises. Confirm
during implement; do not invent a second disconnect path.

### Does streaming change byte-identity?

No, if the loop writes the same bytes in order. Existing proofs compare
`served == png` and SHA-256 (`test_watch.py:3222-3225`); they remain the
acceptance for full GET.

### Bounded memory is the property; prove it without writing 1GB

See §5. Sparse files give a large `st_size` with tiny disk use on Linux.

---

## 4. What breaks, what must stay byte-identical

### Pytest (`test_watch.py`)

| test | lines | impact |
|---|---|---|
| `test_fileview_image_served_byte_identical` | 3184–3225 | full GET must stay **byte-identical** and longer than old text cap; still 200 |
| `test_fileview_non_image_binary_says_what_it_is` | 3227–3250 | attachment headers + body equality |
| `test_no_scriptable_type_can_reach_the_inline_mime_table` | 3252–3282 | table membership; untouched |
| `test_fileview_inline_allowlist_is_raster_only` | 3284–3326 | MIME/disposition only |
| `test_fileview_magic_bytes_gate_extension_claims` | 3328–3345 | same |
| `test_filebytes_blocks_escape` | 3347–3380 | confinement; untouched if gate stays first |
| `test_fileview_no_truncation_for_oversize_binary` | 3382–3399 | full length > `read_text` default; **must remain green** after streaming |

New tests (Range, streaming memory, 416) extend this module; they do not
replace the byte-identical proofs.

### Browser guards (do not edit in this design lane; list impact)

| guard | role | change needed when implementing? |
|---|---|---|
| `dev/capture/fileimg.mjs` | `<img>` + `/filebytes` fetch + motion | **should stay green** with streaming; no Range in client |
| `dev/capture/fileview.mjs` | markdown Rendered/Source | does not hit `/filebytes` for md |
| `dev/capture/filehead.mjs` | heading lockup | no bytes path |

Registered in `justfile` `DEFAULT_GUARDS` (includes `filehead fileview fileimg`).
If a guard ever asserted response headers exhaustively, it would need
`Accept-Ranges` tolerance; today fileimg cares about path + pixels + opacity,
not `Accept-Ranges`.

### Must stay byte-identical

- Full-body payload of a 200 response without `Range` vs on-disk file.
- Inline vs attachment decision matrix (SVG/HTML/spoof PNG).
- Escape/404 matrix.

### Must change (when authorised)

- `_send_bytes` implementation (stream).
- Optional: new pure range parser + 206/416 branches.
- `watch-design.md` § image/binary surfaces: document streaming + Range.
- Possibly delete or demote unbounded `read_bytes` from production.

### Cache-Control revisit (parked question from the ledger)

Today: `private, max-age=0, must-revalidate` (`watch.py:5139`).

| directive | why it was chosen | still right? |
|---|---|---|
| `private` | project files; not a public CDN cache | **yes**, stronger under LAN |
| `max-age=0` | avoid sticky stale image after edit / autoreload | **yes** for correctness over perf |
| `must-revalidate` | caches must check before reuse when stale | consistent with max-age=0 |

`--autoreload` re-execs on **server source** mtime, not on target file mtime;
the target image can change under a long-lived tab without a generation bump.
`/mtime` polling re-renders the **shell data**, not necessarily re-fetching an
`<img>` whose URL is unchanged — browsers may keep the image by URL regardless
of `Cache-Control` heuristics, but `max-age=0` is the honest signal.

**Recommendation:** keep the header for v1 of #354. A later change (e.g.
`ETag` from size+mtime, or cache-buster query on mtime) is a separate
increment; do not couple it to streaming. Uncertain only about whether he
wants snappier back/forward image paints enough to accept short `max-age`;
that is a product call, not a correctness one.

---

## 5. Red-first test plan

Repo rule: a check is not verification until it has been red; name the
production line that must change for it to fail; no scaffolding that stands
in front of the bug.

### The hollow outcome this section must pre-empt

The most likely wrong implementation **keeps every status code and header
correct**: it does `data = open(full, "rb").read()` (or keeps `read_bytes`),
then slices `data[first:last+1]` for 206 and writes the slice. Ranges look
perfect; the 1GB buffer is untouched.

**A check that only inspects the HTTP response cannot tell those two apart.**
Status, `Content-Range`, `Content-Length`, and body bytes are identical.

### Distinguishing stream-from-disk from read-all-then-slice

**Primary behavioural check (A2):** wrap the real body open at the production
seam — the open that `_send_bytes` uses for the **body**, not the 32-byte
`detect_file_kind` probe — and record every `read(n)` call:

| implementation | what the wrapper sees on a 200 MiB sparse GET |
|---|---|
| stream (correct) | many `read(≤65536)` (or similar chunk size); never one unbounded `read()` / `read()` with no size / `read()` ≥ file size |
| hollow (read all + slice) | one `read()` with no argument, or one `read(size)` / `read()` that returns the whole file, then slice |

How to instrument without a hollow mock:

- Prefer a **subclass of `io.BufferedReader` / custom file object** installed
  by patching `builtins.open` only when the path is the fixture file **and**
  the mode is `"rb"` **after** kind detection has already run — or patch
  `watch.read_bytes` **out of existence** and assert `_send_bytes` no longer
  calls it while a separate open-wrapper records chunk sizes.
- **Named production line that must break for red:** `_send_bytes` at
  `:8968` (`data = read_bytes(full)`) and/or `read_bytes` at `:7115-7116`
  (`return f.read()`). Restoring those two lines must turn A2 red.
- **Do not** patch `read_bytes` to return `b""` for the large path — that is
  the hollow pattern this repo already paid for (a fake that never reaches
  the branch under test). The real request must still return correct body
  bytes; the wrapper only *observes* read sizes.

**Companion structural check (optional, weaker alone):** assert
`_send_bytes`'s source no longer contains a call to `read_bytes`, or that
`read_bytes` is unused by the handler. Alone this can go hollow if someone
inlines `f.read()`; alone the read-size check can be gamed by one
`read(size)` of the whole file — **so A2 must fail on a single unbounded or
whole-file `read` as well as on many small ones being absent**.

**RSS check (tertiary, optional):** sparse file + peak RSS delta ≪ size on
Linux. Noisy under threads and page cache; never the sole proof.

**If an implementer cannot get a reliable read-size observation:** say so in
the implement PR and fall back to the dual of (structural: no
`read_bytes` / no argument-less `f.read` on the body path) + (RSS on sparse).
That is weaker but still better than header-only checks. **This plan does
name a check that can tell the two implementations apart (A2); it is not
honest to claim headers alone can.**

### A. Streaming (primary)

| # | behaviour | check | production line that must break for red |
|---|---|---|---|
| A1 | full GET still byte-identical | existing `test_fileview_image_served_byte_identical` | any truncate / wrong seek / dropped tail in the write loop |
| A2 | body path never issues one whole-file read | instrumented open / read-size log as above; assert max single read ≤ `FILEBYTES_CHUNK` (or a small multiple) **and** total bytes read == size | `_send_bytes` body read strategy (`:8968` today) and `read_bytes` (`:7115-7116`) |
| A3 | large logical size does not OOM / hang the suite | sparse file (below); GET completes; A2 still holds | same as A2 |
| A4 | no truncation reintroduced | existing `test_fileview_no_truncation_for_oversize_binary` | re-adding a byte cap on the stream |

**Sparse-file idiom (honest, no 1GB write):**

```python
path = os.path.join(target, "huge.bin")
with open(path, "wb") as f:
    f.write(b"\x00\x01")   # binary head for kind=binary
    f.truncate(200 * 1024 * 1024)  # 200 MiB logical; sparse on ext4/xfs/btrfs
```

Assert `os.path.getsize(path) == 200 << 20` and disk usage via
`os.stat(path).st_blocks * 512` is far smaller (**precondition**: if not
sparse, skip or fail the environment — assert the gap so the check cannot
pass on a full allocation nobody noticed).

**`RLIMIT_FSIZE`** (`test_watch.py:4376-4399`) is the idiom for **write**
failures (#370). It does not induce a large **read**. Prefer sparse files for
#354; mention RLIMIT only if testing that a write path is untouched.

### B. Range (second)

| # | behaviour | check | production line |
|---|---|---|---|
| B1 | `Range: bytes=0-3` on a known blob → 206, body `blob[:4]`, `Content-Range: bytes 0-3/<n>`, `Content-Length: 4` | new test | range parse + seek path |
| B2 | `bytes=N-` open-ended → correct tail | new | open-ended parse |
| B3 | `bytes=-3` suffix | new | suffix parse |
| B4 | start past EOF → 416, `Content-Range: bytes */size`, empty body | new | unsatisfiable branch |
| B5 | malformed `Range: crap` → **200 full body** (ignore) | new | ignore path; **precondition** body equals full file |
| B6 | multi-range `bytes=0-1,2-3` → **200 full** (documented ignore) | new | comma branch |
| B7 | no Range still 200 + `Accept-Ranges: bytes` | extend existing or new | header emission |
| B8 | Range on escape path still 404 before range logic | extend escape test | order: confine then range |
| B9 | Range does not change MIME/disposition matrix | spoof SVG + PNG control with Range | disposition after range |
| B10 | a large satisfiable range is still streamed (not read-all-then-slice) | A2-style instrumentation on a 206 of a sparse multi-MB range | seek + chunked write of the slice only |

Each B* test must use a **real HTTP request** through the existing
`_serve` / `_get_bytes` pattern (as existing filebytes tests do), not only
unit-test the parser — and **also** unit-test the pure parser for the matrix
of edge strings so the handler tests stay few.

**Red proof for B1:** implement streaming only; B1 fails (200 full body). Add
Range; B1 green. That sequencing is the staging.

**Red proof for hollow Range:** after B1 is green, reinstate
`data = read_bytes(full); body = data[first:last+1]` — B1–B9 stay green;
**B10 / A2 go red**. If B10 does not exist, the hollow Range implementation
ships.

### C. Guards

| # | behaviour | check |
|---|---|---|
| C1 | fileimg still PASS | run when implementing; no design-lane run required |
| C2 | if headers are snapshotted anywhere, allow `Accept-Ranges` | audit at implement time |

---

## 6. Cost and staging

Each increment is landable and verifiable alone. **No implementation under
this design id.**

### Increment 1 — Stream full responses (fixes the filed bug)

- Rewrite `_send_bytes` to stat + open + chunked write.
- Stop calling unbounded `read_bytes` from the handler.
- Keep all headers; **do not** advertise `Accept-Ranges` yet (would be a lie
  before 206 works).
- Tests: A1 green (existing), A2/A3 new and shown red against the old
  `read_bytes` path first.
- Docs: one paragraph in `watch-design.md`.

**Exit criterion:** a multi-hundred-MB sparse binary can be GETted without a
whole-file `read`; small PNG proofs still byte-identical.

### Increment 2 — Single-range only

- Pure `parse_byte_range`.
- 206 / 416 / ignore-malformed / ignore-multi.
- `Accept-Ranges: bytes` on 200 and 206.
- Tests B1–B10, each red-first where practical.
- Docs: Range contract in `watch-design.md`.

**Exit criterion:** curl-style Range requests return correct slices; full GET
unchanged; hollow read-all-then-slice fails B10/A2.

### Increment 3 — Disconnect hygiene + Cache-Control decision (optional)

- Confirm #299's `_expected_disconnect` covers long streams (likely already).
- Only if he asks: short max-age or validators — **not** required to close #354.

### Explicit non-increments

- Multi-range.
- ETag / If-Range.
- Client-side JS that sends Range for images (unnecessary if streaming works).
- Changing confinement or the raster allowlist.
- Raising or removing `/reviewraw`'s cap (#355; see §7).

### Rough size

Increment 1: ~1–2 hours focused, mostly tests.
Increment 2: ~2–3 hours including the parse matrix.
No port / no `just guards` required for unit+HTTP tests; browser guard is
confirmation, not the design gate.

---

## 7. #355 — the same question one door along (`/reviewraw`)

A plan that fixes `/filebytes` and leaves `/reviewraw` unexamined would be
read as an oversight. Measured so nobody has to guess:

### What is there today

```python
# watch.py:5312 (the /reviewraw handler)
name = parse_qs … p
full = resolve_confined(target, os.path.join(".dreamwork", "review", name))
    if name and "/" not in name else None
text = read_text(full, limit=2_000_000) if full else None   # :9055
…
self._send(text, "text/html")   # :9059 — encodes whole string again in _send
```

- Cap is **2_000_000 characters** via `read_text` (`:7099-7104` with
  explicit limit).
- Body is a full Python `str`, then `_send` (`:8949-8955`) encodes the whole
  thing to UTF-8 again — so a near-cap artifact is ~2MB of text **plus** ~2MB
  of encoded bytes transiently.
- Confinement: basename only (`"/" not in name`) **and**
  `resolve_confined` under `.dreamwork/review/` — stronger path shape than
  `/filebytes`. Proven by `test_reviewraw_blocks_escape_and_missing`
  (`test_watch.py:3418-3426`).

### Is it a defect today?

**No.** Re-measured against `.dreamwork/review/` (18 HTML artifacts):

| artifact | size |
|---|---|
| largest: `threaded-topic-chats-v2.html` | **84,987 B** |
| second: `367-strip-below-cliff.html` | **81,851 B** |
| cap | 2_000_000 chars |
| headroom on largest | **~23.5×** (4.2% of cap) |

The growth vector is demonstrated rather than hypothetical: the
second-largest artifact carries **one base64-embedded screenshot** (~55 KB of
base64 ≈ ~41 KB of image). Artifacts must be offline-clean, so every image is
inlined at ~1.33× its bytes — the cap is reached by embedded evidence at
roughly **~25 screenshots' worth** of that size, not by prose.

**Do not recommend raising or removing the cap.** Recommend noticing it.

### Two small recommendations (both for #355, not this task's implement)

1. **Make truncation loud.**
   Today, if `read_text` hits the limit mid-file, the iframe still gets
   `200` + `text/html` with a **silently truncated** document. That is the
   worst failure shape available: a blank or half-rendered frame with no
   error. Fix shape (when #355 is authorised): detect `len(text) == limit`
   **and** file longer than that (stat or peek), and either:
   - serve a small error HTML shell explaining the cap was hit (preferred for
     the iframe — something visible), or
   - `413` / `500` with a plain message.
   Name the production line: `read_text(full, limit=2_000_000)` at `:9055`
   and the lack of a post-read length check. A test that only GETs a small
   artifact cannot see this — the red fixture must be a file whose character
   length exceeds the limit (can be sparse-ish or a generated string of
   `limit + 1` ASCII chars written once; not 1GB).

2. **Record the Content-Type trust story in a comment beside the code.**
   `/filebytes` refuses client- or extension-reflected MIME for XSS reasons
   (#336). `/reviewraw` serves `text/html` deliberately (`:9059`) because the
   artifact is a **self-contained HTML document the loop itself built**,
   confined to `.dreamwork/review/` with a basename-only `p=`. That trust
   story genuinely differs from an arbitrary target file. The next reader
   will want to "align" the two endpoints; a three-line comment at `:9047`
   prevents that "fix." **No behaviour change** — documentation of an
   intentional asymmetry.

### What #355 is not

- Not "stream `/reviewraw` like `/filebytes`" as the first move — the body is
  text HTML for an iframe; the urgent bug is silent truncation, not a 1GB
  buffer (there is a cap).
- Not raising the cap so more screenshots fit silently.
- Not applying `Range` to HTML artifacts.

---

## What approval of this does not authorise

Nothing is built. Approving accepts:

1. Streaming-with-bounded-buffer is the **primary** fix for #354.
2. Single-range `206` is the **secondary** capability; multi-range and
   validators are out; invalid Range → 200; unsatisfiable → 416 with
   `bytes */size`.
3. The #336 security contract (MIME, disposition, magic, confinement) does
   not move.
4. `Cache-Control` stays as today unless a separate ruling says otherwise.
5. #355 is "notice and make truncation loud," not "raise the cap."

It does **not** authorise editing `watch.py`, adding tests, changing guards,
or shipping any header behaviour.

---

## Uncertainties (honest)

1. **Read-size instrumentation flake / inventiveness:** A2 is the load-bearing
   anti-hollow check. If patching `open` races with `detect_file_kind`'s
   32-byte read, the implementer must filter by call order or by "reads after
   headers are sent." Not confident the first attempt at the wrapper will be
   clean; confident the *requirement* (distinguish whole-file read from
   chunked) is right. Settling it: write A2 red against current code first —
   current code does one unbounded `f.read()`, so A2 must fail today.
2. **Whether any browser we care about sends `Range` for `<img>`** — not
   measured in this pass against live Chromium network logs. Confidence is
   high from platform behaviour, not from a capture in this repo. Settling it:
   one DevTools/Playwright request log on `fileimg` for `pic.png`. If a browser
   *does* send Range, increment 2 becomes more valuable but increment 1 remains
   necessary for ignore/full paths.
3. **Suffix ranges on size 0 / interactive edge cases** — specified above from
   RFC reading; implementer should pin with B-matrix rather than invent at
   coding time.
4. **`Transfer-Encoding: chunked` vs known `Content-Length`** — recommend
   Content-Length from `stat` always when the file is a regular file. Not
   re-verified against every proxy; this server is loopback/stdlib and has no
   reverse-proxy requirement today.

## Out of scope findings (for the coordinator to file if useful)

- **#355** as expanded in §7 — loud truncation + comment; not a defect today
  at 4.2% of cap.
- **`read_bytes` is a loaded footgun** while it exists: any future caller that
  reuses it re-opens #354. Increment 1 should remove or sharply document it.
- No second copy of confinement logic was found; `/filebytes` does call
  `resolve_confined` (the test that proves it is load-bearing).
- `_send` (`:8949-8955`) always materialises the full UTF-8 body for text
  routes; that is fine for capped `read_text` paths and is not #354.

--- SUMMARY ---

- **Primary fix is streaming, not Range.** A 1GB file is held today as one
  full `bytes` from `read_bytes` (`watch.py:909`) inside `_send_bytes`
  (`:8968-8984`). The common client is `<img src="/filebytes…">`
  (`buildFile` `:2939-2956`) with **no `Range` header**, so Range alone leaves
  that path buffering the whole file. The ledger recommendation is incomplete
  in that sense; Range remains the right *non-corrupting* form of partial
  response, but as a **second** capability after chunked streaming.
- **Current path, grounded:** `do_GET` `/filebytes` (`:9032-9046`) →
  `resolve_confined` (`:8737-8749`, call at `:9042`) → `detect_file_kind`
  (32-byte magic, `:7167-7186`) → `_send_bytes` → unbounded `f.read()` →
  single `wfile.write`. Confinement is real (`test_filebytes_blocks_escape`
  `:3347-3380`); it does not bound size. One process copy; no UTF-8 second
  copy on the byte path.
- **Range design (smallest correct):** single `bytes` range only; `206` +
  `Content-Range` + slice `Content-Length`; **`416` with `bytes */size`** when
  unsatisfiable; **syntactically invalid and multi-range ignored → full `200`**
  (RFC, and multi-range is refused without `multipart/byteranges`); suffix and
  open-ended both work; `Accept-Ranges: bytes` only once 206 exists; **no**
  multi-range, If-Range, ETag, or Last-Modified in this task.
- **Streaming design:** `stat` + open + 64KiB read/write loop; prefer
  `Content-Length` from size; never materialise the file; keep MIME /
  disposition / nosniff / Cache-Control from #336. #299 disconnect handling
  already wraps the handler (`:8912-8925`).
- **Hollow-implementation guard:** headers-only tests **cannot** tell
  read-all-then-slice from real streaming. A2 (and B10 for large ranges) must
  observe per-`read` sizes at the body open and fail if a single whole-file
  read occurs; restoring `:8968` / `:7115-7116` is the named red.
- **Cache-Control:** keep `private, max-age=0, must-revalidate` (`:8982`) for
  v1; revisit only as a separate product call.
- **What must stay byte-identical:** full GET body vs disk
  (`test_fileview_image_served_byte_identical` `:3184-3225`); allowlist and
  attachment matrix; escape 404s. Guards `fileimg` / `fileview` / `filehead`
  should stay green without client changes.
- **Staging:** (1) stream full GET, (2) single-range 206/416 + Accept-Ranges,
  (3) optional disconnect/cache. Design only — no `watch.py` edits authorised.
- **#355 (`/reviewraw`):** largest artifact 84,987 B — **4.2% of the 2M cap,
  not a defect today**. Growth vector is base64 screenshots (~25 of that size
  hit the cap). Recommend **loud truncation** (silent mid-file cut is the
  worst failure shape) and a **comment** that `text/html` is intentional for
  loop-built artifacts under `.dreamwork/review/` — do **not** raise or remove
  the cap; do not conflate with `/filebytes` MIME rules.
- **Uncertain:** first-pass open-wrapper cleanliness for A2 (requirement solid);
  whether any target browser sends Range for images (high confidence no, not
  captured here).
