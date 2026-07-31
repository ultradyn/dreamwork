# Spike #279 — Jovian storm throwaway prototype: preserved findings

Preserved from the retired branches `prototype/279-jovian` (tip `ae4d3acb`)
and `prototype/279-jovian-final` (tip `a1c180c1`) by lane `#711`. The two
branches were a rewritten/rebased line: **`-final` supersedes `-jovian`
entirely** (verified by content, see "Branch relationship" below), so only
`-final`'s artifacts were preserved. The shader source is reproducible from
the findings note and was not preserved; the findings and the evidence
bounds are what a completed negative result leaves behind.

`#279`'s own ledger record named `prototype/279-jovian-final` as its
"throwaway primary source". This document is what that record now points
at on master, so dereferencing the record resolves to evidence rather than
to a deleted branch.

## Verdict

**Partial / FAIL against the seven supplied references.** The street and
spot variants read as atmospheric vortex structures, the spot has a
coherent dark eye and warm wall, and text remains the dominant object.
But the result still lacks the references' fine cloud-top turbulence,
luminous material depth, and organic multi-scale detail; the band cells
are especially too subdued to read strongly at the canonical tier. This
was the requested final iteration, so no further churn was attempted.

## Branch relationship (confirmed by content)

`comm -23` over the two branch tip trees is **empty**: no file present in
`prototype/279-jovian` is absent from `prototype/279-jovian-final`. The
`-final` branch additionally carries six `*-duplicate.png` capture pairs
(the duplicate-hash determinism proof its note describes). The `-final`
findings note is a strict superset of `-jovian`'s: it rewrites the
"Compact design" paragraph to replace the live two-tier performance
mechanism with frozen static telemetry (`n/a static`), rewrites the perf
decision criterion, and **appends** the "Final bounded visual iteration"
section that carries the FAIL verdict. `prototype/279-jovian` is
therefore a plain answer-1 delete (content superseded), recorded for
restoration as `git branch prototype/279-jovian ae4d3acb`.

## Evidence bounds (from the `-final` note)

The findings note is the throwaway primary source; the numbers below are
its *bounds*, not a reproduction. The capture protocol was a frozen static
pipeline — fixed 24-RAF warmup, stop RAF, one fixed-time render, frozen
telemetry, screenshot, checksum of final PNG bytes — at a single canonical
0.32 linear-resolution tier, never adapted during capture. Determinism was
proven by capturing each desktop/mobile variant twice and recording
byte-identical final-file sha256 hashes (12 captures, 6 distinct hashes,
each pair identical):

| variant | device | sha256 (first 16) |
|---|---|---|
| bands | desktop | `05aae9172318dcbe` |
| bands | mobile | `eed1d448f89acc5a` |
| street | desktop | `e1137c491eea645a` |
| street | mobile | `fc9230dcf30ffe90` |
| spot | desktop | `4ebcafe91104ee0f` |
| spot | mobile | `29acecd8cdff8af9` |

Sanity probes rejected all-white failures (`nonWhiteFraction`, mean
luminance, band/street/spot geometry energies) but do **not** prove a
frame is nonblank — a fully-black frame passes them. Human Vision
established the committed captures contained visible structure; the probes
are bounds, not proof. `expectedFocalBBox` is declared responsive framing,
not image-derived detection. RAF interval is labelled `n/a static` because
no live performance was measured under the static protocol; any later
benchmark is separate and must label its own quantity.

## Design compact (from the `-final` note)

A standalone offline HTML document owns a WebGL canvas, a restrained
dashboard-text specimen, a metrics readout, and an accessible bottom
switcher. `?variant=bands|street|spot&seed=<n>&time=<s>&frame=<i>` makes
states shareable and deterministic; `frame` wins over live time. Three
fragment-shader branches deliberately disagree about geometry:

1. **Broad band shear** — many horizontal jets with offset noise, sparse
   rolling folds, maximal calm.
2. **Nested vortex streets** — counter-rotating eddies nested along
   multiple jet boundaries, maximal reference-like complexity.
3. **Deep storm** — one elliptical Great-Red-Spot-like circulation with
   concentric shear, eye-wall detail, and surrounding bands.

All render at a quarter-linear-resolution buffer, upscaled once, at the
single 0.32 tier. The genericness critique (anisotropic horizontal shear;
eddies that deform neighbours; ≥3 spatial scales; near-black blue/umber
luminance; asymmetry; geometric, not palette, variant differences; text as
the brightest object) held and is the reason a generic space-nebula shader
would have failed the references.

## What outlives the spike

The durable negative result: a WebGL storm shader approached the supplied
references' large-scale structure but could not reach their fine
turbulence, luminous depth, or organic multi-scale detail at the canonical
performance tier, and the deterministic static capture pipeline's sanity
proves non-white, not non-blank. `#280` (an open follow-on) remains
blocked on this result; `watch.py`'s current shader is unchanged.
