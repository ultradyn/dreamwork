# #354 — `/filebytes` must not buffer a whole file

**Tasks:** #354
**Status:** design; **no implementation authority**. Nothing is changed in
`watch.py`, no test is added, no header is sent under this id.
**Date:** 2026-07-28
**Depends on:** #336 (landed — the endpoint and the security contract exist).
Related but out of scope: #355 (`/reviewraw` text cap), #275/#276 (LAN/public
exposure that removes today's loopback mitigation).

---

## The recommendation

His ledger entry recommended HTTP `Range` / `206 Partial Content` as "the only
cap that does not corrupt." That reasoning about **capping** is right — a
hard byte-count truncate would turn a PNG into mojibake's cousin. But it is
**incomplete as the fix for the bug as stated**, and saying so is the point of
this plan.

> **The primary fix is streaming the response from disk with a bounded read
> buffer, never materialising the whole file in the process. `Range` /
> `206` is a second, separate capability: useful for resumable downloads and
> for clients that ask, but not what an ordinary `<img src="/filebytes…">`
> sends. Ship streaming first; add single-range only after.**

Concretely:

| layer | what it does | does it fix a 1GB `<img>`? |
|---|---|---|
| stream full GET with fixed-size chunks | peak memory ≈ chunk size, not file size | **yes** |
| single-range `206` | client may fetch a slice | **no**, unless the client sends `Range` |
| hard cap on `read_bytes` | corrupt binary / break byte-identical proofs | deliberately rejected by #336 |

The ledger's "only cap that does not corrupt" still holds for *limits on what
is returned*. Streaming is not a cap; it is *how* an uncapped response is
emitted. Both are needed; streaming is the one that matches the common path.

---

## 1. Exact current behaviour (grounded)

### Body production and send path

`/filebytes` is handled in `do_GET` at `watch.py:8677-8691`. It resolves the
path, branches on `detect_file_kind`, and calls `_send_bytes`:

```
rel = parse_qs … p
full = resolve_confined(target, rel)          # :8688
if not full or detect_file_kind(full) != "image":
    self._send_bytes(full, rel, inline=False)
else:
    self._send_bytes(full, rel, inline=True)
```

`_send_bytes` (`watch.py:8602-8629`):

1. `data = read_bytes(full)` — **entire file into one `bytes` object**.
2. `send_response(200)` plus headers from the file **length of that object**.
3. `self.wfile.write(data)` — one write of the whole buffer.

`read_bytes` (`watch.py:6752-6762`):

```python
with open(path, "rb") as f:
    return f.read()   # no limit; deliberate, commented
```

Contrast `read_text` (`watch.py:6744-6749`): `f.read(limit)` with default
`limit=200_000` characters. That idiom is for **text** that can be truncated
honestly; the comment on `read_bytes` correctly refuses to transfer it.

### Where a 1GB file is held, and in how many copies

For a 1GB target-rooted file served once:

| place | size | notes |
|---|---|---|
| Python heap (`data` in `_send_bytes`) | ~1GB | one contiguous `bytes` |
| OS page cache | up to ~1GB | after `read(2)` |
| socket send buffer | small / kernel | not the problem |

There is **one deliberate full copy in the process** (the return value of
`read_bytes`). There is not a second Python copy from encoding — the body is
raw bytes, not UTF-8. The response is not chunked: `Content-Length` is set to
`len(data)` before any write, so the handler already knows the size from the
buffer, not from `stat`.

`detect_file_kind` (`watch.py:6812-6831`) only reads **32 bytes** of head for
magic, then closes. That path is fine; it is not the leak.

### Client paths that hit `/filebytes`

- **Image view** (`buildFile`, `watch.py:2816-2833`):  
  `<img class="fileimg …" src="/filebytes?p=…">` — a normal navigation GET
  with **no `Range` header**. Browsers do not send `Range` for ordinary image
  display; they may for media seeking (audio/video) or when a user agent
  implements speculative partial fetches (not something this page relies on).
- **Binary panel** (`watch.py:2845`):  
  `<a class="filebin-dl" href="…" download>` — full GET download, again no
  `Range` unless the browser or a download manager adds one.
- **Guards**: `dev/capture/fileimg.mjs` asserts an XHR/network hit to
  `/filebytes` for the right path and that the `<img>` draws; it does not send
  `Range`.

So for the path that motivated #336 (evidence PNGs in `/file`), the request is
a full GET. **A pure Range implementation leaves that path buffering the whole
file.**

