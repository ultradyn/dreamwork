# DREAMWORK.md — guard fixture

## Goals

- Give the browser guards a target whose content never moves, so a red
  light means the code broke rather than that the loop got on with its
  work overnight.
- Hold one example of every input shape the renderer claims to handle,
  hard-wrapped at about seventy-two columns the way the loop writes.

## Philosophy

Small verified increments are the error-catching mechanism, and a
verification that depends on mutable state is not one. Prose here is
deliberately long enough to wrap several times in a question card, because
the reflow guard measures line boxes and needs paragraphs to measure.

## Preferences & Routines

- Fixture content changes are a deliberate act: a guard that starts
  failing after one is telling you about the guard, not the page.
