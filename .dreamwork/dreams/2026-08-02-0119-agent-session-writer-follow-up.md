# Agent-session writer follow-up

The automatic writer reclassifies `agent_session` as derived by the ordinary
cwd `status-sync`, but three existing contract surfaces still describe the old
manual, author-owned design: `client_env.py`, `initialization.md`, and
`file-formats.md`. They were outside this lane's owned files, so this lane did
not edit them. They should be reconciled when the coordinator folds #858;
otherwise the prose will direct agents to keep performing the convention this
writer replaces.

The standing red-proof example also shows `begin <path>` without the now-required
independent `--expectation` source. This task's head corrected it, and the tool
correctly refused the first final check after that expectation changed, but a
lane receiving only the boilerplate would lose a round trip at proof time.
