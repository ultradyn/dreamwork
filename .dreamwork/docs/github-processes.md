# GitHub shape — ultradyn/dreamwork

Discovery doc for the `ud-dreamwork-github` plugin (loaded 2026-07-25).
The loop's map for acting native on this repo. Surveyed 2026-07-25.

| Fact | Value |
|---|---|
| Remote | `git@github.com:ultradyn/dreamwork.git` (ssh), single remote `origin` |
| Visibility | Private |
| Default branch | `master` |
| Issues | Enabled, none open — the repo has never had one |
| Pull requests | None; history is direct commits to `master` |
| CI | None — no `.github/` directory at all |
| Branch protection | None (direct pushes to `master` are how it works today) |
| Labels | GitHub's defaults only, untouched (bug, documentation, duplicate, enhancement, good first issue, help wanted, invalid, question, wontfix) |
| `gh` auth | Account XertroV, ssh for git operations |

## Conventions the loop should follow

Nothing here is inherited from other contributors — this repo has only
ever had one author, so its conventions are the loop's own:

- **Commit subjects** are `dreamwork: <what changed>` for skill
  behaviour, `dreamwork(maintain:<item>): ...` for maintenance passes,
  and a bare area prefix (`watch:`, `review:`, `ledger:`, `docs:`) for
  everything else. Bodies explain *why*, in prose.
- **Task references** use the loop's own ledger ids (`#91`), not GitHub
  issue numbers. That matters here: GitHub would linkify `#91` as issue
  91 in its web UI. Until the repo has real issues the collision is
  theoretical; if it ever gets them, either the ledger switches prefix
  or commit bodies stop bare-referencing ids.
- **No PR flow** yet. If one starts, it needs `open-pr` authority in
  DREAMWORK.md first.

## Authority

None granted — the plugin is read-only here (DREAMWORK.md Plugins).
It watches and captures; it does not comment, push, open PRs, or merge.
Pushing the repo itself is a separate, human-granted permission (session
wrap and on ask) exercised by the loop, not by the plugin.

## Gaps worth knowing

- No CI means no external verification signal: the project's own test
  suite, run locally every increment, is the whole safety net.
- No issue templates or labels-in-use means a gh-sourced task's `type`
  cannot be label-informed yet; it will have to be read from the text.
