"""Tests for `client_env.py` — #665.

THE FALSE GREEN THIS FILE IS BUILT AGAINST, named up front because it is the
shape that makes a test file like this worthless: **a test that passes because
it read the env var the test itself set.** Hand `identify()` a dict containing
`CLAUDE_CODE_SESSION_ID` and assert the session id comes back, and the test
passes against a `client_env` that never consults the registry at all — a bare
`return {"session_id": env.get("CLAUDE_CODE_SESSION_ID")}` satisfies it
completely. It proves the string was plumbed, and nothing about where the
string came from. It was CONSTRUCTED and RUN during this lane (see the report),
and every state test below is therefore paired with a binding test in
`TestTheRegistryIsTheOneHome`, which patches `CLIENTS` and so can only pass if
the production registry is what actually runs.

Every test names the production line whose reversion reds it.
"""
import ast
import contextlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import client_env
import status_sync


HERE = Path(__file__).resolve().parent

# A fixed clock, so `recorded_at` never makes a test flake or depend on the
# machine's zone.
CLOCK = datetime(2026, 7, 31, 19, 30, 0, tzinfo=timezone.utc)

# A synthetic registry. Its variable names are DELIBERATELY not any real
# client's: a test that used the real names could pass against a hand-rolled
# reader that ignores the registry, which is the whole failure this file is
# built against.
FAKE = client_env.Client(
    name="fakeclient",
    detect=("FAKE_CLI",),
    session_id_var="FAKE_SESSION",
    subagent_var="FAKE_CHILD",
)
# A measured client that genuinely has no session-id variable — the case his
# open question asks about, and the shape a future client will need.
IDLESS = client_env.Client(
    name="idlessclient",
    detect=("IDLESS_CLI",),
    session_id_var=None,
    subagent_var=None,
)


