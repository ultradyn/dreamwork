# QaCompose

Render the answer/note compose dock with the production
`qaCompose(key, st, title)` builder. Pass the object from
`QaCompose.fixture.json` as props and load `styles.css` from this package.
`ck` is the live entry address (`o<number>` open, `a<number>` folded), `st`
is the entry state, and `title` is the question title used for the field's
accessible name. (The prop is `ck` rather than `key` because React reserves
`key` for reconciliation and strips it from component props.)

The wrapper exports the MARKUP only. The send button's `onclick` names
`submitCard`, which the live dashboard resolves after mount; the POST path is
not reproduced here. The wrapper owns no HTML or palette. Edit
`client/components.js` to change its markup and `client/style.css` to change
its appearance, then run `just build-client`. Local packaging and equality
checks do not verify this export format against the design tool.
