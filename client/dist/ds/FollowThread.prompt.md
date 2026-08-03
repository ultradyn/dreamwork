# FollowThread

Render a note thread with the production `followThread(follows, fold)` builder.
Pass the object from `FollowThread.fixture.json` as props and load
`styles.css` from this package. `follows` is the array of note objects (`author`,
`text`, `when`); `fold` collapses the thread behind a `<details>` summary when
the thread holds two or more notes.

The builder reads the page's mutable `data` binding while formatting note text,
so `ctx` gives a bounded temporary context (the same `ambient` seam `QaCard`
uses), then restores the surrounding bundle even when the builder throws.

The wrapper owns no HTML or palette. Edit `client/components.js` to change its
markup and `client/style.css` to change its appearance, then run
`just build-client`. Local packaging and equality checks do not verify this
export format against the design tool.
