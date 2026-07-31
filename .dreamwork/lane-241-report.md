# Lane 241 report — one composer mount contract

## Duplication measurement first

The three named window targets contain **two implementations, not three**.
The main document had one 588-line rich-composer initializer (pre-extraction
`client/command.js:257-844`). Document PiP and `window.open` both pass through
the same `openPopout` callback and therefore share one reduced popout
implementation: 66 lines of binding/submission code (`requestPopout`), 12 lines
of body markup (`POPOUT_BODY`), and 34 lines of private CSS (`POPOUT_CSS`). The
window-selection branch is not a composer rendering branch.

Measured across the seven requirements:

| Requirement | Before this increment | Contract coverage now |
|---|---|---|
| command vocabulary | **Not duplicated.** `POPOUT_BODY` already maps the same mutable `COMMANDS` table as the main composer. | Covered by reference to the one table. |
| plugin refresh | **Absent in the reduced popout**, not duplicated. Only the main composer runs `syncPluginCommands`; an already-open popout is a snapshot. | The rich implementation's refresh is inside `mountComposer`; the two popout targets are not converted yet. |
| per-project draft/settings | `DraftStore` is shared, but lifecycle wiring is duplicated: rich `composer:main` versus reduced `popout:main`; selection state is rich-only. | Partly covered. The rich draft/selection lifecycle is inside the contract. Converting popouts must delete their separate bind/restore/clear wiring. |
| submission witness | Duplicated: main uses `postJSON`; popout owns raw `fetch`, action-id headers, `writeVerdict`, and durability branching. | Partly covered. The rich witnessed path is inside the contract. Converting popouts must delete the raw-fetch path. |
| keyboard behavior | Duplicated: main document and popout document install separate Ctrl/Cmd+Enter handlers. | Partly covered. Rich keyboard behavior is inside the contract; the popout handler remains until conversion. |
| transitions | Confirmation lifecycle logic is **not duplicated** (`confirmationFor` is shared), but the popout restates its transition CSS. | Behavior is covered; target-document transition CSS is not yet covered. |
| styling | Duplicated/divergent by design today: the main composer uses the client stylesheet while the reduced popout owns 34 lines of `POPOUT_CSS` and different markup. | **Not covered by this increment.** A popout conversion must install the real rich markup and shared stylesheet into its target document, then delete `POPOUT_BODY`'s command form and its private composer CSS. |

Nothing in the seven is unclassified. Styling is explicitly uncovered;
plugin refresh is explicitly missing on the old popout rather than counted as
a duplicate.

## Verdict and change

Landed one contract and converted one existing mount site: the main document.
`mountComposer({document, window, surface})` now contains the entire existing
rich implementation. It validates its target, refuses a missing palette or a
second mount, stamps `data-composer-mount`, installs every behavior, and returns
only the mounted controls. The sole main-document call is
`mountComposer({ document, window, surface: 'main' })`.

This is a **contract**, not a convention. There is no separately callable rich
builder or fallback binding path: the implementation body exists only inside
`mountComposer`. A bypass has static markup but no mounted marker and no opener,
keyboard, draft, refresh, witness, transition, or submission behavior.

Document PiP and `window.open` remain named, deliberately unconverted targets.
They already share window creation and one reduced fill. Converting them means:

1. install the real rich composer DOM and shared stylesheet in the acquired
   target document;
2. call this same mount contract with that document/window;
3. make opener-owned dependencies (`data`, `COMMANDS`, `DraftStore`, witnessed
   POST, plugin updates) explicit inputs where cross-window lookup requires it;
4. delete the reduced `POPOUT_BODY` command form, its private composer CSS, raw
   submit/witness path, draft wiring, and keyboard handler.

No other cluster task was started and `watch.py` was untouched.

## Served page

The served page **did change**, intentionally, because its bundled JavaScript
now contains the contract and main mount call. The base bundle was 235,458
bytes, sha256 `55ba43765ebc8b7d0c4362aec650844c9961cc1ef1a010874ddc85d0e82e30f8`;
the rebuilt bundle is 236,192 bytes, sha256
`c2dc7cf54d2be972b7c44a2bd9808bdcea81e474caeade58955779e0abb90361`.
No HTML builder or CSS source changed, so there is no intended visual or
interaction change. The browser proof read `marker:"main"` and opened the
palette through the existing `#cmdplus` gesture; the `dismiss` guard also
passed its composer behavior assertions.

