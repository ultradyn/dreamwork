# Live #229 review-route UX review

**Task:** #272  
**Date:** 2026-07-26  
**Route:** `http://localhost:35111/review?p=threaded-topic-chats.html&q=…#229…`  
**Method:** isolated Playwright context; no interaction with the human's tabs; no POSTs or source edits.

## Evidence

| Capture | Viewport/output | Temporary path |
|---|---:|---|
| Desktop top | 1440×900 | `.dreamwork/review/evidence/review-route-272/desktop-top.png` |
| Desktop full | 2066×5174 | `/tmp/review-272-ux/desktop-full.png` |
| Desktop dock crop | `#qdock` | `.dreamwork/review/evidence/review-route-272/dock.png` |
| Mobile top | 390×844 | `.dreamwork/review/evidence/review-route-272/mobile-top.png` |
| Mobile full | 943×4272 | `/tmp/review-272-ux/mobile-full.png` |

The three focused captures are preserved in the repository; oversized full-page
captures remain ephemeral because the measured geometry and representative crops
carry the review findings without adding roughly 1.9 MB of redundant pixels.

## Measured geometry

### Desktop, 1440×900

- review document / iframe: approximately 1078×668; the iframe scrolls internally;
- dock: 261×5014, `position: sticky`, `overflow: visible`;
- composer top: approximately 5044 px;
- after outer `scrollY=400`, dock top is approximately -280 px: the dock is taller than the viewport, so sticky positioning cannot keep the action usable;
- six discussion rows and two textareas (global composer plus dock);
- one send control is approximately 26.2 px high, below the 44 px touch target.

### Mobile, 390×844

- iframe: 360×508, then the dock is stacked below;
- dock: 358×3583;
- composer top: approximately 4143 px;
- body scroll height: approximately 4272 px.

## Findings and scoped solutions

### Critical: the answer control follows the entire discussion wall

Every note/reply grows the dock above the response control. The control is more than 5k px down on desktop and 4k px down on mobile.

**Solution:** split the dock into:

1. a sticky identity/decision header;
2. an internally scrollable discussion region whose maximum height reserves space for header and composer;
3. a sticky composer footer.

The response surface must remain visible independently of discussion length.

### Critical: the decision and response surfaces are disconnected

The A–E approval prompt is deep inside the iframe artifact. The dock shows question prose and discussion but not the structured decision at the point of response.

**Solution:** add a dock decision strip containing the exact approval ask plus a `Jump to decision` bridge into an artifact `#decision` anchor. A later structured approval control may supplement free text, but identity and durable receipt semantics must be fixed first (#266/#263).

### High: dual scrolling and truncated artifact context

The multi-thousand-pixel artifact is constrained to a 668 px desktop / 508 px mobile frame while the outer page also scrolls.

**Smallest solution:** increase the usable iframe height and provide explicit `Open full artifact` and `Jump to decision` controls. Preserve iframe isolation required by #253; parent rendering is not the first increment.

### High: discussion lacks usable structure

Six YOU/LOOP turns are rendered as flat siblings. There is no collapse of earlier material, reply nesting, date grouping, or jump-to-latest behavior. Long pasted review text dominates the dock.

**Solution:** consume #254's conventional note/reply tree; pin the question and decision; show the latest two turns and place older turns behind the established atmospheric disclosure gesture.

### High: weak artifact/dock relationship, especially on mobile

Desktop columns do not share section state. On mobile, the discussion appears only after a short iframe preview, losing the “read and answer” relationship.

**Solution:** label the dock `Answering · docked from this review`. On mobile use Document/Discussion tabs or a sticky answer sheet; do not place a 3.5k-pixel discussion between the document and composer.

### Medium: competing text surfaces and weak target assurance

The global composer and dock composer compete. The full target title is not persistently visible while responding, which compounds #266's wrong-target failure.

**Solution:** de-emphasise or hide the global composer on review routes; keep the full stable dock identity in the sticky header; show explicit mode and target confirmation; enforce 44 px controls.

### Lower: accessibility and feedback

The dock textarea lacks an accessible label. Focus flow through the iframe and long dock needs explicit testing. Long loop follow-ups can visually resemble a terminal answer.

**Solution:** add an `aria-label`, skip-to-response link, cross-iframe focus guard, open/amended/awaiting-decision status chip, and quieter loop-follow-up styling. Verify reduced-motion transitions separately during implementation.

## Ranked program

1. Sticky dock footer composer plus internal discussion scroll.
2. Pinned stable target identity and decision prompt with jump-to-A–E.
3. Collapse and nest discussion through #254.
4. Mobile Document/Discussion tabs or answer sheet.
5. Taller iframe plus explicit full-artifact/decision navigation.
6. Accessibility, touch-target, and status-feedback hardening.

## Preserved strengths

- The dark Dreamwork aesthetic and artifact decision rail are coherent.
- The desktop two-column intent is sound once the dock becomes viewport-bounded.
- Authorship labels and timestamps are visible.
- Proposal-only status is visible in the artifact.
