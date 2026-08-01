# Citation repair census — 2026-08-02 (#920)

## Verdict

Re-measured at `c5e2b30238f49e85d8e23a8648314462dba7377b`, before
planning or editing any cited document: **19 of 19 pinned occurrences are
false at `dc739001`**, not 12 of 19. The inherited figure counted only a
12-member symbol-bearing subset (and treated repeated tokens inconsistently),
not whether every pinned coordinate supports its sentence. All 19 coordinates
resolve, but every resolved region is unrelated to what its sentence claims.

This triggers #920's explicit close condition: *"If it does not reproduce,
that is the finding and this id closes."* No citation repair follows this
measurement commit.

The expectation is independent of the bad pin: for each historical sentence I
read the claim, then recovered the revision in which that sentence was authored
(`git blame ee98506c^`) or the revision the sentence itself names. I confirmed
the claimed content in that tree. The `dc739001` coordinate was used only as
the subject being judged.

## Re-runnable census

Run the block below from the repository root. It always prints its fixed
denominator (`examined=19`) and faults if an occurrence disappears or becomes
ambiguous. `false=0 examined=19` is therefore distinct from examining nothing.
The `needle` is claim-derived evidence in the independently recovered target;
it is not copied from `dc739001`.

```bash
python3 - <<'PY'
from pathlib import Path
import subprocess

# document, unique prose locator, old pin, supported replacement, evidence
ROWS = [
 ('.dreamwork/docs/briefs/547-composer-default-runmode-removal.md', 'Remove the `runModePicker(d)`', 'watch.py:4100 @ dc739001', 'watch.py:4100 @ 6edcf95b', 'runModePicker(d)'),
 ('.dreamwork/docs/briefs/547-composer-default-runmode-removal.md', 'sibling control at watch.py:4101', 'watch.py:4101 @ dc739001', 'watch.py:4101 @ 6edcf95b', 'posturePicker(d)'),
 ('.dreamwork/docs/briefs/548-bdinput-cap-binding.md', 'literal (`watch.py:3712', 'watch.py:3712 @ dc739001', 'watch.py:3712 @ e2acedf5', 'const BURN_LIMIT_CAP = 256;'),
 ('.dreamwork/docs/briefs/548-bdinput-cap-binding.md', '(256→168 — a pre-existing line', 'watch.py:3712 @ dc739001', 'watch.py:3712 @ e2acedf5', 'const BURN_LIMIT_CAP = 256;'),
 ('.dreamwork/docs/briefs/548-bdinput-cap-binding.md', '`max=` at watch.py:3931', 'watch.py:3931 @ dc739001', 'watch.py:3931 @ e2acedf5', 'max="${BURN_LIMIT_CAP}"'),
 ('.dreamwork/docs/briefs/562-chat-surface.md', 're-render idiom (see the comment', 'watch.py:4020-4027 @ dc739001', 'watch.py:4020-4027 @ 8b3c10cc', 'panel re-renders'),
 ('.dreamwork/docs/briefs/562-chat-surface.md', '**The count line is total-only.**', 'watch.py:4037-4040 @ dc739001', 'watch.py:4037-4040 @ 8b3c10cc', 'function chatList(d)'),
 ('.dreamwork/docs/handoffs/2026-07-29-0810-claude-to-grok.md', 'Relevant code: `setCardMode`', 'watch.py:4019-4021 @ dc739001', 'watch.py:4016-4021 @ c42ce90', 'function setCardMode'),
 ('.dreamwork/handoffs.md', '- **#614** → folded', 'watch.py:3654 @ dc739001', 'watch.py:3654 @ f4c3f3e8', 'WATCHED_MTIME_IGNORED ='),
 ('.dreamwork/handoffs.md', '- **#614** · landed', 'watch.py:3654 @ dc739001', 'watch.py:3654 @ 72d6fa65', 'WATCHED_MTIME_IGNORED ='),
 ('.dreamwork/handoffs.md', '- **#548** → folded', 'watch.py:3942 @ dc739001', 'watch.py:3942 @ 0f96b606', 'max="${BURN_LIMIT_CAP}"'),
 ('.dreamwork/handoffs.md', '- **#543** · landed', 'watch.py:4039 @ dc739001/4056', 'watch.py:4056 @ 3d186750', 'topic chats ·'),
 ('.dreamwork/handoffs.md', "`read_subagent_policy`'s docstring", 'watch.py:4050 @ dc739001', 'watch.py:4074-4082 @ 410c442d', 'def read_subagent_policy'),
 ('.dreamwork/handoffs.md', '`resolve_posture` -> POST /posture', 'watch.py:4135-4145 @ dc739001', 'watch.py:4135-4145 @ 410c442d', 'out["subagent_policy"]'),
 ('.dreamwork/handoffs.md', '- **#545** → folded', 'watch.py:4412 @ dc739001', 'watch.py:4412 @ 84d695d8', 'data-${kind}'),
 ('.dreamwork/lane-641-report.md', '`WATCHED_MTIME_IGNORED_SUFFIXES =', 'watch.py:4068 @ dc739001', 'watch.py:4174 @ 29bfd77d', 'WATCHED_MTIME_IGNORED_SUFFIXES = ("-shm",)'),
 ('.dreamwork/lane-645i5-report.md', '# REDPROOF: raw connect reintroduced', 'watch.py:3476 @ dc739001', 'temporary red-proof injection replacing 6641ad76:watch.py:3476 (restored before commit)', 'conn = db_core._connect('),
 ('.dreamwork/reviews-cx-session-2026-08-01.md', '`test_watch.py:13170-13207`', 'watch.py:3946-3974 @ dc739001', 'watch.py:3946-3974 @ 4e83d224', 'def apply_delta(base, delta)'),
 ('.dreamwork/reviews-cx-session-2026-08-01.md', '`file-formats.md:2172-2178`', 'watch.py:3999-4006 @ dc739001', 'watch.py:3999-4006 @ 4e83d224', 'def _data_json_response(entry, since)'),
]

