# Contextual review annotations (#253)

## Recommendation

Adopt **A: a lightweight annotation sidecar whose selections may be promoted once into a #229 topic chat**. It preserves a lifecycle for each mark without making every mark expensive. **B, one chat per annotation**, creates chat-list pollution and worker/context cost before discussion is warranted. **C, one document-level review chat**, is quieter but loses per-mark identity, resolution and orphan handling.

This is a proposal, not implementation authority. The existing review view deliberately embeds the self-contained artifact in a style-isolated iframe and optionally docks its originating question beside it (`watch.py:1946-1965`, `buildReview`; raw delivery is confined to `.dreamwork/review` at `watch.py`, `/reviewraw`). The current dock is responsive—sticky on wide layouts and static below 900px (`watch.py:637-642`, `.qdock`)—but it is question-level, not selection-level.

## Model and truth boundaries

A sidecar record should contain only shallow operational truth:

- annotation id, kind (`question`, `task`, or `update-request`), author/time and state;
- artifact identity: content hash/version;
- anchor: heading path, paragraph ordinal, normalized selected quote, surrounding normalized context hash;
- optional promoted-chat id and backlinks; resolution/orphan metadata.

On reopening, first match the same artifact version; after edits, search the same heading path, then fuzzy-match the normalized quote using context to disambiguate. If no unique credible match exists, mark it **orphaned** and show recovery choices (reattach, retain as detached, export, delete). Never silently relocate a mark.

The sidecar is the shallow annotation truth. A promoted #229 chat is the deep conversational truth. Promotion is one-time and atomic: seed the chat with artifact/anchor provenance and the annotation, then store reciprocal links. Further discussion occurs only in that chat; this prevents two live threads from forking. This follows #229's fresh-worker-per-turn, append-only transcript model (`.dreamwork/review/threaded-topic-chats.html:98-101`) and its #235 precedent that promotion links back rather than growing a second live thread (`threaded-topic-chats.html:441-447`). Promoted runs should inherit #236's compact file/tool provenance index, not hidden reasoning or full tool bodies (`threaded-topic-chats.html:443-447`), and generated views should use the #239 resolver rather than a private theme (`threaded-topic-chats.html:445-447`), including #256's host-background-hook constraint (ledger #256).

## Authority and task semantics

A `question` remains inert until promoted; no worker is dispatched from the sidecar. A `task` or `update-request` immediately mints a normal **human-origin** ledger task with an annotation backlink, so it enters ordinary prioritisation, ownership and recovery rather than an annotation-only queue. `update-request` is a typed intent, not permission to edit. Worker dispatch occurs only through an approved promoted chat or normal coordinator authority.

This separation matches the repository's directional semantics: open `answers.md` entries are human-authored questions to the dreamer and resolution preserves the original question (`file-formats.md:20-45`); question notes/answers are chronological authored sub-bullets (`file-formats.md:58-66,86-108`). Annotation sidecars should not impersonate either grammar. #253 itself requires provenance, task authority, privacy, accessibility and recovery (ledger #253); #254 separately fixes the misleading sibling rendering of human Note and loop Answer evidenced by `review-note-reply-unclear.png` (ledger #254). Complete #254 first so annotation UI is not designed atop ambiguous authorship.

## UI boundary

Keep the iframe isolated. Recommended integration is a **narrow, versioned `postMessage` bridge**: trusted review content reports selection text plus structural hints; the parent validates origin/source, size and schema, computes/persists the anchor, and owns a mutable side rail. The parent can therefore apply dashboard accessibility, responsive layout, motion and privacy rules without injecting application state into arbitrary artifacts.

The alternative is in-page annotation rendering. It makes geometry and highlights easier, but couples every generated artifact to mutable UI/runtime code, weakens style/security isolation, complicates offline/public exports and risks divergence from #239/#256. The bridge is the smaller contract. It must not accept commands, HTML, file paths or worker authority from the child.

On mobile or for keyboard/screen-reader users, offer “Add annotation” followed by an accessible quote/heading picker and editable context, rather than requiring pointer selection. The rail becomes a full-width sheet with focus return and announced state changes. Preserve a source-list fallback when highlights cannot be placed.

## Privacy, export and recovery

Default sidecars should be gitignored local data, consistent with runtime ephemera being explicitly gitignored because committed live state becomes false (`file-formats.md:357-365`). Export must be explicit and produce a reviewable, redacted Markdown/JSON artifact; promotion or task minting should disclose exactly which quote/context crosses into durable project history. Recovery must retain orphaned records, backlinks and failed/pending promotion intent, and allow deterministic reconciliation after restart. Exact submitted human words deserve special care: the existing submission log is the verbatim witness while rendered files may reflow text (`file-formats.md:253-296`).

## IGC matrix (binary goals)

| Idea | Per-mark lifecycle | Low chat cost/noise | Durable conversation | Edit recovery | Isolation/privacy | Result |
|---|---:|---:|---:|---:|---:|---|
| A. Sidecar + optional promotion | PASS | PASS | PASS | PASS | PASS | **Not refuted** |
| B. Chat per annotation | PASS | FAIL | PASS | PASS | PASS | Refuted: pollution/cost |
| C. Document-level chat | FAIL | PASS | PASS | FAIL | PASS | Refuted: marks lose lifecycle |

## Staging

1. Finish #254 and verify authorship/reply causality.
2. Review this proposal; make no sidecar or worker changes yet.
3. Add gitignored sidecar storage and anchor re-resolution, with no worker dispatch.
4. After #229 is approved, add one-time promotion and reciprocal backlinks.
5. Add immediate normal-ledger task minting for `task`/`update-request`.
6. Exercise edit re-resolution, ambiguous/orphan recovery, mobile/a11y fallback, explicit export and restart reconciliation.

## Risks and open decisions

Risks are malicious/noisy iframe messages, selection geometry drift, quote collisions, accidental durable disclosure, duplicate promotion/task minting after retries, backlink divergence, and inaccessible selection-only interaction. Open decisions include sidecar filename/schema, fuzzy-match threshold, export redaction UX, lifecycle states, and whether static public artifacts disable the bridge entirely.

**Best human clarifying question:** Approve the recommended parent-owned side rail with a narrow iframe `postMessage` selection bridge, rather than rendering annotation controls inside each artifact?