def _target(tmp_path: Path, status: dict | None = None) -> Path:
    dw = tmp_path / ".dreamwork"
    dw.mkdir(exist_ok=True)
    if status is not None:
        (dw / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    return tmp_path


def _status(tmp_path: Path) -> dict:
    return json.loads((tmp_path / ".dreamwork" / "status.json").read_text())


# ── the four states, from the data alone ─────────────────────────────────
#
# Production lines: `identify`'s branches. Collapsing any of them to a single
# "unknown" value reds the corresponding test here.

class TestIdentifyStates:

    def test_resolved_client_reports_id_and_unknown_subagent_for_claude_code(self):
        # #678 (measured 2026-07-31): nothing in claude-code's environment
        # discriminates a subagent from the main agent. The old registry set
        # `subagent_var='CLAUDE_CODE_CHILD_SESSION'`, but that variable is
        # present in BOTH roles (coordinator AND a real subagent), so it
        # reported `is_subagent: true` for the main agent — the exact
        # confusion the field was built to prevent. The registry now records
        # `None`, so the bit is `None` (unknown) for this client rather than
        # a confident boolean that is wrong.
        rec = client_env.identify(
            {"CLAUDECODE": "1",
             "CLAUDE_CODE_SESSION_ID": "3a19e737-cb3f-4dde-8304-3241ac374cdb",
             "CLAUDE_CODE_CHILD_SESSION": "1"})
        assert rec["client"] == "claude-code"
        assert rec["session_id"] == "3a19e737-cb3f-4dde-8304-3241ac374cdb"
        assert rec["is_subagent"] is None
        assert "note" not in rec, "a resolved record explains nothing"

    def test_coordinator_role_is_also_unknown_not_measured_false(self):
        # A coordinator's environment carries the SAME markers a subagent's
        # does (CLAUDE_CODE_CHILD_SESSION=1 is present here too), so with
        # `subagent_var=None` the bit stays `None`. It must not collapse to
        # `False` (measured-not-a-subagent): that is the false confidence #678
        # is about, and `None` (unknown) is the honest state.
        rec = client_env.identify(
            {"CLAUDECODE": "1",
             "CLAUDE_CODE_SESSION_ID": "abc",
             "CLAUDE_CODE_CHILD_SESSION": "1"})
        assert rec["is_subagent"] is None

    def test_unknown_client_records_absent_with_a_reason(self):
        rec = client_env.identify({"PATH": "/usr/bin", "HOME": "/home/x"})
        assert rec["client"] is None
        assert rec["session_id"] is None
        assert rec["is_subagent"] is None
        assert "no known client marker" in rec["note"]

    def test_client_with_no_session_var_records_null_never_a_guess(self,
                                                                   monkeypatch):
        """His open question, answered in the honest direction.

        A client that exposes no session-id variable records `null` and says
        so — the `#613` `system_prompt` discipline (never in the transcript,
        so rendered absent rather than invented). The failure this forbids is
        a plausible-looking inferred id that a reader would then trust.
        """
        monkeypatch.setattr(client_env, "CLIENTS", (IDLESS,))
        rec = client_env.identify({"IDLESS_CLI": "1"})
        assert rec["client"] == "idlessclient"
        assert rec["session_id"] is None
        assert "exposes no session-id env var" in rec["note"]
        # And the subagent bit is `None`, not `False`: this client has no
        # signal, which is not the same as a measured "not a subagent".
        assert rec["is_subagent"] is None

    def test_declared_var_missing_from_env_is_reported_as_an_anomaly(self,
                                                                     monkeypatch):
        # The registry says this client HAS the var; the environment does not
        # carry it. That is a different fact from "the client has none", and
        # a single "unknown" would hide a registry that has gone stale.
        monkeypatch.setattr(client_env, "CLIENTS", (FAKE,))
        rec = client_env.identify({"FAKE_CLI": "1"})
        assert rec["session_id"] is None
        assert "does not carry it" in rec["note"]

    def test_empty_session_id_is_not_a_session_id(self, monkeypatch):
        monkeypatch.setattr(client_env, "CLIENTS", (FAKE,))
        rec = client_env.identify({"FAKE_CLI": "1", "FAKE_SESSION": "   "})
        assert rec["session_id"] is None
        assert "set but empty" in rec["note"]

    def test_ambiguous_markers_refuse_rather_than_pick_one(self, monkeypatch):
        """The child-harness ceiling, made safe rather than papered over.

        A harness launched as a child of another inherits the parent's
        markers. When two registry rows match at once the answer is "I cannot
        tell", and `status_sync`'s own rule applies: "I could not tell" and a
        confident answer must not be the same value.
        """
        monkeypatch.setattr(client_env, "CLIENTS", (FAKE, IDLESS))
        rec = client_env.identify({"FAKE_CLI": "1", "IDLESS_CLI": "1"})
        assert rec["client"] is None
        assert "ambiguous" in rec["note"]
        assert "fakeclient" in rec["note"] and "idlessclient" in rec["note"]


class TestTheSessionIdCannotIdentifyALane:
    """#652's measured trap + #678's correction, pinned together.

    Every concurrent lane is an Agent-tool subagent of ONE CLI process and
    inherits the SAME `CLAUDE_CODE_SESSION_ID` — #652's measured trap, which
    still holds. What no longer holds is that anything SEPARATES them: #678
    measured that `CLAUDE_CODE_CHILD_SESSION` (the registered separator) is
    present in BOTH roles, so a coordinator and a lane now produce
    byte-identical records. A future change that re-introduces a working
    discriminator reds the last assertion here.
    """

    def test_lane_and_coordinator_share_an_id_and_now_produce_identical_records(self):
        shared = "3a19e737-cb3f-4dde-8304-3241ac374cdb"
        base = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": shared}
        coordinator = client_env.identify(dict(base))
        lane = client_env.identify(dict(base, CLAUDE_CODE_CHILD_SESSION="1"))
        assert coordinator["session_id"] == lane["session_id"] == shared
        # #678: neither role is distinguishable, so both are unknown — not
        # one True and one False.
        assert coordinator["is_subagent"] is None
        assert lane["is_subagent"] is None
        # The two records are byte-identical because nothing in claude-code's
        # environment separates the roles. Asserted positively so a future
        # working discriminator is a deliberate change, not a silent flip.
        assert coordinator == lane


# ── the binding checks (#655) ────────────────────────────────────────────
#
# "If a value is meant to come from ONE place, add the check that BINDS it
# there — a test that can only pass if the production reader is what actually
# runs." Measured on #655: a correct reuse was entirely unguarded, and a
# hand-rolled replacement passed every test its author wrote.

class TestTheRegistryIsTheOneHome:

    def test_write_path_follows_the_registry_not_a_hard_coded_var_name(
            self, tmp_path, monkeypatch):
        """The test the naive env-dict tests cannot be a substitute for.

        The environment here contains ONLY the synthetic variables. A
        `client_env` that named `CLAUDE_CODE_SESSION_ID` directly — anywhere,
        however correctly — resolves nothing from this environment and reds.
        The whole production path is exercised, not just `identify`: `write()`
        is the direct-write path (`status_sync._agent_session_record` is the
        production writer, but it reuses `record()`, so this binds the registry
        that path reads).
        """
        monkeypatch.setattr(client_env, "CLIENTS", (FAKE,))
        t = _target(tmp_path, {})
        rc, msg = client_env.write(
            t, env={"FAKE_CLI": "1", "FAKE_SESSION": "sid-42",
                    "FAKE_CHILD": "1"},
            now=CLOCK)
        assert rc == 0, msg
        rec = _status(t)["agent_session"]
        assert rec == {"client": "fakeclient", "session_id": "sid-42",
                       "is_subagent": True,
                       "recorded_at": "2026-07-31T19:30:00+00:00"}

    def test_the_real_registry_names_the_measured_client_variables(self):
        """The registry's content, pinned to what is measured.

        Separate from the behavioural tests on purpose: those all run against
        a synthetic registry precisely so they cannot be satisfied by the real
        names, which leaves the real names themselves unguarded unless
        something asserts them. This is that something. #678 corrected the
        `subagent_var`: `CLAUDE_CODE_CHILD_SESSION` is present in BOTH roles
        so it is now `None` (no discriminator) rather than a name that
        reports a confident wrong boolean.
        """
        cc = {c.name: c for c in client_env.CLIENTS}["claude-code"]
        assert cc.session_id_var == "CLAUDE_CODE_SESSION_ID"
        assert cc.subagent_var is None
        assert "CLAUDECODE" in cc.detect

        codex = {c.name: c for c in client_env.CLIENTS}["codex"]
        assert codex.detect == ("CODEX_THREAD_ID",)
        assert codex.session_id_var == "CODEX_COMPANION_SESSION_ID"
        assert codex.subagent_var is None

    def test_a_discriminating_client_still_reports_a_confident_boolean(self):
        """Direction 2 of #678's red-proof: the unknown is claude-code-specific.

        The fix that made claude-code's bit `None` must NOT make `is_subagent`
        permanently unknown for every client — that would be a check that can
        never fail. A client whose registry entry has a real, working
        `subagent_var` (here the synthetic FAKE) must still resolve a
        confident boolean. Reverting `subagent_var` to a non-None name and
        reading the env is the production line under test
        (`identify`'s `if c.subagent_var is not None` branch).
        """
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(client_env, "CLIENTS", (FAKE,))
        try:
            subagent = client_env.identify(
                {"FAKE_CLI": "1", "FAKE_SESSION": "s", "FAKE_CHILD": "1"})
            main_agent = client_env.identify(
                {"FAKE_CLI": "1", "FAKE_SESSION": "s"})
        finally:
            monkeypatch.undo()
        assert subagent["is_subagent"] is True
        assert main_agent["is_subagent"] is False

    def test_only_client_env_names_the_registry_variables(self):
        """An AST guard: the var names have exactly one home.

        The transmission mechanism this forbids is imitation — a second
        `os.environ.get("CLAUDE_CODE_SESSION_ID")` somewhere else, which would
        work today and diverge the day the registry gains a client or a client
        renames a variable. AST rather than a substring scan, and docstrings
        excluded, because #652's finding is *documented* in several modules'
        docstrings and prose that merely NAMES a variable is not a second
        reader (#659 established the same distinction for `read_text_full`).
        Test modules are excluded: constructing a fake environment is exactly
        what a test legitimately does.
        """
        names = {v for c in client_env.CLIENTS
                 for v in (c.detect + (c.session_id_var, c.subagent_var))
                 if v}
        offenders = []
        for path in sorted(HERE.glob("*.py")) + sorted(HERE.glob("dev/*.py")):
            if path.name.startswith("test_") or path.name == "client_env.py":
                continue
            tree = ast.parse(path.read_text())
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef,
                                     ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = getattr(node, "body", None)
                    if (body and isinstance(body[0], ast.Expr)
                            and isinstance(body[0].value, ast.Constant)
                            and isinstance(body[0].value.value, str)):
                        docstrings.add(id(body[0].value))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Constant)
                        and isinstance(node.value, str)
                        and id(node) not in docstrings
                        and node.value in names):
                    offenders.append("%s:%d names %r"
                                     % (path.name, node.lineno, node.value))
        assert not offenders, (
            "client env variable names belong only in client_env.CLIENTS; "
            "found: " + "; ".join(offenders))

    def test_write_refuses_through_the_shared_status_reader(self, tmp_path):
        """Binds the writer to `status_sync`'s refusal contract (#402/#655).

        Two assertions, because either alone is weak: the identity check fails
        if the function body was COPIED, and the patch check fails if the
        writer hand-rolled a `json.loads` that ignores the shared reader and
        writes anyway.
        """
        assert client_env._read_status is status_sync._read_status

        t = _target(tmp_path, {})
        torn = '{"task": "on #665", "dreamers": ['
        spath = t / ".dreamwork" / "status.json"
        spath.write_text(torn)
        before = spath.read_bytes()
        rc, msg = client_env.write(t, env={"CLAUDECODE": "1"}, now=CLOCK)
        assert rc == 1
        assert "refusing to write" in msg
        assert spath.read_bytes() == before, (
            "a status.json that could not be read must be left untouched, "
            "never rebuilt from what the writer happens to hold")


