import pytest

from au_radar.catalogue import AgentTask, Catalogue
from au_radar.agent_harness import _url_looks_like_auth, run_agent_task, run_all_agent_trials


class FakeMessage:
    def __init__(self, tool_name, tool_input):
        self.content = [
            type("Block", (), {"type": "tool_use", "name": tool_name, "input": tool_input, "id": "t1"})()
        ]
    stop_reason = "tool_use"


class FakeMessagesAPI:
    def __init__(self, tool_calls):
        self.tool_calls = list(tool_calls)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        name, args = self.tool_calls.pop(0)
        return FakeMessage(name, args)


class FakeClient:
    def __init__(self, tool_calls):
        self.messages = FakeMessagesAPI(tool_calls)


def test_agent_hard_stops_before_login_field_regardless_of_requested_action(fixture_server, browser_page):
    task = AgentTask(
        id="t", name="Renew document", description="Renew a document",
        target_hint="document renewal", stop_condition="stop at login",
    )
    # The model asks to navigate to the index, then to click through to the
    # service page, then (incorrectly) tries to type into the login form.
    # The harness must never let that third action execute.
    client = FakeClient(tool_calls=[
        ("navigate", {"url": fixture_server + "/index.html"}),
        ("click", {"description": "Renew your document"}),
        ("click", {"description": "Continue to login"}),
        ("type_text", {"description": "Username", "text": "should-never-run"}),
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert trace.outcome == "reached_auth_boundary"
    # The type_text action must never have been executed against the real page.
    executed_actions = [s.action for s in trace.steps]
    assert "type_text" not in executed_actions
    assert browser_page.url.endswith("login.html")


def test_agent_hard_stops_on_password_field_inside_iframe(fixture_server, browser_page):
    task = AgentTask(
        id="t", name="Renew document", description="Renew a document",
        target_hint="document renewal", stop_condition="stop at login",
    )
    client = FakeClient(tool_calls=[
        ("navigate", {"url": fixture_server + "/iframe_login.html"}),
        ("type_text", {"description": "Username", "text": "should-never-run"}),
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert trace.outcome == "reached_auth_boundary"
    assert "type_text" not in [s.action for s in trace.steps]


def test_agent_hard_stops_on_async_rendered_password_field(fixture_server, browser_page):
    task = AgentTask(
        id="t", name="Renew document", description="Renew a document",
        target_hint="document renewal", stop_condition="stop at login",
    )
    client = FakeClient(tool_calls=[
        ("navigate", {"url": fixture_server + "/async_login.html"}),
        ("type_text", {"description": "Username", "text": "should-never-run"}),
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert trace.outcome == "reached_auth_boundary"
    assert "type_text" not in [s.action for s in trace.steps]


def test_agent_hard_stops_on_login_field_injected_after_the_baseline_settle(fixture_server, browser_page):
    # slow_async_login.html injects the password field at 900ms -- past the
    # 500ms baseline, so only the poll in _settle_for_login_field catches it.
    task = AgentTask(id="t", name="x", description="x", target_hint="x", stop_condition="x")
    client = FakeClient(tool_calls=[
        ("navigate", {"url": fixture_server + "/slow_async_login.html"}),
        ("type_text", {"description": "Username", "text": "should-never-run"}),
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert trace.outcome == "reached_auth_boundary"
    assert "type_text" not in [s.action for s in trace.steps]


def test_agent_hard_stops_on_one_time_code_field(fixture_server, browser_page):
    task = AgentTask(id="t", name="x", description="x", target_hint="x", stop_condition="x")
    client = FakeClient(tool_calls=[
        ("navigate", {"url": fixture_server + "/otp_login.html"}),
        ("type_text", {"description": "6-digit code", "text": "should-never-run"}),
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert trace.outcome == "reached_auth_boundary"
    assert "type_text" not in [s.action for s in trace.steps]


def test_agent_hard_stops_on_oidc_authorize_redirect_url(fixture_server, browser_page):
    # A federated-auth redirect URL (an /oauth2/authorize path) is an auth
    # boundary even before any password field has rendered.
    task = AgentTask(id="t", name="x", description="x", target_hint="x", stop_condition="x")
    client = FakeClient(tool_calls=[
        ("navigate", {"url": fixture_server + "/oauth2/authorize?response_type=code&client_id=x"}),
        ("read_page", {}),
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert trace.outcome == "reached_auth_boundary"
    assert [s.action for s in trace.steps] == ["navigate"]  # stopped before the 2nd action


def test_settle_for_login_field_runs_even_when_the_action_raises(fixture_server, browser_page, monkeypatch):
    # A failed action must still get the settle + login-field poll: a click
    # that times out may already have started a redirect to a slow SSO page.
    import au_radar.agent_harness as ah

    calls = []
    real_settle = ah._settle_for_login_field
    monkeypatch.setattr(ah, "_settle_for_login_field", lambda page: calls.append(1) or real_settle(page))
    browser_page.set_default_timeout(300)

    task = AgentTask(id="t", name="x", description="x", target_hint="x", stop_condition="x")
    client = FakeClient(tool_calls=[
        ("navigate", {"url": fixture_server + "/index.html"}),
        ("click", {"description": "this element text does not exist on the page"}),
        ("finish", {"outcome": "blocked", "evidence": "e"}),
    ])

    run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert len(calls) >= 2  # once for the successful navigate, once for the failed click


@pytest.mark.parametrize("url", [
    "https://login.microsoftonline.com/common/oauth2/authorize?response_type=code",
    "https://example.okta.com/login/login.htm",
    "https://idp.example.com/saml2/idp/SSOService.php?SAMLRequest=abc",
    "https://service.example.gov.au/oauth2/authorize?client_id=x",
    "https://myid.gov.au/",
])
def test_url_looks_like_auth_positive(url):
    assert _url_looks_like_auth(url)


@pytest.mark.parametrize("url", [
    "https://www.passports.gov.au/renew-passport",
    "https://www.servicesaustralia.gov.au/medicare",
    "https://www.legislation.gov.au/Details/C2009A00028",
    # dev-doc page that merely quotes an OAuth URL in a query param
    "https://developer.example.gov.au/guide?example=https://x/authorize%3Fresponse_type%3Dcode",
    # an ordinary content page whose path is not an /authorize endpoint
    "https://www.example.gov.au/services/response_type=code-explained",
    "about:blank",
    "",
])
def test_url_looks_like_auth_negative(url):
    assert not _url_looks_like_auth(url)


def test_agent_recovers_from_a_failed_click_instead_of_crashing(fixture_server, browser_page):
    task = AgentTask(id="t", name="x", description="x", target_hint="x", stop_condition="x")
    browser_page.set_default_timeout(500)  # keep the doomed click's timeout fast for this test
    client = FakeClient(tool_calls=[
        ("navigate", {"url": fixture_server + "/index.html"}),
        ("click", {"description": "text that does not exist on this page"}),
        ("finish", {"outcome": "blocked", "evidence": "could not find the link"}),
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert trace.outcome == "blocked"
    failed_step = trace.steps[1]
    assert failed_step.action == "click"
    assert "Action failed" in failed_step.observation


def test_agent_trace_records_finish_outcome_when_model_calls_finish(fixture_server, browser_page):
    task = AgentTask(
        id="t", name="x", description="x", target_hint="x", stop_condition="x",
    )
    client = FakeClient(tool_calls=[
        ("navigate", {"url": fixture_server + "/index.html"}),
        ("finish", {"outcome": "blocked", "evidence": "no service found"}),
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert trace.outcome == "blocked"
    assert trace.evidence == ["no service found"]


def test_second_call_messages_include_first_actions_tool_result(fixture_server, browser_page):
    # Regression test for Critical 3: the harness must accumulate conversation
    # history and feed the tool_result for each action back into the next
    # create() call, not resend a fixed "Continue the task." string every turn.
    task = AgentTask(
        id="t", name="x", description="x", target_hint="x", stop_condition="x",
    )
    client = FakeClient(tool_calls=[
        ("navigate", {"url": fixture_server + "/index.html"}),
        ("finish", {"outcome": "blocked", "evidence": "e"}),
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert len(client.messages.calls) == 2
    first_observation = trace.steps[0].observation
    second_call_messages = client.messages.calls[1]["messages"]

    tool_result_blocks = [
        block
        for m in second_call_messages
        if m["role"] == "user" and isinstance(m["content"], list)
        for block in m["content"]
        if block.get("type") == "tool_result"
    ]
    assert len(tool_result_blocks) == 1
    assert tool_result_blocks[0]["tool_use_id"] == "t1"
    assert tool_result_blocks[0]["content"] == first_observation


class FakeMessageWithLeadingThinkingBlock:
    """Simulates a real Claude response: a ThinkingBlock (no .name/.input)
    ahead of the actual tool_use block. Regression test for the content[0]
    bug documented in FUTURE.md."""

    def __init__(self, tool_name, tool_input):
        thinking_block = type("Block", (), {"type": "thinking", "thinking": "reasoning..."})()
        tool_block = type(
            "Block", (), {"type": "tool_use", "name": tool_name, "input": tool_input, "id": "t1"}
        )()
        self.content = [thinking_block, tool_block]

    stop_reason = "tool_use"


class FakeMessagesAPIWithThinking:
    def __init__(self, tool_calls):
        self.tool_calls = list(tool_calls)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        name, args = self.tool_calls.pop(0)
        return FakeMessageWithLeadingThinkingBlock(name, args)


class FakeClientWithThinking:
    def __init__(self, tool_calls):
        self.messages = FakeMessagesAPIWithThinking(tool_calls)


def test_agent_extracts_tool_use_past_a_leading_thinking_block(fixture_server, browser_page):
    task = AgentTask(id="t", name="x", description="x", target_hint="x", stop_condition="x")
    client = FakeClientWithThinking(tool_calls=[
        ("finish", {"outcome": "blocked", "evidence": "no service found"}),
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert trace.outcome == "blocked"


class FakeMessageWithMultipleToolUse:
    """Simulates Claude emitting more than one tool_use block in a single
    turn. Regression test: the API rejects the *next* create() call if any
    tool_use id from the previous turn lacks a matching tool_result."""

    def __init__(self, calls):
        self.content = [
            type("Block", (), {"type": "tool_use", "name": name, "input": args, "id": f"multi-{i}"})()
            for i, (name, args) in enumerate(calls)
        ]

    stop_reason = "tool_use"


class FakeMessagesAPIWithMultiToolUse:
    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        turn = self.turns.pop(0)
        return FakeMessageWithMultipleToolUse(turn)


class FakeClientWithMultiToolUse:
    def __init__(self, turns):
        self.messages = FakeMessagesAPIWithMultiToolUse(turns)


def test_agent_resolves_every_tool_use_id_when_model_emits_more_than_one(fixture_server, browser_page):
    task = AgentTask(id="t", name="x", description="x", target_hint="x", stop_condition="x")
    client = FakeClientWithMultiToolUse(turns=[
        # First turn: model emits two tool_use blocks at once (only the
        # first, "navigate", should actually execute).
        [("navigate", {"url": fixture_server + "/index.html"}), ("read_page", {})],
        [("finish", {"outcome": "blocked", "evidence": "e"})],
    ])

    trace = run_agent_task(browser_page, client, task, model="claude-sonnet-5", max_steps=10)

    assert trace.outcome == "blocked"
    # The second create() call must not have been rejected by the API for an
    # orphaned tool_use id -- if it had been, this second call would never
    # have happened / the FakeMessagesAPI would have raised IndexError on an
    # empty `turns` list from an unexpected retry-from-scratch.
    assert len(client.messages.calls) == 2
    second_call_messages = client.messages.calls[1]["messages"]
    tool_result_ids = {
        block["tool_use_id"]
        for m in second_call_messages
        if m["role"] == "user" and isinstance(m["content"], list)
        for block in m["content"]
        if block.get("type") == "tool_result"
    }
    assert tool_result_ids == {"multi-0", "multi-1"}


def test_run_all_agent_trials_covers_every_task_n_times(fixture_server, browser_page):
    tasks = [
        AgentTask(id="t1", name="T1", description="d", target_hint="h", stop_condition="s"),
        AgentTask(id="t2", name="T2", description="d", target_hint="h", stop_condition="s"),
    ]
    catalogue = Catalogue(chat_services=[], agent_tasks=tasks, legislation_comparators=[])
    client = FakeClient(tool_calls=[
        ("finish", {"outcome": "blocked", "evidence": "e"}) for _ in range(4)  # 2 tasks x 2 trials
    ])

    traces = run_all_agent_trials(
        lambda: browser_page, client, catalogue, n_trials=2, model="claude-sonnet-5",
    )

    assert len(traces) == 4
    assert sorted(t.task_id for t in traces) == ["t1", "t1", "t2", "t2"]