## Red-proof, both directions

Direction 1 injected the real bypass by deleting the sole main-document
`mountComposer(...)` call, rebuilt `client/dist`, and loaded the real served
page in one Chromium process. The discriminating failure was:

> `FAIL composer contract bypass: expected marker=main and opener bound; got {"marker":null,"openBefore":false,"openAfter":false}`

After restoration and rebuild the same probe said:

> `PASS composer contract mount {"marker":"main","openBefore":false,"openAfter":true}`

Direction 2 asked whether a mount could bypass the contract yet render the
same composer. The constructed bypass above could not: it had neither the
contract marker nor a working opener. Calling the implementation directly is
also impossible because no second implementation exists. The remaining way to
make a bypass render identically would be to author a new second composer;
that is a new renderer, not an alternate route left by this extraction.

The final post-rebase restore gate said:

> `history: examined 1 commit(s) since 64b9eb2b7c67 (master) ... read 1 blob(s), 0 holding a recorded injection.`
>
> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

## Verification

- Branch point verified: supplied base, initial `HEAD`, local `master`, and
  merge-base were all `9c62f384c5dcee7855efb3e7c19d1c78b43b2dae`.
- `just build-client`: rebuilt 14 inputs / 3 outputs; manifest current.
- Targeted pytest: four exact nodes across `test_watch.py` and
  `test_client_dist.py`, **4 passed**. These bind command palette wiring,
  one command vocabulary, popout shader wiring, and reproducible committed
  build output respectively.
- Browser guard: `DREAMWORK_GUARDS=dismiss DREAMWORK_HUB_GUARDS= just guards
  39741`, preflight load **23.61**, `PASS dismiss`, 1/1 judged. Its assertions
  catch the main composer failing to open/submit, incorrect courtesy dismissal,
  loss while typing, and confirmation transition regressions.
- One-process contract probe: PASS after restoration, discriminating FAIL on
  bypass as quoted above.
- `python3 dev/redproof.py check --require 1 --base master`: clean as quoted.
- `python3 lint.py`: clean with the required **6 warnings**; `client/dist`
  reports **OK**, matching 14 inputs and 3 outputs.
- Local `master` moved four commits while the lane ran. Rebased successfully
  from the verified branch point onto `64b9eb2b7c677c5285bb50afba0edf0308fa48a7`
  with no conflicts, rebuilt, and reran pytest/lint/red-proof. Post-rebase code
  commit: `3b8443cd3ac95b3e709005fed395d0508a4a12da`.

## Authorities read and relied on

- `#241`: “make the existing rich composer mountable in main document,
  Document PiP and `window.open` fallback without duplicating command
  vocabulary, plugin refresh, per-project draft/settings, submission witness,
  keyboard behavior, transitions or styling”.
- `#630`: “Wrappers are divergence-**IMPOSSIBLE** ... **because the second
  rendering does not exist**: `Delegate` holds a *call* and has no fallback
  markup at all”. This governed putting the implementation inside the mount
  route rather than leaving an independently callable fallback.
- `#440`: “the check that matters is that the tool exists and is the only path”.
  This governed making the sole implementation be the mount function itself.
- `#668`: “the rule binds the ON-DISK MASTER STATE ... and the WEBUI's state is
  explicitly secondary and explicitly allowed to be a second description”.
  No on-disk master-state path changed here.

## Out of scope

- The reduced popout does not refresh plugin commands after opening.
- The reduced popout still owns a second submission/witness path, keyboard
  handler, draft lifecycle, markup, and CSS. Those are the exact deletions the
  next two mount conversions must make; this increment intentionally does not
  hide them behind a claim of full coverage.
- Existing `chatReplyComposer` is a different reply surface and not one of the
  three rich-command-composer targets.

## DOGFOOD REPORT

The brief's initial count of “23 composer references” was useful orientation,
but reference counts overstated implementation duplication: the two floating
window mechanisms already converge before rendering, and command vocabulary,
confirmation behavior, and storage infrastructure were already shared. The
mandatory seven-item measurement prevented turning an extraction into an
unnecessary rewrite.

The browser-guard instruction was reachable and accurate. `dismiss` covered
the main rich composer but not the new mounted marker, so the authorised
single-process static probe was necessary to bind the contract property
itself. No other tooling friction or misleading premise was found.
