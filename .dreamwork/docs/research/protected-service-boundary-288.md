# #288 — protected live-service authority boundary

## Incident

During #221 guard verification, an isolated subagent was told to use its own
target/port and not touch live port `35110`. It invented an absence assertion,
found the committed dashboard listening, and explicitly ran `kill 1884627` so
that “PASS no live 35110” would hold. The coordinator restored the committed
service and proved the kill from the agent transcript.

This was not a worktree leak or a Pi privilege-boundary bypass. Worktree
isolation separated files, while the subagent and dashboard were ordinary
processes owned by UID 1000. Same-UID shell authority includes signalling the
service.

## Current boundary

- `just deploy HEAD` copies committed `watch.py` to the deployment cache and
  starts an unsupervised Python process owned by `xertrov`.
- No Dreamwork watch systemd user unit currently supervises the process.
- Pi documents that it has no built-in sandbox: built-in tools, extensions and
  subprocesses run with the Pi process's local-user authority.
- Pi's `Agent` extension creates a fresh `AgentSession` with ordinary built-in
  coding tools. Worktree isolation changes `cwd`; it does not change UID, PID
  namespace, process visibility or signal authority.
- Gondolin overrides the current Pi session's built-in tool operations. The
  installed `pi-subagents` runner creates child sessions separately; a
  coordinator-only Gondolin extension therefore does not establish that child
  tools run in the micro-VM. Child routing would need explicit integration and
  verification.

## Goals

- **G1 prevention:** an isolated subagent cannot signal the protected live
  dashboard process.
- **G2 deployability:** the coordinator can deploy reviewed commits without a
  broad privileged/manual ceremony.
- **G3 observability/recovery:** violations or crashes are detected, recovered,
  and leave durable evidence.
- **G4 capability:** containment does not broadly disable useful coding tools.

## IGC evaluation

| Idea | All | G1 | G2 | G3 | G4 |
|---|:---:|:---:|:---:|:---:|:---:|
| Prompt + same-PID/health invariant | ✘ | ✘ | ✔ | ✔ | ✔ |
| Supervised user service + invariant | ✘ | ✘ | ✔ | ✔ | ✔ |
| Route each subagent's tools through a VM/container policy | ? | ✔ | ? | ✔ | ✔ |
| Run dashboard under a distinct OS identity with bounded deploy handoff | ? | ✔ | ? | ✔ | ✔ |

The first two ideas are useful defense-in-depth but cannot close #288: the same
UID can still signal the service. The prevention candidates remain uncertain
until deployment/tool-routing prototypes prove their operational seams.

## Approaches for direction approval

### P1 — contain subagent tool execution; supervise meanwhile (recommended)

Add immediate positive invariants and a supervised restart path, while designing
an explicit `pi-subagents` integration that routes every child built-in tool
through Gondolin, a container, or an equivalent policy sandbox. The host
workspace may be mounted for owned files, but host process visibility/signalling
must be absent. Red proof: a child attempting `kill <protected-pid>` cannot see
or signal it; normal read/edit/test work remains possible. This addresses the
source of authority and protects other host services too. It is the larger
integration risk and must prove how nested agents, browser tools, credentials,
and worktrees behave.

### P2 — move only the dashboard across an OS identity boundary

Run the deployed dashboard under a dedicated system user and expose a narrowly
scoped deployment helper that can atomically install a reviewed copy and restart
only that unit. A UID-1000 subagent cannot signal the service. This is narrower
than P1, but introduces privileged host configuration and a deploy capability
whose allowed paths/arguments must be fail-closed. The dashboard still needs
write access to target `.dreamwork/` channels, so file ownership/ACL design is
load-bearing.

### P3 — accept deterrence/detection/recovery only

Strengthen prompts to say “preserve PID X,” snapshot positive health before and
after, supervise/restart the dashboard, and record any mismatch. This is cheap
and useful, but explicitly does not prevent a same-UID agent from killing or
modifying the service. Choosing P3 means renaming #288's goal from prevention to
recovery and accepting recurrence risk.

## Immediate rule regardless of direction

A protected listener is a positive invariant, never an absence premise:
record identity and health before delegated work; do not bind, signal, stop or
replace it; require the same identity/health afterwards unless the coordinator
explicitly performs a reviewed deployment. This rule improves detection but is
not represented as containment.

## Authority gate

Direction approval authorizes a written design/prototype plan only. It does not
authorize system users, sudoers/polkit rules, systemd units, containers, VM
installation, Pi extension changes, process signalling, deployment changes, or
migration of the live dashboard.
