from au_radar.catalogue import AgentTask, Catalogue
from au_radar.agent_harness import run_agent_task, run_all_agent_trials


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