def evidence(replacement, needle):
    if replacement.startswith('temporary red-proof injection'):
        rev, path, span = '6641ad76', 'watch.py', '3476'
    else:
        token, rev = replacement.rsplit(' @ ', 1)
        path, span = token.rsplit(':', 1)
    text = subprocess.check_output(['git', 'show', f'{rev}:{path}'], text=True)
    lo, *rest = map(int, span.split('-'))
    hi = rest[0] if rest else lo
    region = '\n'.join(text.splitlines()[lo-1:hi])
    return needle in region

false = unresolved = correct = 0
for doc, locator, old, replacement, needle in ROWS:
    lines = [line for line in Path(doc).read_text(encoding='utf-8').splitlines()
             if locator in line]
    if len(lines) != 1 or not evidence(replacement, needle):
        unresolved += 1
        print(f'UNRESOLVED {doc}: {old}')
    elif replacement in lines[0] and old not in lines[0]:
        correct += 1
    elif old in lines[0]:
        false += 1
    else:
        unresolved += 1
print(f'false={false} correct={correct} unresolved={unresolved} examined={len(ROWS)}')
raise SystemExit(0 if unresolved == 0 else 2)
PY
```

Initial output:

```text
false=19 correct=0 unresolved=0 examined=19
```

## Per-occurrence judgement

| document | token | prose claim | where it actually is | action |
|---|---|---|---|---|
| `briefs/547-composer-default-runmode-removal.md` | `watch.py:4100` | `runModePicker(d)` call | `6edcf95b:watch.py:4100` | documented; no repair because the re-measurement closes #920 |
| same | `watch.py:4101` | sibling `posturePicker(d)` control | `6edcf95b:watch.py:4101` | documented only |
| `briefs/548-bdinput-cap-binding.md` | `watch.py:3712` | `BURN_LIMIT_CAP` declaration | `e2acedf5:watch.py:3712` | documented only |
| same | `watch.py:3712` | same pre-existing declaration used for red-proof | `e2acedf5:watch.py:3712` | documented only |
| same | `watch.py:3931` | rendered `max=` binding | `e2acedf5:watch.py:3931` | documented only |
| `briefs/562-chat-surface.md` | `watch.py:4020-4027` | topic-chat re-render comment | `8b3c10cc:watch.py:4020-4027` | documented only |
| same | `watch.py:4037-4040` | `chatList` count line | `8b3c10cc:watch.py:4037-4040` | documented only |
| `handoffs/2026-07-29-0810-claude-to-grok.md` | `watch.py:4019-4021` | `setCardMode` | `c42ce90:watch.py:4016-4021` | documented only |
| custodial `handoffs.md` folded #614 | `watch.py:3654` | ignore-set missing `-shm` | `f4c3f3e8:watch.py:3654` | coordinator replacement below |
| custodial `handoffs.md` landed #614 | `watch.py:3654` | same ignore-set measurement | `72d6fa65:watch.py:3654` | coordinator replacement below |
| custodial `handoffs.md` #548 | `watch.py:3942` | rendered cap binding | `0f96b606:watch.py:3942` | coordinator replacement below |
| custodial `handoffs.md` #543 | `watch.py:4039` | `topic chats · N` panel copy | `3d186750:watch.py:4056` | coordinator replacement below |
| custodial `handoffs.md` #659 | `watch.py:4050` | `read_subagent_policy` docstring | `410c442d:watch.py:4074-4082` | coordinator replacement below |
| custodial `handoffs.md` #659 | `watch.py:4135-4145` | posture read-modify-write chain | `410c442d:watch.py:4135-4145` | coordinator replacement below |
| custodial `handoffs.md` #545 | `watch.py:4412` | `artifactRow` data attribute | `84d695d8:watch.py:4412` | coordinator replacement below |
| `lane-641-report.md` | `watch.py:4068` | `WATCHED_MTIME_IGNORED_SUFFIXES` | `29bfd77d:watch.py:4174` | documented only |
| `lane-645i5-report.md` | `watch.py:3476` | transient `_sabotage` injection | never committed; it temporarily replaced `6641ad76:watch.py:3476` | remove the false revision claim; documented only |
| `reviews-cx-session-2026-08-01.md` | `watch.py:3946-3974` | `compute_delta` / `apply_delta` contract | `4e83d224:watch.py:3946-3974` | documented only |
| same | `watch.py:3999-4006` | `_data_json_response` contract | `4e83d224:watch.py:3999-4006` | documented only |

## Coordinator-custodial replacements

These are exact substring replacements; I did not edit `handoffs.md`.

| context | exact old text | exact new text |
|---|---|---|
| folded #614 | `watch.py:3654 @ dc739001` | `watch.py:3654 @ f4c3f3e8` |
| landed #614 | `watch.py:3654 @ dc739001` | `watch.py:3654 @ 72d6fa65` |
| #548 | `watch.py:3942 @ dc739001` | `watch.py:3942 @ 0f96b606` |
| #543 | `watch.py:4039 @ dc739001/4056` | `watch.py:4056 @ 3d186750` |
| #659 docstring | `watch.py:4050 @ dc739001` | `watch.py:4074-4082 @ 410c442d` |
| #659 chain | `watch.py:4135-4145 @ dc739001` | `watch.py:4135-4145 @ 410c442d` |
| #545 | `watch.py:4412 @ dc739001` | `watch.py:4412 @ 84d695d8` |

## Campaign ruling

**Recommendation: run #920 and #847 as one corpus campaign, while preserving
separate counters for qualified-but-false and unqualified citations.** #847's
record says each item must be judged from what the prose claims, not repaired
mechanically; the 19 rows above require the identical operation. One pass avoids
first adding a plausible-but-wrong pin and later auditing it as a false pin.
A combined census should report both denominators so neither population can
degrade to zero invisibly. Because #920's filed count does not reproduce, close
#920 on this measurement and move any chosen repair work into that combined
#847 campaign rather than silently widening this task.

Relied-on ledger lines:

- #920: *"If it does not reproduce, that is the finding and this id closes."*
- #847: *"Any pass ... has to look at what the prose CLAIMS ... one at a time."*
- #921: *"It stops asserting the coordinate is correct at the pinned revision."*

## Red-proof results and limits

- **Direction 1, executed on the census's production manifest:** I replaced
  the independently recovered `6edcf95b` target for `runModePicker(d)` with
  the bad `dc739001` target. The expected target derives from the brief's prose
  claim plus the pre-certification authoring tree, not from the subject pin.
  The census exited 2 with the discriminating message
  `UNRESOLVED ... watch.py:4100 @ dc739001` and
  `false=18 correct=0 unresolved=1 examined=19`. `redproof.py restore` restored
  the report byte-for-byte; `cmp` used the exact `.orig` path printed by
  `redproof.py`, then the restored census again printed
  `false=19 correct=0 unresolved=0 examined=19`.
- **Direction 2, constructed and observed:** I changed the prose claim from
  `posturePicker` to the wrong `tintPicker` while applying the reviewed
  `watch.py:4101 @ 6edcf95b` citation. The census falsely reported
  `false=18 correct=1 unresolved=0 examined=19`. The file was restored with
  `cp` from the exact path printed by `lane_scratch.py` and verified by `cmp`.
  This is the honest limit: claim needles are a reviewed manifest, not a
  semantic parser. The same class includes blessing `watch.py` when the claim
  actually lives in `client/style.css`. The census proves reviewed decisions
  stay applied; it cannot replace the judgement that creates them.

No guard change, production change, or cited-document repair was assessed as
part of this close-on-non-reproduction outcome.

## Dogfood report

The filed `12 of 19` combined two denominators: 19 pinned occurrences but a
12-member symbol-selected subset, with duplicate citation tokens counted in
the former and effectively collapsed in the latter. The design's supporting
measurement was true about that subset (`0 of 12` nearby), but the task title
promoted it into an all-occurrence defect count. The re-measure-first/close-on-
non-reproduction rule caught this exactly. No additional tooling friction was
found; the snapshot paths printed by `redproof.py` and `lane_scratch.py` were
different as warned, and using each printed path made both `cmp` checks clean.
