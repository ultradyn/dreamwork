# Answers

Render the complete `/answers` listing with the production `buildAnswers(data)`
builder. `Answers.fixture.json` contains five named prop sets; render
`unreadable`, `empty`, `open`, `answered`, and `askform` separately. The
unreadable state exercises the channel-broken banner; empty exercises both
"none awaiting the dreamer" and "none yet" fallbacks; open and answered each
exercise a real record through the matching `answerRecord` path with a
content-stable `aid`; askform is the populated healthy surface where the
ask-form sits alongside real open and answered questions.

This is a route-level design export, the second after Reviews. It delegates
wholesale because the production route and the coexistence guard still use
`buildAnswers`, so the wrapper owns no competing markup. Edit `client/views.js`
to change the route markup and `client/style.css` to change its appearance,
then run `just build-client`. Task #1050 must retarget or retire this export
when it deletes `buildAnswers` during the visible React route flip.
