# Expand

Render a collapsible disclosure with the production `expand(s, inner, cls, keep)`
builder. Pass the object from `Expand.fixture.json` as props and load
`styles.css` from this package. `s` is the summary text, `inner` is pre-rendered
HTML body, `cls` adds a class to the `<summary>`, and `keep` is the persistence
key: when set it emits `data-keep` so the live tick restores the open state.

The wrapper owns no HTML or palette. Edit `client/components.js` to change its
markup and `client/style.css` to change its appearance, then run
`just build-client`. Local packaging and equality checks do not verify this
export format against the design tool.
