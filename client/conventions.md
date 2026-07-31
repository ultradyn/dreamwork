# Dreamwork dashboard conventions

The dashboard is a dark, monospace operations surface. Its visual language is
quiet by default: one cool accent marks live activity, while the warm warning
colour is reserved for a broken channel that the operator cannot otherwise
see.

## Styling source

- `style.css` is the sole source for token values and component CSS. The
  dashboard serves that file, and `just build-client` copies it byte-for-byte
  to `dist/ds/styles.css` under the client-dist manifest guard.
- `tokens.css` is only a tooling entrypoint: it imports `style.css` and contains
  no values of its own. Extract custom properties from the imported `:root`.
- Never copy a hex value into generated component code or this document. Use a
  `var(--name)` reference and read `style.css` when choosing the name.

## Token intent

Use the background and panel family for depth, the line/border family for
structure, and the text family in descending emphasis. Accent is for current
activity and interaction. Warning means a broken communication path, not a
generic highlight. The code-only palette is confined to source panes.

Spacing and radius are tokens too. Preserve the narrow reading column, compact
type scale, stable scrollbar gutter, and visible keyboard focus rings. Motion
should explain continuity across navigation or regrouping; reduced-motion
rules remain authoritative.

## Component work

Prefer the existing class vocabulary and component builders before adding a
new styling idiom. Stage-2 React wrappers must delegate to those builders and
must not contain fallback markup. A wrapper may add a mounting boundary, but
it must not reinterpret token values or duplicate HTML.
