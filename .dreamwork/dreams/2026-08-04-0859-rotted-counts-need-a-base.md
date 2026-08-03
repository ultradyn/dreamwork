# 2026-08-04-0859 — a count is only precise when its base is part of the claim

## The decision

Task #1209 offered three remaining brief-premise families. The tempting F3
guard — require dates or SHAs on rule citations — exposes age but cannot prove
that a ruling remains live, and it rejects correct undated citations. Forbidding
mutable ledger fields has the same false-refusal defect. The observed F4 count
has a narrower mechanical subject: `lint.py`'s numeric `lesson citations` WARN
rows at the generation Base SHA.

| Rival | All | F3 | F4 | F5 | Refuses correct? |
|---|:---:|:---:|:---:|:---:|:---:|
| date/SHA on rule citations | ✘ | partial | — | — | yes |
| derive and compare `lesson citations` rows | ✔ | — | partial | — | no |
| forbid mutable ledger fields in heads | ✘ | — | — | ✔ | yes |

The surviving rival derives the exact lint population from the generation SHA
and refuses only a mismatch. A correct count still generates, so specificity is
preserved. Quoted and fenced stale examples are evidence rather than live
claims and stay generatable.

## What remains

This closes only the observed F4 subtype, not arbitrary authored counts. F3
(a relaxed rule quoted as live) and F5 (mutable field restatement) remain open.
The rule-citation parser problem is sharper than it first appears: syntax can
identify a citation, but not whether the surrounding sentence invokes the rule
or merely quotes a bad invocation as evidence.