# ── integration: the record must survive the other writer ────────────────

class TestStatusSyncOwnsAgentSession:
    """agent_session is DERIVED (#858): status_sync writes it, cwd-restricted.

    The #665 'author-owned, never derived' contract is superseded.
    `status_sync._agent_session_record` returns None unless the sync target is
    the invocation cwd (so a lane syncing another checkout cannot overwrite
    the main agent's identity), and accepts the candidate UUID only when
    `session_source` resolves it live. This class pins the classification and
    the cwd restriction; `test_status_sync.py`'s `TestAgentSessionWriter` pins
    the live-only write itself.
    """

    def test_agent_session_is_in_the_derived_set(self):
        # The classification has one home: status_sync.DERIVED. The prose
        # surfaces must agree (TestProseAgreesWithDerivedClassification).
        assert "agent_session" in status_sync.DERIVED

    def test_a_sync_of_another_checkout_leaves_the_record_alone(
            self, tmp_path):
        # The cwd restriction: target != cwd -> _agent_session_record returns
        # None -> status_sync does not touch agent_session. This is the
        # property that stops a lane syncing the main checkout from
        # overwriting the main agent's identity, and it is why a record seeded
        # by the (target-agnostic) direct write survives a sync run from
        # elsewhere.
        t = _target(tmp_path, {"task": "on #665"})
        (t / ".dreamwork" / "tasks.md").write_text("## Open\n- **#665** x\n")
        rc, _ = client_env.write(
            t, env={"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "sid-1"},
            now=CLOCK)
        assert rc == 0
        before = _status(t)["agent_session"]

        out_s, err_s = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out_s), contextlib.redirect_stderr(err_s):
            status_sync.main(["--target", str(t)])
        assert _status(t)["agent_session"] == before, (
            "a sync whose target is not the invocation cwd must not touch "
            "agent_session (the cwd restriction)")

    def test_coverage_lists_agent_session_as_derived_not_author_owned(
            self, tmp_path):
        t = _target(tmp_path, {"task": "on #665"})
        (t / ".dreamwork" / "tasks.md").write_text("## Open\n- **#665** x\n")
        out_s, err_s = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out_s), contextlib.redirect_stderr(err_s):
            status_sync.main(["--target", str(t)])
        coverage = next(line for line in out_s.getvalue().splitlines()
                        if line.startswith("coverage:"))
        # Discriminating form (mirrors test_status_sync.py): agent_session
        # must sit on the derived side of the line, never the author-owned tail.
        assert "agent_session" in coverage.split("author-owned", 1)[0], (
            "agent_session is DERIVED; coverage must list it on the derived "
            "side, not the author-owned side: %s" % coverage)


