# #413 — a guard can encode a SUPERSEDED contract, and nothing measures that

Branch `wt/superseded`. Author: the `[superseded]` lane. This is the
measurement-first brief: it inventories the fakes, names the production
fact each pins, and says which it could NOT verify before designing any
checker. The single most valuable concrete deliverable — widening
`health.mjs`'s two blind checks — is in the same commit as this doc.

## The instance, and why a status-pin checker would have missed it

`health.mjs` carries exactly the checks `#263`'s `E5` wants:
*"never shows the answered state for a write that did not land"* and
*"keeps his text, which is now the only copy of it"*. Both were green
with the defect fully present (lesson, 2026-07-29). The client write path
branches on `res.ok` alone:

```
watch.py:3576   if (!res || !res.ok) { qaFail(card, res ? res.status : 0); return; }
```

The fake pins the refusal at `status: 409` (`health.mjs:212`), so it only
ever drives the branch where `res.ok === false`. `E5` is a refusal that
arrives as a `202` — where `res.ok === true` — and the guard runs the
confirming morph anyway: the card restates itself answered, his text is
cleared, and the next tick puts the question back with no explanation.

**The sharp half, and it is the brief's hardest requirement:** a checker
that greps fakes for a pinned status and checks it against the production
constant would NOT have caught this, because `409` is still exactly what
production returns for a `/answer` refusal today (`watch.py:5533`,
`self.send_error(409)` in `_handle_answer`). The pinned fact is **not
stale**. The blindness is in the fake's **scope**: it drives one of the
two statuses the client branches on. The contract that moved is the one
the fake never named. A stale-value detector is the right tool for the
*other* fakes in the inventory (below) and the wrong tool for this one.

## 1. The inventory — every fake in `dev/capture/*.mjs`

Derived with one expression (production facts read from `watch.py`'s
`_handle_ask` / `_handle_answer` / `_handle_comment` / `_handle_command`
and `_send_receipt`):

```
rg -n 'route\.fulfill|new Response\(|window\.fetch\s*=|page\.route\(|status:\s*\d{3}' dev/capture/*.mjs
```

Two species. **Hardcoded-status fakes** literalise a status the server
owns — these are the `#413` family. **Real-server fakes** rewrite the
request and let production choose the status — these are immune, and are
the pattern to prefer (the `subslog`/`submitlog` instances).

### Hardcoded-status fakes (the family)

| Fake (file:line) | Route | Pinned | Production fact | Verdict |
|---|---|---|---|---|
| `health.mjs:212` | `/answer` refusal | `409` | `/answer` refusal IS `409` today (`:10267`) | **Holds, but blind to the `202` refusal** — the `E5` instance |
| `docktarget.mjs:48` | `/answer`,`/comment` success | `200` | success is `202` via `_send_receipt` (`:9958`, journal on) | **Stale** (`200`→`202`); client uses `res.ok` so the check still passes |
| `answers.mjs:364` | `/ask` refusal | `409` | `/ask` has NO refusal path — it always appends (`202 {ok:true}`); bad input is `400` | **Stale / never-existed**: `409` is a status production never returns for `/ask`; same `E5` blindness on `sendAsk` (`:3159`) |
| `reviewdraft.mjs:235` | `/answer` failure | `500` | `/answer` failures are `400`/`404`/`409`, never `500` | **Stale / never-existed**; client treats any `!res.ok` alike so the check passes regardless |
| `draft.mjs:155` | `/command` failure | `500` | `/command` failures are `400`, never `500` (`:10325`) | **Stale / never-existed**; same as above |
| `history.mjs:120` | `/command` failure | network `reject(TypeError)` | `/command` failures are `400` status (`res.ok` false), not a network reject | **Holds as a category** (unreachable is a real client state: `res=null`), but does not exercise production's actual failure status |

### Real-server fakes (immune — production decides the status)

| Fake (file:line) | Route | What it does | Verdict |
|---|---|---|---|
| `subslog.mjs:115` | `/comment` | rewrites the request to a stale title, calls `realFetch`, asserts `status === 409` read from the real response | **Holds** — and robust: if `/comment` refusal ever becomes `202`, this read flips and the check flags it |
| `submitlog.mjs:91` | `/answer`,`/comment` | same shape: rewrites to a stale title, `realFetch`, reads status from the response | **Holds** — same robustness |

### Latency / instrumentation fakes (not status pins)

`confirmation.mjs:42/107/172` delays `/command` 400–500ms (intentional
latency, not a contract); `morphhold.mjs:162` instruments `/mtime`
`text()` timing and writes a real `/command`. Neither pins a server
status. Both hold.

## 2. The counts

- **6** hardcoded-status fakes total.
- **Confirmed stale (pinned status production no longer returns, or never returned):** **4** — `docktarget` (`200`→`202`), `answers.mjs:364` (`409` for `/ask`, never produced), `reviewdraft` (`500` for `/answer`, never produced), `draft` (`500` for `/command`, never produced).
- **Holds today but blind to the moved contract (the `E5` shape):** **1** — `health.mjs` (`409` for `/answer` is correct; the blindness is the missing `202` case).
- **Holds as a category, not a status match:** **1** — `history.mjs` (network reject is a real client state; not a production status).
- **Could NOT verify against production:** **0** for the status itself — every pinned status was checkable against `watch.py` source. The category the brief warned about applies one level up, and it is worth naming: **for 3 of the 6 (`reviewdraft`, `draft`, `answers.mjs:364`), I could verify the pinned status but could NOT verify the check *depends* on it** — the client treats any `!res.ok` identically, so the literal status is decorative to the assertion. That is the #413 blind spot from the other direction: a pinned value that is not load-bearing for the check reads as coverage while exercising nothing the check names.

