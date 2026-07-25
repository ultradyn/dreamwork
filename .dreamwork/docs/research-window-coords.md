# Window coordinates — what this project concluded

The research itself is **generic browser knowledge and lives in the KB**,
where other projects can find it:
`~/.llm-general/ui-design/multi-window-screen-coordinates.md` — short
answer, per-question detail, a what-breaks table, and sources with a
verified/unverified split. Commissioned 2026-07-25.

Kept here: what it means for THIS page, which is the part that would be
lost if only the general note survived.

## The three that matter to us

1. **`screenX`/`screenY` already measure the VIEWPORT**, in CSS pixels.
   Our anchor point was right, and the chrome-offset problem we expected
   to solve does not exist.

2. **They return 0 on native Wayland**, by protocol, and the mode is
   undetectable from JS. So `#74`'s world-space shader anchoring
   collapses to "every window at the origin" on some configurations —
   silently, since it looks identical to the feature being off. It works
   here only because an unrelated CLAUDE.md mitigation puts Brave on
   XWayland. Filed as **#189**, which also blocks **#187**'s
   cross-window ripple: that wavefront was to ride a coordinate system
   that, there, is not present.

3. **There is no window-moved event**, so polling is the only option —
   which suits us, since the page already polls. And a single scale
   constant is wrong across monitors with different `devicePixelRatio`.

## The idea we would not have had

**Drag-to-align.** Where the browser refuses to say where the window is,
ask him once: show something to line up across the seam, let him drag,
store the offset. It is the only recovery available on Wayland, and it
turns an unfixable platform limitation into a ten-second setup that
suits this page's character.
