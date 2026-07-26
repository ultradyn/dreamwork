# `ud-dw-generate` notes

## Intended purpose

`ud-dw-generate` should generate random ASCII-safe data. Hex output is the
initial expected shape unless a later use case establishes a different safe
alphabet or output contract.

## Provenance and current state

This helper was based on something Max requested in the dd2 download-page
repository. The current untracked executable is still coupled to that dd2
preview/download infrastructure; it is not yet the intended standalone random
data generator and should not be treated as an approved implementation of this
note.

Leave the executable untouched for now. Revisit it after the dd2 implementation
is fixed, then define the standalone CLI contract and remove the dd2 dependency
before adopting or committing the helper here.
