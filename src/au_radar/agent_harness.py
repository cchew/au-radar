from dataclasses import dataclass, field

from au_radar.anthropic_utils import extract_tool_use
from au_radar.catalogue import AgentTask, Catalogue

# Login-field settle behaviour. After each action the harness waits a fixed
# baseline (so page content has rendered before it's read), then polls for a
# late-appearing login field -- an SSO widget injected by client-side JS well
# after navigation -- returning the instant one is seen and otherwise giving
# up at the cap. A single fixed wait could be outrun by a slow SSO flow; the
# cost of the poll is that a step which never surfaces a login field pays the
# full cap. Acceptable for a human-supervised research run. See FUTURE.md.
LOGIN_FIELD_SETTLE_MS = 500
LOGIN_FIELD_SETTLE_MAX_MS = 2000
LOGIN_FIELD_POLL_MS = 250

# Any frame containing one of these is treated as an auth boundary.
_LOGIN_FIELD_SELECTORS = (
    'input[type="password"]',
    'input[autocomplete="current-password"]',
    'input[autocomplete="one-time-code"]',
)

# High-precision substrings for federated-auth / OIDC / SAML URLs. Matching one
# stops the run even before the login form itself has rendered (the redirect
# step). Kept deliberately narrow to avoid premature stops on ordinary pages.
_AUTH_URL_MARKERS = (
    "login.microsoftonline.com",
    ".okta.com",
    "auth0.com",
    "myid.gov.au",
    "login.my.gov.au",
    "samlrequest=",
    "response_type=code",
    "response_type=token",
    "/oauth2/authorize",
    "/oauth/authorize",
    "/connect/authorize",
    "/saml2/idp",
)

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
        "description": (
            "Click an element on the current page. `description` is matched against "
            "the page's visible text, so it MUST be a short, exact, verbatim substring "
            "copied from the most recent page content you were shown -- never a "
            "paraphrase, summary, or your best guess at what a link 'should' say."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"description": {"type": "string"}},
            "required": ["description"],
        },
    },
    {
        "name": "type_text",
        "description": (
            "Type text into a field on the current page. `description` is matched "
            "against the field's placeholder text, so it MUST be a short, exact, "
            "verbatim substring copied from the most recent page content you were "
            "shown -- never a paraphrase or guess."
        ),
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


def _url_looks_like_auth(url: str) -> bool:
    u = (url or "").lower()
    return any(marker in u for marker in _AUTH_URL_MARKERS)


def _page_has_login_field(page) -> bool:
    """Code-level safety net: never trust the model's own judgment about
    whether it has reached an auth boundary. This is checked before every
    action, independent of what the model asks to do next.

    Positive if the page URL or any frame URL matches a known federated-auth
    pattern (catches the redirect before the form renders), or if any frame
    -- not just the main frame, since AU government SSO widgets commonly
    render inside an embedded iframe -- contains a password, current-password,
    or one-time-code input.
    """
    try:
        if _url_looks_like_auth(page.url):
            return True
    except Exception:
        pass
    for frame in page.frames:
        try:
            if _url_looks_like_auth(frame.url):
                return True
            for selector in _LOGIN_FIELD_SELECTORS:
                if frame.locator(selector).count() > 0:
                    return True
        except Exception:
            # A frame can detach mid-check (navigation racing the check, an
            # iframe being removed). Treat as inconclusive for that frame,
            # never as license to proceed -- other frames are still checked.
            continue
    return False


def _settle_for_login_field(page) -> None:
    """Wait the fixed baseline, then poll (up to the cap) for a login field
    that appears late, returning as soon as one is seen. See the constants
    above for the rationale and cost."""
    page.wait_for_timeout(LOGIN_FIELD_SETTLE_MS)
    waited = LOGIN_FIELD_SETTLE_MS
    while waited < LOGIN_FIELD_SETTLE_MAX_MS:
        if _page_has_login_field(page):
            return
        page.wait_for_timeout(LOGIN_FIELD_POLL_MS)
        waited += LOGIN_FIELD_POLL_MS


def run_agent_task(page, client, task: AgentTask, model: str, max_steps: int = 15) -> AgentTrace:
    trace = AgentTrace(task_id=task.id, model=model)
    system_prompt = (
        f"You are navigating a website to complete this task: {task.description}\n"
        f"Target: {task.target_hint}\nStop condition: {task.stop_condition}\n"
        "Use the tools provided. Before clicking or typing, read the page content you "
        "were shown and copy the exact visible text of the element -- do not paraphrase "
        "or guess link/button text, since it must match the real page verbatim. "
        "Call `finish` when done or blocked."
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
            model=model, max_tokens=2048, system=system_prompt,
            tools=TOOLS, messages=list(messages),
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_block = extract_tool_use(response)
        action, args = tool_block.name, tool_block.input
        extra_tool_use_ids = [
            block.id for block in response.content
            if block.type == "tool_use" and block.id != tool_block.id
        ]

        if action == "finish":
            trace.outcome = args["outcome"]
            trace.evidence.append(args["evidence"])
            break

        try:
            if action == "navigate":
                page.goto(args["url"])
            elif action == "click":
                page.get_by_text(args["description"]).first.click()
            elif action == "type_text":
                page.get_by_placeholder(args["description"]).fill(args["text"])
            elif action == "read_page":
                pass  # observation captured below regardless of action

            # Let async-rendered content (e.g. an SSO widget injected after the
            # page settles) appear before the page is read and before the next
            # loop iteration's guardrail check -- see _settle_for_login_field.
            _settle_for_login_field(page)
            observation = page.inner_text("body")
        except Exception as exc:
            # A failed action (element not clickable, navigation timeout,
            # etc.) is real, informative signal about site navigability --
            # feed it back to the model so it can adapt (try a different
            # element, a different path) rather than crashing the whole
            # trial and losing every prior step's real API cost.
            try:
                page_state = page.inner_text("body")
            except Exception:
                page_state = "(page content unavailable)"
            observation = f"Action failed: {exc}\n\nCurrent page content:\n{page_state}"
        trace.steps.append(AgentStep(action=action, args=args, observation=observation))
        # Every tool_use block from this turn needs a matching tool_result in
        # the next message, or the next create() call is rejected outright --
        # the API validates this strictly. Claude can emit more than one
        # tool_use block in a turn even though only the first is executed
        # (see extra_tool_use_ids above), so those extras get an explicit
        # "not executed" result rather than being silently dropped.
        tool_results = [{"type": "tool_result", "tool_use_id": tool_block.id, "content": observation}]
        for extra_id in extra_tool_use_ids:
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": extra_id,
                "content": "Not executed: only one action is processed per turn. Issue a single action and wait for its result before the next.",
                "is_error": True,
            })
        messages.append({"role": "user", "content": tool_results})

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
