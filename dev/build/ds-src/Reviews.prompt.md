# Reviews

Render the complete reviews listing with the production `buildReviews(data)`
builder. `Reviews.fixture.json` contains three named prop sets; render
`loading`, `empty`, and `multi` separately. The multi-row state deliberately
uses distinct names, decisions, and question links so it exercises row order,
the join, and both linked decision markers.

This is the first route-level design export. It delegates wholesale because
the production route and the coexistence guard still use `buildReviews`, so
the wrapper owns no competing markup. Edit `client/views.js` to change the
route markup and `client/style.css` to change its appearance, then run
`just build-client`. Task #1044 must retarget or retire this export when it
deletes `buildReviews` during the visible React route flip.
