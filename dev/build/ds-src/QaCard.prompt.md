# QaCard

Render one Dreamwork question using the production `qaCard(q, k)` builder.
Pass the object from `QaCard.fixture.json` as props and load `styles.css` from
this package. `k` is the live entry address: `o<number>` for an open or
awaiting question and `a<number>` for a folded question.

The wrapper deliberately owns no HTML or palette. Edit `client/components.js`
to change markup and `client/style.css` to change appearance, then run
`just build-client`. Do not recreate the card from this prompt.

Local packaging proves export, fixture, styles, and builder/wrapper DOM
equality. The remaining ingestion question is human-judged: upload
`client/dist/ds/` to claude.ai/design, render the fixture, and check whether
the string-mounted component remains editable and useful at the desired
component granularity. No local check claims that external result.
