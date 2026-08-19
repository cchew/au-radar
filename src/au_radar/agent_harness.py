from dataclasses import dataclass, field

from au_radar.catalogue import AgentTask, Catalogue

TOOLS = [
    {
        "name": "navigate",
        "description": "Navigate the browser to a URL.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "click",
        "description": "Click an element on the current page, described in plain text.",
        "input_schema": {
            "type": "object",
            "properties": {"description": {"type": "string"}},
            "required": ["description"],
        },
    },
    {
        "name": "type_text",
        "description": "Type text into a field on the current page, described in plain text.",
        "input_schema": {
            "type": "object",
            "properties": {"description": {"type": "string"}, "text": {"type": "string"}},
            "required": ["description", "text"],
        },
    },
    {
        "name": "read_page",
        "description": "Read the current page's visible text content.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "finish",
        "description": "Stop the task and record the outcome.",
        "input_schema": {
            "type": "object",
            "properties": {
                "outcome": {
                    "type": "string",
                    "enum": ["reached_auth_boundary", "blocked", "inaccessible", "completed_public_info"],
                },
                "evidence": {"type": "string"},
            },
            "required": ["outcome", "evidence"],
        },
    },
]


@dataclass
class AgentStep:
    action: str
    args: dict
    observation: str


@dataclass
class AgentTrace:
    task_id: str
    model: str
    outcome: str = "inaccessible"
    steps: list[AgentStep] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


def _page_has_login_field(page) -> bool:
    """Code-level safety net: never trust the model's own judgment about
    whether it has reached an auth boundary. This is checked after every
    action, independent of what the model asks to do next."""
    return page.locator('input[type="password"]').count() > 0


def run_agent_task(page, client, task: AgentTask, model: str, max_steps: int = 15) -> AgentTrace:
    trace = AgentTrace(task_id=task.id, model=model)
    system_prompt = (
        f"You are navigating a website to complete this task: {task.description}\n"
        f"Target: {task.target_hint}\nStop condition: {task.stop_condition}\n"
        "Use the tools provided. Call `finish` when done or blocked."
    )

    messages: list[dict] = [{"role": "user", "content": "Begin the task."}]

    for _ in range(max_steps):
        # Checked BEFORE requesting the next action, not after executing one:
        # this is what makes the guardrail apply uniformly to every action
        # type (including a login form appearing via a click, not just via
        # navigate), and it means the model is never even asked for an
        # action once the boundary is reached.
        if _page_has_login_field(page):
            trace.outcome = "reached_auth_boundary"
            break

        response = client.messages.create(
            model=model, max_tokens=1024, system=system_prompt,
            tools=TOOLS, messages=list(messages),
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_block = response.content[0]
        action, args = tool_block.name, tool_block.input

        if action == "finish":
            trace.outcome = args["outcome"]
            trace.evidence.append(args["evidence"])
            break

        if action == "navigate":
            page.goto(args["url"])
        elif action == "click":
            page.get_by_text(args["description"]).first.click()
        elif action == "type_text":
            page.get_by_placeholder(args["description"]).fill(args["text"])
        elif action == "read_page":
            pass  # observation captured below regardless of action

        observation = page.inner_text("body")
        trace.steps.append(AgentStep(action=action, args=args, observation=observation))
        messages.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_block.id, "content": observation}],
        })

    return trace


def run_all_agent_trials(
    page_factory, client, catalogue: Catalogue, n_trials: int, model: str, max_steps: int = 15,
) -> list[AgentTrace]:
    traces = []
    for task in catalogue.agent_tasks:
        for _ in range(n_trials):
            page = page_factory()
            traces.append(run_agent_task(page, client, task, model=model, max_steps=max_steps))
    return traces
