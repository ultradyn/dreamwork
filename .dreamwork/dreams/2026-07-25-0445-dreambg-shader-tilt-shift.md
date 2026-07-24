# Dream — dreambg: tilt-shift fractal background (task #51)

Replaced the placeholder `dreambg` shader in watch.py with a real dream-like
background: a domain-warped fBm fractal (5-octave value noise, two levels of
warp) rendered to a ~1/6-res buffer, then pushed through a drifting
tilt-shift depth-of-field so most of the frame is softly out of focus at any
moment. Composited very subtly over #0b0f19 in an indigo/violet palette,
dithered against banding. Text always wins (peak shader luminance ~0.10 vs
dim-text ~0.42). A hidden layer switcher ('l' key, or triple-click the
bottom-right corner) cycles the raw components — fractal, warp field, focus
mask, blurred fractal — with an unobtrusive fading label. Kept: pause when
hidden, reduced-motion static frame, no-WebGL fallback, inline GLSL, single
embedded string.

## The blur IS the perf budget — and it doubles as a driver-bug sidestep

All the costly work stays low-res: fractal at 1/6, the multi-tap blur at 1/6
too (split into two compounding 8-tap passes), and only a 1-tap upscale
touches full res. This is the intended "render low, upscale through blur"
pattern — but it also turned out to be the only shape that renders reliably
under headless SwiftShader, which was the real story of this increment.

## Headless-GL context loss is flaky, not your shader

Most of the time here went into a context that was lost by animation frame
~2/3, painting nothing (flat #0b0f19). The trail: FBO round-trips work
single-shot; a trivial continuous loop survives; but a heavy fractal FBO
sampled by a many-tap blur drops the context — and crucially it's
**intermittent** (a structurally identical pipeline survived one run and died
the next; 16 taps died, 12 lived, then 12 died elsewhere). It is not a
deterministic property of the shader; it's a headless-SwiftShader defect that
won't hit the human's real GPU.

Three things made it robust: (1) a real `webglcontextlost`/`restored` handler
that rebuilds every GL object and resumes — best practice that also protects
real users on GPU reset / tab backgrounding; (2) reload-on-loss in the
capture harness (retry the page until a context survives ~1.5s) so headless
review is reliable; (3) keeping per-draw tap counts modest and blurring at
low res. Also fixed a genuine bug found along the way: leaving the FBO
texture bound to a sampler unit while it is the render target is a feedback
loop — unbind before rendering into a target each frame.

## Method note

The visual-review loop earned its keep: the "flat #0b0f19" failure was
invisible to reasoning and obvious the moment I measured pixels (zero
variance where dither guarantees noise). Screenshot-and-measure, not imagine.
