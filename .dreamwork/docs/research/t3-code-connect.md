# T3 Code Connect at `5719e8a`

**Revision:** [`5719e8ac4020dda0e375ef61d044b61f55a0df8a`](https://github.com/pingdotgg/t3code/tree/5719e8ac4020dda0e375ef61d044b61f55a0df8a)  
**Scope:** first-party repository source and docs at that revision only.

## What Connect is

T3 Connect is T3 Code's optional, account-mediated way to **mesh devices around T3 execution environments**. Its onboarding asks the user to publish the current environment and then connect other devices; the starting file is only persistence for an account's “Don't show this again” choice for that post-sign-in wizard ([onboarding state, lines 3–15](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/apps/web/src/cloud/connectOnboarding.ts#L3-L15); [dialog explanation, lines 33–40](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/apps/web/src/components/cloud/ConnectOnboardingDialog.tsx#L33-L40), [steps, lines 219–230](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/apps/web/src/components/cloud/ConnectOnboardingDialog.tsx#L219-L230)).

It is **not** a separate coding-agent protocol or hosted agent runtime. A selected Connect environment is registered as an ordinary relay connection target ([environment list and registration, lines 48–108](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/apps/web/src/components/cloud/CloudEnvironmentConnectList.tsx#L48-L108)); execution remains in one T3 server, which owns providers, terminals, projects/threads, filesystem, git, and processes ([remote architecture, lines 24–55](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/architecture/remote.md#L24-L55)).

## Transport, deployment, and authentication

- **Data path:** clients continue to use T3 Code's normal HTTP/WebSocket server boundary. A tunnel is another `AccessEndpoint`, not another environment or transport protocol ([tunneled access, lines 219–241](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/architecture/remote.md#L219-L241)).
- **Publishing:** the environment host runs a managed, pinned `cloudflared`; the runtime starts `cloudflared tunnel run` with a connector token in `TUNNEL_TOKEN` and supervises it ([runtime setup, lines 32–49](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/apps/server/src/cloud/ManagedEndpointRuntime.ts#L32-L49), [launch/supervision, lines 208–243](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/apps/server/src/cloud/ManagedEndpointRuntime.ts#L208-L243)). The relay is separately deployed and uses a retained PlanetScale database; fresh source builds omit Connect unless Clerk/OAuth/relay public configuration is supplied ([configuration and relay deployment, lines 9–55](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/cloud/t3-connect-clerk.md#L9-L55)).
- **Account auth:** web, desktop, and mobile share one Clerk application. Relay JWTs come from the configured `t3-relay` template with audience `t3-code-relay` ([lines 1–5](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/cloud/t3-connect-clerk.md#L1-L5)). Headless hosts use a separate public OAuth client with PKCE and no client secret; OAuth is directly with Clerk, while the relay validates the bearer token when managing a link ([lines 57–73](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/cloud/t3-connect-clerk.md#L57-L73)).
- **Lifecycle:** `t3 connect login/link/status/unlink/logout` manages durable exposure intent. `link` can install `cloudflared` and does not require a running server; the next `t3 serve`/`t3 start` reconciles the link and launches the tunnel ([lines 75–99](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/cloud/t3-connect-clerk.md#L75-L99)).
- **Environment auth remains relevant:** the remote architecture requires explicit authentication for remote/public environments and treats tunnel exposure as insufficient by itself ([security model, lines 380–398](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/architecture/remote.md#L380-L398)). Thus Clerk/relay identity handles Connect account/link discovery; it should not be read as replacing the environment's own authenticated T3 server session.

## Capabilities

Connect provides:

1. managed reachability for a T3 server behind NAT or without inbound ports;
2. account-scoped discovery and connection of published environments from another web, desktop, or mobile client;
3. optional publication of agent-activity summaries for mobile push notifications and Live Activities ([the two publish controls, lines 354–375](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/apps/web/src/components/cloud/ConnectOnboardingDialog.tsx#L354-L375)); and
4. through the connected **T3 server**, the normal T3 capabilities: provider/model state, projects, threads, terminals, filesystem, git, and process runtime ([execution-environment ownership, lines 61–77](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/architecture/remote.md#L61-L77)).

The activity publication option is status/notification plumbing, not evidence of an arbitrary interactive terminal-stream API.

## Difference from general T3 Code web/remote mode

General remote mode is the broader architecture: a client may reach a T3 server by direct LAN/private/public WS/WSS, a user-operated tunnel, or desktop-managed SSH launch plus port forwarding ([access methods and direct access, lines 193–218](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/architecture/remote.md#L193-L218), [SSH, lines 243–265](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/architecture/remote.md#L243-L265)). Hosted web pairing is only bootstrap: the browser connects directly to the supplied backend; the hosted app does not proxy HTTP or WebSocket traffic ([hosted pairing constraints, lines 156–178](https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/docs/architecture/remote.md#L156-L178)).

**Connect is one managed product path inside that model:** Cloudflare-backed reachability plus Clerk account discovery/linking and optional activity delivery. It does not alter the T3 server execution boundary or introduce a general external-agent integration protocol.

## Implications for dreamwork #201 / #202

- **#202:** “T3 Connect” now resolves precisely: it is a T3 Code feature, not a standalone protocol to implement in dreamhub.
- **Connect alone does not implement #201.** Connect publishes/discovers a **T3 server**. The complete T3 Code application supplies its own UI and control over sessions owned by that server.
- A **link-out/integration** direction is coherent and much smaller: let T3 Code own agent UI/control and have dreamhub point users at the relevant T3 environment. Connect matters only when that environment needs cross-device managed reachability.
- A **dreamhub-native herdr path** remains distinct: #201 concerns adopting an already-running herdr PTY, streaming its terminal state, injecting input, and preserving dreamhub's localhost/per-target constraints. No examined Connect source defines an API for arbitrary PTYs, ANSI frames, keyboard injection, or herdr's Unix-socket NDJSON protocol.
- Therefore “T3 Code already is #201” is too broad. **T3 Code overlaps #201 at the product outcome; Connect itself is reachability/discovery, not the streaming/control substrate.** The choice is principally build dreamhub-native control versus integrate/link out to the larger T3 Code system.
- The planned herdr `/compact` control increment remains useful under either choice because it tests dreamhub's own control path without committing to terminal emulation.

## Unresolved unknowns

- No supported revision-pinned deep link was established for opening a particular environment, project, thread, or agent session.
- No public embed/extension API for placing T3 Code UI inside dreamhub was established.
- No source inspected establishes that T3 Code can adopt an already-running, herdr-managed PTY rather than launching and owning its own provider session.
- Relay retention beyond the noted database, service availability/SLA, pricing, and long-term hosted-service guarantees are not specified by the cited revision.
- The exact boundary between Clerk/relay credentials and the connected environment's session-token exchange would need a narrower protocol trace before implementing an automated link-out or handoff.
