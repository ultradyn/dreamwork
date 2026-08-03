# ArtifactRow

Render one review or research artifact row with the production
`artifactRow(r, kind)` builder. Pass the object from `ArtifactRow.fixture.json`
as props and load `styles.css` from this package. `kind` is `"review"` or
`"research"`; the view link and raw endpoint follow the one `/<kind>`
convention. `r.decision` — `"accepted"`, `"rejected"`, `"pending"`, or absent
(`"unlinked"`) — controls the decision marker; `r.question_title` links it to
the question it was raised against.

The builder lives in `client/views.js` (the only one of the exported wrappers
that does), and it is consumed here by bare name, never copied. The wrapper
owns no HTML or palette. Edit `client/views.js` to change its markup and
`client/style.css` to change its appearance, then run `just build-client`.
Local packaging and equality checks do not verify this export format against
the design tool.
