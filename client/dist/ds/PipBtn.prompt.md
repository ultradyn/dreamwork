# PipBtn

Render the pop-out affordance with the production `pipBtn(url, label)` builder.
Pass the object from `PipBtn.fixture.json` as props and load `styles.css` from
this package. The button is icon-only: it carries `data-pipurl` (the float
target), `data-piplabel`, and a fixed `title` tooltip.

The wrapper owns no HTML or palette. Edit `client/components.js` to change its
markup and `client/style.css` to change its appearance, then run
`just build-client`. This export is button MARKUP only; the separate-document
Document-PiP runtime (#859) is not part of it. Local packaging and equality
checks do not verify this export format against the design tool.
