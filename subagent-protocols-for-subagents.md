> **Bundled reference — vendored, not authored here.** The subagent half
> of the `subagent-protocols` handshake, copied from that skill so a
> dreamwork install carries the channel without depending on the host's
> skill set (a machine without `subagent-protocols` installed still has
> the protocol). Upstream source:
> `~/.claude/skills/subagent-protocols/for-subagents.md`, sha256
> `3d658e79509e420eb4c8504e34c6cb9471a1eb3e7bacca4aae1f0d857365af06`
> (2026-07-29). **Staleness story:** the protocol is a small, stable
> handshake (append-only inbox files, a startup message, id-prefixed
> lines), so a drifted snapshot is low-risk; re-sync this file during the
> docs-freshness maintenance rotation if upstream changes the handshake
> itself (not on any edit), and bump the sha above. One deliberate
> deviation from upstream: the `watch-file.sh` reference names the copy
> bundled beside this file; the body is otherwise verbatim. The
> coordinator half lives in `subagent-protocols-for-coordinators.md`;
> the dispatch-time wiring is in `SKILL.md`'s Subagents section.

# For Subagents

Follow this when another agent dispatched you and gave you the parent inbox path.

## Startup

1. If you have a background-monitor tool that can stream new lines from a file as events, create your own append-only inbox file, for example `~/.cache/agent-comms/<repo>/<your-id>-inbox.md`; create `~/.cache/agent-comms/<repo>/` if needed, then start a monitor watching your inbox. If you have no such tool, skip this step; you cannot receive mid-task messages and will only report at the end.
2. Append a startup message to your parent inbox file containing exactly:
   - that you have started
   - whether you have a background-monitor tool
   - whether you are watching your own inbox, and if so the exact path of your inbox

Example:

```text
[<your-id>] started; background-monitor: yes; watching-inbox: yes; inbox: /home/me/.cache/agent-comms/<repo>/<your-id>-inbox.md
```

## Channel Rules

- Treat inbox files as append-only transcripts.
- Prefix every line you append with your id, for example `[<your-id>] ...`.
- To reach the coordinator, append to the parent inbox path from your dispatch prompt.
- If you set up your own inbox, read coordinator replies from that file via your monitor.
- `~/.cache/agent-comms/<repo>/` is the shared location (`<repo>` namespaces inboxes per project); `watch-file.sh <file>` tails a file's new lines as a monitor command (bundled beside this file as `subagent-protocols-watch-file.sh`).
- Direct messaging brokers such as c2c or message-to-coordinator may be unreliable; the inbox files are the durable channel.
