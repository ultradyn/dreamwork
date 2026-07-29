> **Bundled reference — vendored, not authored here.** The coordinator
> half of the `subagent-protocols` handshake, copied from that skill so a
> dreamwork install carries the channel without depending on the host's
> skill set. Upstream source:
> `~/.claude/skills/subagent-protocols/for-coordinators.md`, sha256
> `58f87ca66b6f19dfbc894c196cf5679bf1a579956c40b59a8fa6f14267ed7b5c`
> (2026-07-29). Same staleness story as
> `subagent-protocols-for-subagents.md`: the handshake is small and
> stable; re-sync on the docs-freshness rotation if upstream changes the
> protocol itself, and bump the sha. One deliberate deviation from
> upstream: the prompt snippet's path points at the vendored subagent
> half rather than a host skill path; the body is otherwise verbatim.
> The subagent half lives in `subagent-protocols-for-subagents.md`.

# For Coordinators

Follow this when you are dispatching subagents and want a clean startup handshake.

## Before Dispatching

Create your append-only coordinator inbox, for example `~/.cache/agent-comms/<repo>/coord-inbox.md`, creating `~/.cache/agent-comms/<repo>/` if needed. Start an inbox monitor on it, such as `Monitor` or a background watch running `watch-file.sh <your-inbox>`, so subagent messages arrive as events. Monitor events are background events, not user replies.

## Add To Every Dispatch Prompt

- The absolute path to your inbox file, plus a one-line instruction to send the startup handshake there.
- An instruction to read this skill's `for-subagents.md` and follow it, or inline the startup steps if the subagent cannot read the file.
- Tell the subagent to use the inbox files as the channel, not a flaky broker.

Prompt snippet:

```text
Parent inbox: /home/me/.cache/agent-comms/<repo>/coord-inbox.md. Send your startup handshake there before working. Read <skill-dir>/subagent-protocols-for-subagents.md and follow it. Use the inbox files for durable comms, not a direct messaging broker.
```

## Interpret Startup

Read each startup handshake from your inbox:

- If the subagent reports `background-monitor: yes` and `watching-inbox: yes` with an inbox path, you have two-way streaming; append to that inbox to reach it mid-task.
- Otherwise communication is one-way; the subagent can report to you, but you cannot push mid-task instructions reliably.

Record each subagent id and inbox path before relying on replies.

## Teardown

Stop the inbox monitor when the subagent finishes. Leave the inbox files in place as the transcript.