### Confinement — the claim is true, and here is the check

Every file-serving route is supposed to go through `resolve_confined`
(`watch.py:8382-8394`):

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

`/filebytes` calls it at `:8688` before any open of the body. The confinement
proof is behavioural, not "we imported the helper":
`test_filebytes_blocks_escape` (`test_watch.py:3080-3113`) hits `/filebytes`
with parent traversal, absolute path, tilde, empty, `.`, and a **symlink that
resolves outside the target**, expecting 404 each time. That is the named
production line for escape — `resolve_confined` returning `None` so
`_send_bytes` 404s at `:8611-8612`.

**Honest limit of the mitigation:** confinement means "only files inside the
target," not "only small files." A dreamer (or a committed evidence dump) can
place a 1GB file under the target; the gate will serve it. Loopback-only
reduces *who* can ask; it does not reduce *what* is held when someone does.
`#275`/`#276` (and the trusted-LAN mode already designed under #233) shrink
that second mitigation, which is why #354 is filed as robustness rather than
as a hypothetical.

### Headers today (must stay or be extended carefully)

From `_send_bytes` `:8616-8628`:

| header | value |
|---|---|
| status | always `200` |
| `Content-Type` | allowlisted raster MIME **or** `application/octet-stream` |
| `Content-Length` | `len(data)` |
| `Content-Disposition` | `inline` **or** `attachment; filename="…"` |
| `X-Content-Type-Options` | `nosniff` |
| `Cache-Control` | `private, max-age=0, must-revalidate` |

No `Accept-Ranges`, no `Content-Range`, no `ETag`, no `Last-Modified`. No
`Range` parsing anywhere in `watch.py` (confirmed: no `206`, no
`Content-Range` string).

### Security contract that must not move

Inherited from #336 / `watch-design.md` "The file view's image and binary
surfaces":

- Inline MIME comes only from `INLINE_IMAGE_EXTS` / `_INLINE_IMAGE_MIME` and
  matching magic — **never** from the client.
- SVG/HTML/scriptable types stay out of the inline allowlist.
- Non-inline is always `application/octet-stream` + `attachment` + `nosniff`.
- `safe_attachment_filename` keeps `filename=` ASCII-safe.

Streaming and Range are **transport**. They must not change kind detection,
disposition, or MIME selection.

---

## 2. The `Range` design (smallest correct thing)

RFC 9110 §14. Spec below is implementable without a second design pass.

### What to implement

| piece | decision |
|---|---|
| unit | `bytes` only |
| multi-range | **no** — if `Range` contains a comma (multi-range), respond `200` with the full stream (or `416` only if you prefer strict; **recommend ignore → 200 full**, same as many simple servers) |
| `Accept-Ranges` | always `bytes` on successful `/filebytes` responses (200 and 206) |
| satisfiable single range | `206 Partial Content`, body = that slice only |
| `Content-Range` | `bytes <first>-<last>/<complete>` on 206 |
| `Content-Length` | length of the **selected representation** (the slice on 206, full size on 200) |
| unsatisfiable | `416 Range Not Satisfiable` with `Content-Range: bytes */<complete>` and **empty body** |
| malformed `Range` | **ignore** the header; serve full `200` (RFC allows; avoids turning typos into hard failures for odd clients) |
| open-ended | `bytes=N-` → from N to end; `bytes=-N` → last N bytes (suffix) — both are single-range forms and should work |
| empty file | size 0: `bytes=0-0` is unsatisfiable → 416; no Range → 200 empty |
| `If-Range` / `ETag` / `Last-Modified` | **leave out** (see below) |
| `If-Match` / conditional GET | **leave out** |

### Parsing rules (concrete)

1. Read `Range` header. Absent → full 200 stream.
2. If value does not start with `bytes=` (case-sensitive unit token per
   common practice; be liberal with surrounding whitespace) → ignore, full 200.
3. If multiple ranges (`,`) → ignore, full 200. *Stated so nobody "finishes"
   multi-range later without a design.*
4. Parse one `first-last` / `first-` / `-suffix`.
5. Against `size = os.path.getsize(full)` (or `stat` once):
   - suffix: `first = max(0, size - suffix)`, `last = size - 1`
   - open end: `last = size - 1`
   - if `first >= size` or `first < 0` or `last < first` after clamp → 416
   - clamp `last = min(last, size - 1)` when last was given past EOF (RFC:
     satisfiable ranges may be truncated to the representation)
6. Seek to `first`, read/write `(last - first + 1)` bytes in chunks.

**Production home:** pure helpers, not buried in `do_GET`:

- `parse_byte_range(header, size) -> None | ("full",) | ("partial", first, last) | ("unsat",)`
- or return a small named result the handler switches on.

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
| applying Range to `/filedata` or `/reviewraw` | different contracts (JSON text / HTML text); #355 owns reviewraw |

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

1. `buildFile` sets `img.src = '/filebytes?p=…'` with no client Range logic.
2. Chromium/Firefox/WebKit issue a normal GET for that URL.
3. A server that only implements Range still does `f.read()` for that GET.

### Streaming design (primary increment)

After confinement + kind + headers:

1. `stat` the file once → `size`, and open `rb`.
2. Send headers with `Content-Length: size` (full) or slice length (206).
   Prefer known length over `Transfer-Encoding: chunked` — simpler clients,
   matches today's contract, and the tests assert lengths.
3. Loop: `chunk = f.read(CHUNK)` (recommend **64 KiB**, named constant
   `FILEBYTES_CHUNK = 65536`), `wfile.write(chunk)`, until done or client
   disconnects.
4. **Never** assign the whole file to a local `bytes` in this path.

`read_bytes` as a "return all bytes" helper becomes either:

- deleted from the hot path and kept only if something else needs it (today:
  only `_send_bytes`), or
- reimplemented as a generator / left as a test-only footgun that production
  stops calling.

**Client disconnect:** `BrokenPipeError` / `ConnectionResetError` should not
traceback-spam (same class as #299 for `/mtime`). Stream loop catches and
returns quietly. Not unique to #354 but becomes more visible when files are
large and the user navigates away mid-load.

### Does streaming change byte-identity?

No, if the loop writes the same bytes in order. Existing proofs compare
`served == png` and SHA-256; they remain the acceptance for full GET.

### Bounded memory is the property; prove it without writing 1GB

See §5. Sparse files give a large `st_size` with tiny disk use on Linux; the
test asserts the process did not allocate ~size bytes of anonymous memory, or
— more simply and more robustly — that the production code path no longer
contains an unbounded `f.read()` of the body (structural) **and** that a
large sparse file request completes with peak RSS delta far below file size
(behavioural). Prefer the behavioural check at a real seam.

---

## 4. What breaks, what must stay byte-identical

### Pytest (`test_watch.py`)

| test | lines (approx) | impact |
|---|---|---|
| `test_fileview_image_served_byte_identical` | 2917–2958 | full GET must stay **byte-identical** and longer than old text cap; still 200 |
| `test_fileview_non_image_binary_says_what_it_is` | 2960–2983 | attachment headers + body equality |
| `test_fileview_inline_allowlist_is_raster_only` | 3017–3059 | MIME/disposition only |
| `test_fileview_magic_bytes_gate_extension_claims` | 3061–3078 | same |
| `test_filebytes_blocks_escape` | 3080–3113 | confinement; untouched if gate stays first |
| `test_fileview_no_truncation_for_oversize_binary` | 3115–3132 | full length > `read_text` default; **must remain green** after streaming |
| `test_no_scriptable_type_can_reach_the_inline_mime_table` | 2985–3015 | table membership; untouched |

New tests (Range, streaming memory, 416) extend this module; they do not
replace the byte-identical proofs.

### Browser guards (do not edit in this design lane; list impact)

| guard | role | change needed when implementing? |
|---|---|---|
| `dev/capture/fileimg.mjs` | `<img>` + `/filebytes` fetch + motion | **should stay green** with streaming; no Range in client |
| `dev/capture/fileview.mjs` | markdown Rendered/Source | does not hit `/filebytes` for md |
| `dev/capture/filehead.mjs` | heading lockup | no bytes path |

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

Today: `private, max-age=0, must-revalidate` (`:8627`).

| directive | why it was chosen | still right? |
|---|---|---|
| `private` | project files; not a public CDN cache | **yes**, stronger under LAN |
| `max-age=0` | avoid sticky stale image after edit / autoreload | **yes** for correctness over perf |
| `must-revalidate` | caches must check before reuse when stale | consistent with max-age=0 |

`--autoreload` re-execs on **server source** mtime (`watch-design.md`), not on
target file mtime; the target image can change under a long-lived tab without
a generation bump. `/mtime` polling re-renders the **shell data**, not
necessarily re-fetching an `<img>` whose URL is unchanged — browsers may keep
the image by URL regardless of `Cache-Control` heuristics, but `max-age=0`
is the honest signal.

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

### A. Streaming (primary)

| # | behaviour | check | production line that must break for red |
|---|---|---|---|
| A1 | full GET still byte-identical | existing `test_fileview_image_served_byte_identical` | any truncate / wrong seek / dropped tail in the write loop |
| A2 | no whole-file `read()` on the body path | **structural or behavioural** (pick one primary): (i) after change, `read_bytes` is unused by `_send_bytes` and a test opens a large sparse file and asserts peak RSS delta ≪ size; or (ii) inject by restoring `data = open().read(); wfile.write(data)` and watch A2 fail | `_send_bytes` body read strategy (`watch.py:8613` today) |
| A3 | large logical size does not OOM / hang the suite | sparse file, e.g. write PNG magic + `truncate` to several hundred MB or use `os.posix_fallocate` only if needed; **do not write 1GB of data** | same as A2 |
| A4 | client disconnect mid-stream does not traceback | optional; pattern from #299 | bare `wfile.write` without catching pipe errors |

**Sparse-file idiom (honest, no 1GB write):**

```python
path = os.path.join(target, "huge.bin")
with open(path, "wb") as f:
    f.write(b"\x00\x01")   # binary head for kind=binary
    f.truncate(200 * 1024 * 1024)  # 200 MiB logical; sparse on ext4/xfs/btrfs
```

Assert `os.path.getsize(path) == 200<<20` and disk usage via
`os.stat(path).st_blocks` is far smaller (precondition: if not sparse, skip
or fail the environment — assert the gap so the check cannot pass on a full
allocation nobody noticed).

**RLIMIT_FSIZE** (`test_watch.py:4088-4099`) is the idiom for **write**
failures (#370). It does not induce a large **read**. Prefer sparse files for
#354; mention RLIMIT only if testing that a write path is untouched.

**RSS measurement caveats (state uncertainty):** peak RSS is noisy under
threads and page cache. Mitigations: (1) run the assertion only on Linux;
(2) compare before/after delta with a generous factor (e.g. delta < size/4);
(3) pair with a source/AST check that `_send_bytes` does not call
`read_bytes` / `.read()` without a size argument. The AST check alone can go
hollow if someone inlines `f.read()`; the RSS check alone can flake — **both
together**, or one solid mock of `open` that fails if `read()` is called with
no argument after the first 32-byte kind probe. Prefer instrumenting at the
**real open of the body** rather than patching `read_bytes` to return `b""`
for the large path (that is the hollow pattern this repo already paid for).

### B. Range (second)

| # | behaviour | check | production line |
|---|---|---|---|
| B1 | `Range: bytes=0-3` on a known blob → 206, body `blob[:4]`, `Content-Range: bytes 0-3/<n>`, `Content-Length: 4` | new test | range parse + seek path |
| B2 | `bytes=N-` last byte → correct tail | new | open-ended parse |
| B3 | `bytes=-3` suffix | new | suffix parse |
| B4 | `bytes=999999-` past EOF on small file → 416, `Content-Range: bytes */size`, empty body | new | unsatisfiable branch |
| B5 | malformed `Range: crap` → 200 full body (ignore) | new | ignore path; **precondition** body equals full file |
| B6 | multi-range `bytes=0-1,2-3` → 200 full (documented ignore) | new | comma branch |
| B7 | no Range still 200 + `Accept-Ranges: bytes` | extend existing or new | header emission |
| B8 | Range on escape path still 404 before range logic | extend escape test | order: confine then range |
| B9 | Range does not change MIME/disposition matrix | spoof SVG + PNG control with Range | disposition after range |

Each B* test must use a **real HTTP request** through `make_handler` (as
existing filebytes tests do), not only unit-test the parser — and **also**
unit-test the pure parser for the matrix of edge strings so the handler tests
stay few.

**Red proof for B1:** implement streaming only; B1 fails (200 full body). Add
Range; B1 green. That sequencing is the staging.

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
- Keep all headers; add nothing Range-related yet (or add only
  `Accept-Ranges: bytes` as a harmless advertisement — optional; can wait for
  increment 2 so Accept-Ranges is not a lie before Range works).
  **Recommend waiting:** do not advertise `Accept-Ranges` until 206 works.
- Tests: A1 green (existing), A2/A3 new and shown red against the old
  `read_bytes` path first.
- Docs: one paragraph in `watch-design.md`.

**Exit criterion:** a multi-hundred-MB sparse binary can be GETted without
≈size heap growth; small PNG proofs still byte-identical.

### Increment 2 — Single-range only

- Pure `parse_byte_range`.
- 206 / 416 / ignore-malformed / ignore-multi.
- `Accept-Ranges: bytes` on 200 and 206.
- Tests B1–B9, each red-first where practical.
- Docs: Range contract in `watch-design.md`.

**Exit criterion:** curl-style Range requests return correct slices; full GET
unchanged.

### Increment 3 — Disconnect hygiene + Cache-Control decision (optional)

- Quiet pipe errors on long streams (#299 class).
- Only if he asks: short max-age or validators — **not** required to close #354.

### Explicit non-increments

- Multi-range.
- ETag / If-Range.
- `/reviewraw` streaming (#355).
- Client-side JS that sends Range for images (unnecessary if streaming works).
- Changing confinement or the raster allowlist.

### Rough size

Increment 1: ~1–2 hours focused, mostly tests.  
Increment 2: ~2–3 hours including the parse matrix.  
No port / no `just guards` required for unit+HTTP tests; browser guard is
confirmation, not the design gate.

---

## What approval of this does not authorise

Nothing is built. Approving accepts:

1. Streaming-with-bounded-buffer is the **primary** fix for #354.
2. Single-range `206` is the **secondary** capability; multi-range and
   validators are out.
3. The #336 security contract (MIME, disposition, magic, confinement) does
   not move.
4. `Cache-Control` stays as today unless a separate ruling says otherwise.

It does **not** authorise editing `watch.py`, adding tests, changing guards,
or shipping any header behaviour.

---

## Uncertainties (honest)

1. **RSS-based memory assertions** can flake under load; the implementer
   should prefer a dual check (no unbounded read on the body path + sparse
   file behavioural bound) and treat a green-only RSS number as weak evidence.
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

- **#355** already tracks `/reviewraw`'s 2_000_000 character `read_text` cap
  (`watch.py:8700`) — still a full in-memory string for large artifacts;
  related class, different contract.
- **`read_bytes` is a loaded footgun** while it exists: any future caller that
  reuses it re-opens #354. Increment 1 should remove or sharply document it.
- No second copy of confinement logic was found; `/filebytes` does call
  `resolve_confined` (the test that proves it is load-bearing).

--- SUMMARY ---

- **Primary fix is streaming, not Range.** A 1GB file is held today as one
  full `bytes` from `read_bytes` (`watch.py:6752-6760`) inside `_send_bytes`
  (`:8613-8629`). The common client is `<img src="/filebytes…">` with **no
  `Range` header**, so Range alone leaves that path buffering the whole file.
  The ledger recommendation is incomplete in that sense; Range remains the
  right *non-corrupting* form of partial response, but as a second capability.
- **Current path, grounded:** `do_GET` `/filebytes` → `resolve_confined` →
  `detect_file_kind` (32-byte magic) → `_send_bytes` → unbounded `f.read()` →
  single `wfile.write`. Confinement is real (`resolve_confined` +
  `test_filebytes_blocks_escape`); it does not bound size.
- **Range design (smallest correct):** single `bytes` range only; `206` +
  `Content-Range` + slice `Content-Length`; `416` with `bytes */size` when
  unsatisfiable; malformed and multi-range **ignored** → full `200`;
  `Accept-Ranges: bytes` only once 206 exists; **no** multi-range, If-Range,
  ETag, or Last-Modified in this task.
- **Streaming design:** `stat` + open + 64KiB read/write loop; prefer
  `Content-Length` from size; never materialise the file; keep MIME /
  disposition / nosniff / Cache-Control behaviour from #336.
- **Cache-Control:** keep `private, max-age=0, must-revalidate` for v1;
  revisit only as a separate product call.
- **What must stay byte-identical:** full GET body vs disk; allowlist and
  attachment matrix; escape 404s. Guards `fileimg` / `fileview` / `filehead`
  should stay green without client changes.
- **Red-first plan:** existing byte-identical tests stay; new sparse-file
  memory/streaming tests (not a real 1GB write); Range matrix B1–B9 through
  real HTTP; each names the production line; avoid mocks that return empty
  bodies for the path under test.
- **Staging:** (1) stream full GET, (2) single-range 206/416, (3) optional
  disconnect hygiene / cache policy. Design only — no `watch.py` edits
  authorised here.
- **Uncertain:** RSS flake risk (pair checks); whether any target browser
  sends Range for images (high confidence no, not captured here).