class TestTheOrientStepDoesNotHandWriteAgentSession:
    """The doc is the transmission vector, so the doc is bound to the code
    (#659). Under #858 agent_session is DERIVED (written by status_sync), so
    `initialization.md` step 7 must NOT instruct a manual
    `client_env.py --write` -- that path bypasses the liveness validation #858
    made load-bearing. This is the prose regression guard for the task's own
    check: does any surviving text tell an agent to write agent_session by
    hand?
    """

    def _step7(self):
        text = (HERE / "initialization.md").read_text()
        s = text.index("(#665)")
        e = text.index("8. **Reconcile.**", s)
        return text[s:e]

    def test_step_7_points_at_status_sync_not_a_manual_write(self):
        step7 = self._step7()
        assert "status-sync" in step7 or "status_sync" in step7, (
            "step 7 must name status-sync as the agent_session writer")
        assert "client_env.py --write" not in step7, (
            "step 7 must not instruct a manual agent_session write; "
            "agent_session is DERIVED (#858) and a hand-written key bypasses "
            "the liveness check")


class TestProseAgreesWithDerivedClassification:
    """The shared-source-of-truth guard (#908, #858).

    file-formats.md and client_env.py are the contract surfaces agents read.
    If they call a field 'author-owned' / 'never derived' while
    `status_sync.DERIVED` classifies it as derived, the prose directs agents to
    maintain a field the syncer owns -- the exact drift #858's writer replaced
    and this task closed. The classification has ONE home
    (`status_sync.DERIVED`); this asserts the prose does not contradict it.
    Without this guard, re-adding 'Author-owned, never derived' to the row
    passes every other test -- the false-green of an unguarded prose surface.
    """

    def _agent_session_row(self):
        text = (HERE / "file-formats.md").read_text()
        return next(line for line in text.splitlines()
                    if line.startswith("| `agent_session`"))

    def test_file_formats_does_not_call_a_derived_field_author_owned(self):
        # Precondition DERIVED from the code, not a literal: agent_session IS
        # in DERIVED, so its row must not claim author-ownership.
        assert "agent_session" in status_sync.DERIVED
        row = self._agent_session_row()
        assert "author-owned" not in row.lower(), (
            "agent_session is in status_sync.DERIVED; its file-formats.md row "
            "must not call it author-owned: %s" % row[:120])
        assert "never derived" not in row.lower()

    def test_client_env_docstring_does_not_reassert_authored_not_derived(self):
        text = (HERE / "client_env.py").read_text()
        assert "AUTHORED, NOT DERIVED" not in text, (
            "client_env.py must not re-assert the refuted authored-not-derived "
            "argument; status_sync is the writer (#858)")
        assert "leaves it alone by construction" not in text
        assert "three-tuple" not in text
