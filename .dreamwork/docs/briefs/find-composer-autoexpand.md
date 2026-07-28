# Brief — find the composer auto-expand task

Repo: `ud-dreamwork`. **READ-ONLY in the main checkout. No worktree, no branch, change NO tracked file.**
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time, and this lane is read-only besides. Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

## The task

The human says: *"we had a task about making the input text box in the command composer autoexpand as the
user types."* Find it in `.dreamwork/tasks.md`.

The command composer is the dashboard control in `watch.py` that writes `.dreamwork/watch-events.log`
(`do now:` / `add-idea:` / `do-next:` lines). Search for the **behaviour**, not one phrase — it may be worded
as auto-grow, autosize, textarea height, grow-with-content, multi-line, expanding input, or described without
any of those words. Search **both** the `## Open` and `## Recently landed` sections: if it already landed,
that is the answer and it saves a duplicate dispatch.

**Use the production parser** — `import watch` and use `watch.parse_ledger` / `ledger_entries`, or
`python3 dev/ledger.py counts` for orientation. **Do not hand-roll a ledger parser and never split on the
string `## Recently landed`** — that string also appears in an *entry's prose*, so an unanchored split hits
the mention and silently truncates the file's open half. Five hand-rolled ledger parsers have been wrong here;
use `^## Recently landed$` anchored if you must locate sections yourself.

## Report — keep it short, this is a lookup

1. **The id**, or *"no such entry exists"* if that is the truth — say so plainly rather than nominating the
   nearest thing. If the nearest thing is close but not it, name it and say why it is not.
2. **Whether it is open or already landed**, and if landed, the sha.
3. **The entry's full text**, verbatim.
4. **Any sibling entry that would collide with it** — anything else open that touches the composer or
   `watch.py`'s client, since the next lane needs to know what it can own.
5. **Do not implement it.** Another subagent does that. Do not create a worktree or edit anything.
