# #278 · Background shader “acceleration” (read-only diagnosis)

**Date:** 2026-07-26  
**Agent:** grok-sugar-vesi-x6tv  
**Authority:** diagnosis only — no source / Jupiter prototype changes  
**Status:** evidence collected; true open-duration acceleration **not** reproduced

## Claim under test

Over a long open tab, the dream background *appears* to move faster. Candidates listed in the assignment: absolute wall-clock growth/precision, accumulated warp/twist, duplicate RAF loops, timestamp units, resize/reinit, perceptual geometry. Distinguish FPS from apparent velocity.

## Source seams (`watch.py` `SHADER_JS` / `mountDreambg`)

| Input | Source | Notes |
|-------|--------|--------|
| Shader phase `t` → GLSL `uniform float t` | `(Date.now() * 0.001) % 86400` | Wall clock, UTC-day wrap (comment: float precision + multi-window lockstep) |
| Fractal time use | `tt = t * 0.03`, `sin(tt*1.7)`, fBm offsets ±`tt` | Constant coefficients — **no integrated velocity state** |
| Warp pulse | `warpStart = lastMs` (RAF `ms`); envelope 0→1→0 over ~1.6s | From `pulseWarp()` on route dissolve only |
| Tint / project hue | exp lerp with `dt` capped at 0.1s | Cosmetic; not fractal advection |
| Domain anchor | `screenX/Y * WORLD_SCALE`, `domScale = WORLD_SCALE * innerHeight/fboH` | World-space pin; re-read every frame |
| Loop | single `requestAnimationFrame(step)` chain per mount | `stop` on context loss; remount only on restore / popout |
| Feedback textures | explicitly unbound each frame | No multi-frame feedback accumulation |

Mount sites: main page once (`window.dreambg = mountDreambg(...)`); popouts call `mountPopoutBg` → separate canvas/window only.

## Fixture / method (non-vacuous)

- Disposable target `/tmp/dreamwork-278-fixture`, `watch.py --port 39951` (not 35110/35111).
- Playwright Chromium headless; canvas `#dreambg` present (`550×350` buffer), `window.dreambg.frames` advancing.
- **Optical velocity proxy:** mean absolute channel difference (MAD) between consecutive frames on a 100–120px downscale of the WebGL canvas.
- **FPS:** `Δframes / Δwall`.
- **Time rate:** `Δ((Date.now()*0.001)%86400) / Δwall` (theory = 1).
- Conditions: real open early; `Date.now` patched +6h / +20h (simulates late UTC / long absolute time while keeping RAF cadence real); real +8s open; after SPA navigations.
- Scratch: `/tmp/dreamwork-278-evidence/probe.json` (+ screenshot).

## Measurements (summary)

| Condition | ~FPS | avg frame-to-frame MAD | mad/sec | mean `secs` | max warp |
|-----------|------|------------------------|---------|-------------|----------|
| early-real | 59.8 | **0.546** | 32.8 | ~33570 | 0 |
| Date.now +6h | 60.0 | **0.190** | 11.4 | ~55170 | 0 |
| Date.now +20h | 61.7 | **0.475** | 29.0 | ~19171 (wrap) | 0 |
| after 8s real | 57.0 | **0.518** | 29.6 | ~33580 | 0 |
| after nav | 59.4 | **0.526** | 31.4 | ~33583 | 0.066 |

Fixture non-vacuous: MAD ≫ 0, FPS ≈ 60, shader handle live.

Float32 step of `t` at 0…86399 still resolves ≈1/60 s (`delta` 0.0156–0.0176 vs ideal 0.0167) — not a double-rate time quantiser.

RAF instrumentation while measuring shows elevated concurrent callbacks (probe’s own `rAF` + shader); not proof of multiple shader roots. Architecture mounts one main loop; navigations call `pulseWarp`, not remount.

## Hypotheses

| # | Hypothesis | Prediction | Verdict |
|---|------------|------------|---------|
| H1 | Open-duration true acceleration (dt integration bug) | MAD/sec rises after long open at fixed FPS | **REFUTED** (8s real: MAD 0.52 vs early 0.55; FPS flat) |
| H2 | Absolute wall-clock magnitude makes motion faster | +6h/+20h Date.now increases MAD/sec | **REFUTED** (+6h **slower** optically; +20h ≈ early) |
| H3 | float32 `t` loses sub-frame steps → jumps look like speed-up | large `t` has Δt ≫ 1/60 | **REFUTED** in [0,86400) |
| H4 | Accumulated warp/twist | `warp` grows with session | **REFUTED** (settles 0; only brief pulse after nav) |
| H5 | Duplicate RAF after rerender/navigation doubles speed | FPS or MAD doubles after nav | **REFUTED** (FPS ~60; MAD unchanged) |
| H6 | Timestamp unit mix (ms vs s) doubles rate over time | `dSecs/dWall ≠ 1` or drifts | **REFUTED by construction** (`Date.now` seconds); warp uses RAF ms only for envelope age |
| H7 | Resize/reinit accelerates | size() changes time base | **Not indicated** (no size path mutates `t`) |
| H8 | **Phase-dependent / perceptual agitation** | Optical MAD varies with UTC phase / field state, not open age | **SUPPORTED** (MAD 0.19 vs 0.55 at different `secs`; equations recompute pure `f(t,p)` each frame) |
| H9 | Many navigations → frequent `pulseWarp` feels “faster” | warp spikes on dissolve | **PLAUSIBLE secondary** (measured maxWarp 0.066 after nav; design intent) |

## Distinction: FPS vs apparent velocity

- **FPS** stayed ~60 under all probes → not a throughput acceleration.
- **Apparent velocity** (MAD/sec) tracks **where** the day-phase fractal sits, not how long the tab has been open.
- Shader advection rate in GLSL is `∂tt/∂t = 0.03` constant; curl amplitude is bounded (`0.38+0.14*sin(...)`).

## Smallest candidate seams (if product still wants a calmer long-session feel)

Not a confirmed “bug fix” — hardening / product choices:

1. **Document as non-bug:** wall-clock phase is intentional multi-window lockstep; appearance evolves with UTC, not with tab age. Midnight `% 86400` is a one-shot reshuffle (already commented).
2. **If long-open calm is desired:** drive fractal `t` from `performance.now()/1000` (page-local) or a shared epoch at first paint, keeping optional wall sync behind a flag — trades multi-window field continuity for session-stable “tempo perception.”
3. **If nav stir is the complaint:** reduce `pulseWarp` amplitude / rate when dissolves are frequent (chrome/tick-related dissolves), separate from ambient `t`.
4. **Optional later measure:** hour-scale real open with MAD logging (not required here; 8s + absolute time injection already falsify open-age rate growth).

## Conclusion

Under disposable instrumentation, the background does **not** accelerate as a function of open duration or absolute `Date.now` magnitude. FPS and time advance are stable; optical change rate is **phase-dependent** on the wall-clock fractal field (and briefly elevated by intentional route `pulseWarp`).  

**Smallest explanatory seam:** pure wall-clock `t` + constant-rate domain warp in `FRACTAL_FS`, not a runaway integrator or multi-RAF bug.

No source edits performed.