## 3. IGC — the general mechanism

**Context.** `watch.py` is held by `laneE5b` (mid-increment on the client
write paths); the fakes are `.mjs` (Node/Playwright). The production
statuses are literals in Python (`send_error(409)`), not named constants,
and the language boundary makes "the fake imports the constant"
impossible without a bridge this repo does not have.

**Goals (each binary).**

- **G1** — catches the `health.mjs` instance (a fake blind to the `2xx`-refusal branch), not only stale-value fakes.
- **G2** — cannot pass by matching nothing (this repo's most-paid-for failure).
- **G3** — adopts one guard at a time; no ~69-file sweep (the `report.mjs`/`serve.mjs` precedent).
- **G4** — needs no edit to `watch.py` and no JS↔Python constant import.
- **G5** — carries no literal tuned to today's tree (the "assert the precondition, derived" rule).

**Rivals.**

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| **R1** grep lint: a pinned status must reference the production constant | ✘ | ✘ | ✔ | ✘ | ✘ | ✔ |
| **R2** fake imports the constant instead of literalising it | ✘ | ✘ | ✔ | ✘ | ✘ | ✔ |
| **R3** per-guard declaration of the contract it encodes, checked against a registry | ✘ | ? | ✘ | ✘ | ✔ | ✘ |
| **R4** runtime assertion in the fake that the pinned value still appears in production source | ✘ | ✘ | ✔ | ✔ | ✔ | ✔ |
| **R5** in-guard coverage assertion: a refusal guard drives a refusal on a `2xx` AND a `4xx`, count derived at runtime | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

**The decisive errors.**

- **R1 ✘G1:** `health.mjs`'s `409` *is* the production constant — the grep passes and the blindness remains. This is the brief's own warning made concrete: the motivating instance refutes the grep checker. **✘G4:** the constants are Python literals in `watch.py`; an `.mjs` cannot import them, and the file is held by another lane. **✘G3:** a sweep over every `route.fulfill` is stale the day a 70th guard is written.
- **R2 ✘G1, ✘G4:** even if the constant were importable, importing `409` does not add the `202` case — the scope blindness survives. Same language-boundary block as R1.
- **R3 ✘G3, ✘G5, ?G1:** a registry of "refusal statuses the client branches on" could in principle force coverage of `{409, 202}` — but the registry is itself a literal tuned to today's client (`✘G5`), maintained across every guard (`✘G3`). It moves the supersession hazard from the fake into the registry without removing it.
- **R4 ✘G1:** `409` still appears verbatim in `watch.py:5533` — the assertion passes and the `E5` blindness is unchanged. Correctly catches the *stale-value* fakes (`docktarget`'s `200`, the `500`s) and worth landing for those, but it is not the general mechanism because it misses the instance that motivated the task.
- **R5 ✔all:** the survivor. It forces the one thing the `E5` instance lacked — a refusal driven on a status the client treats as *success* — and derives the count at runtime so it cannot quietly drop back to `4xx`-only. It is per-guard (inherited like `serve.mjs`), needs no `watch.py` edit and no cross-language import, and carries no literal. **Its honest limit:** it guards refusal paths specifically; it does not detect a stale *success* status (`docktarget`'s `200`). R4 is the complement for those — the two together cover the family, and both are narrow.

**Survivor: R5**, landed concretely as a coverage assertion inside the
widened `health.mjs` (§4). R4 is recorded as the right tool for the
stale-value half and is *not* landed as a grep sweep — adopting it one
guard at a time is the `serve.mjs` precedent, and the next stale-value
fake that bites is where it earns its place.

## 4. The concrete deliverable — widen `health.mjs`'s two checks

The write-side block (`health.mjs:205-244`) gains a second refusal
scenario driven through a `202 {ok:false}` fake — the status the client
treats as success. The three invariants are asserted on it too:

- *a refused `202` says so, instead of nothing*;
- *a refused `202` never shows the answered state for a write that did not land*;
- *a rejected `202` keeps his text*.

A **coverage assertion derived at runtime** (R5) sits above them: the
guard counts the refusal statuses it drove and requires at least one
`2xx` and one `4xx`, so it cannot silently shrink back to `409`-only.
The existing `409` scenario is untouched and stays green.

**Red-proof (non-circular).** The production line whose change reds the
new checks is `watch.py:3576` (`if (!res || !res.ok)`). It is red
*against the current client*: `E5b` has not merged, so a `202` refusal
slips past `!res.ok`, the morph runs, the card becomes answered and the
text is cleared, and the new checks FAIL. Crucially, **this diff touches
only `health.mjs` (the fake)** — the red is produced against the
production client line as it stood before this diff, which is the
brief's "could your red have been produced against the code as it stood
before your diff?" test, passed. A green red-run here would be a
finding; the observed red is the correct, reported result, and the
guard is the instrument that flips green when `E5b` lands its client
fix. The measurement window is `MORPH_HOLD_MS` (`1250ms`); the check
samples at `~700ms`, inside the hold, before the live tick restores the
open state from `data.json`.

## 5. Convention (one line, where the next refusal guard will see it)

A refusal guard on a write path must drive the refusal on a status the
client treats as **success** (`2xx`) as well as one it treats as failure
— because the client branches on `res.ok`, and the moved contract is
always the `2xx` one. Stated in `health.mjs`'s header beside the
`route.fulfill` it already documents, which is the trigger the next
author of a refusal guard is certain to read.
