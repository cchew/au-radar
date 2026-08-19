import json
from dataclasses import dataclass

from au_radar.agent_harness import AgentTrace
from au_radar.chat_harness import ChatTranscript


def _parse_judge_json(text: str, int_fields: list[str], ranges: dict[str, tuple[int, int]]) -> dict:
    """Parse a judge model's JSON reply defensively: tolerate a markdown code
    fence around the JSON (some models wrap replies in ```json ... ``` even
    when told not to), then assert every named field is present, an int, and
    within its documented inclusive range. Raises ValueError naming the
    offending field/value on any violation, rather than silently corrupting
    downstream means or crashing with a raw KeyError/TypeError mid-collection.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines)

    parsed = json.loads(stripped)

    for field_name in int_fields:
        if field_name not in parsed:
            raise ValueError(f"judge JSON missing required field {field_name!r}")
        value = parsed[field_name]
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"judge JSON field {field_name!r} must be an int, got {value!r}")
        low, high = ranges[field_name]
        if not (low <= value <= high):
            raise ValueError(
                f"judge JSON field {field_name!r} = {value} out of range [{low}, {high}]"
            )

    return parsed

CHAT_JUDGE_RUBRIC = """You are evaluating an AI-generated answer to a citizen-style question about government services.

TASK. Score the answer from 0 to 10 using the criteria below. Judge only what is written in
the answer and the sources it cites. Do not assume facts, policies, or availability not explicitly
stated or linked. Do not confuse the substance of answers with their information content: a
verifiable, specific, complete answer that a service is NOT available should be graded highly,
and a non-verifiable, generic, shallow answer that a service IS available should be graded badly.

RUBRIC
1) Verifiability (0-3) - claims supported by real, official government-authorized sources.
   0 no/invented sources or broken links; 1 unofficial or weakly relevant; 2 at least one
   official relevant source; 3 most material claims directly supported by official sources.
2) Specificity & actionability (0-3) - can a real person act on this?
   0 generic only; 1 direction unclear; 2 clear next step and a workable channel; 3 exact entry
   point, steps, and requirements.
3) Depth & completeness (0-3) - full scope of what the user needs.
   0 superficial; 1 main point only; 2 most relevant aspects; 3 comprehensive without padding.
4) Transparency & non-invention (0-1) - honest about uncertainty.
   0 overconfident/invents; 1 distinguishes verified from unknown, does not guess.

RULES. Use only the answer text and its cited sources; do not fill in facts from your own
knowledge. Do not penalize missing details the answer says it could not verify. Penalize confident
statements that lack sources. Treat broken, irrelevant, or circular links as non-verifiable. Judge
the evidence, not whether the policy itself is generous.

OUTPUT. Respond with JSON only: {"verifiability": int, "specificity": int, "depth": int,
"transparency": int, "justification": "2-4 sentence justification"}"""


@dataclass
class ChatScore:
    verifiability: int
    specificity: int
    depth: int
    transparency: int
    total: float
    justification: str
    model: str


def judge_chat_transcript(client, transcript: ChatTranscript, model: str) -> ChatScore:
    conversation_text = "\n".join(
        f"{t['role'].upper()}: {t['content']}" for t in transcript.turns
    )
    prompt = f"{CHAT_JUDGE_RUBRIC}\n\nCONVERSATION TO JUDGE:\n{conversation_text}"

    response = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    parsed = _parse_judge_json(
        response.content[0].text,
        int_fields=["verifiability", "specificity", "depth", "transparency"],
        ranges={
            "verifiability": (0, 3), "specificity": (0, 3),
            "depth": (0, 3), "transparency": (0, 1),
        },
    )

    total = float(
        parsed["verifiability"] + parsed["specificity"] + parsed["depth"] + parsed["transparency"]
    )
    return ChatScore(
        verifiability=parsed["verifiability"],
        specificity=parsed["specificity"],
        depth=parsed["depth"],
        transparency=parsed["transparency"],
        total=total,
        justification=parsed["justification"],
        model=model,
    )


AGENT_JUDGE_RUBRIC = """You are evaluating whether an automated agent could reach a government
service, based on the recorded steps, observations, and outcome below.

Score five dimensions using the evidence in the trace only. Any dimension scored 3 or above
requires you to cite specific observed evidence from the trace; hedging language invalidates a
high score.

1) Findability (0-1) - did the agent's search/navigation reach an official government page? 0 no, 1 yes.
2) Portal quality (0-4) - information architecture and navigability, from a maze with unlabeled
   controls (0) to fully citizen-centric with two-click service access (4).
3) Agent permeability (0-4) - from actively blocking (CAPTCHA/Cloudflare/geo-block) (0) to
   agent-aware with machine-readable endpoints (4).
4) Service access (0-4) - from service not found/information-only (0) to a full initiation
   pathway confirmed through the authentication gateway, never past it (4).
5) Structured access (0-4) - machine-readable service exposure, from none (0) to a full
   service layer such as an API (4). Most services correctly score 0 here.

Navigation efficiency is NOT scored by you -- it's computed directly from the trace's step
count, per spec.

OUTPUT. Respond with JSON only: {"findability": int, "portal_quality": int,
"agent_permeability": int, "service_access": int, "structured_access": int,
"justification": "2-4 sentence justification"}"""

# Spec §3.1: "Navigation efficiency (0-4) - computed from step count, not
# self-reported." Bands below are a reasonable monotonic mapping from step
# count to the 0-4 scale: fewer steps to resolution scores higher.
NAVIGATION_EFFICIENCY_BANDS = [
    (3, 4),   # <= 3 steps
    (5, 3),   # <= 5 steps
    (8, 2),   # <= 8 steps
    (12, 1),  # <= 12 steps
]


def _compute_navigation_efficiency(step_count: int) -> int:
    for max_steps, score in NAVIGATION_EFFICIENCY_BANDS:
        if step_count <= max_steps:
            return score
    return 0


@dataclass
class AgentScore:
    findability: int
    portal_quality: int
    agent_permeability: int
    service_access: int
    structured_access: int
    navigation_efficiency: int
    raw: int
    total: float
    justification: str
    model: str


def judge_agent_trace(client, trace: AgentTrace, model: str) -> AgentScore:
    steps_text = "\n".join(f"{s.action}({s.args}) -> {s.observation[:200]}" for s in trace.steps)
    evidence_text = "\n".join(trace.evidence)
    prompt = (
        f"{AGENT_JUDGE_RUBRIC}\n\nOUTCOME: {trace.outcome}\n\nSTEPS:\n{steps_text}"
        f"\n\nEVIDENCE:\n{evidence_text}"
    )

    response = client.messages.create(
        model=model, max_tokens=512, messages=[{"role": "user", "content": prompt}],
    )
    parsed = _parse_judge_json(
        response.content[0].text,
        int_fields=["findability", "portal_quality", "agent_permeability", "service_access", "structured_access"],
        ranges={
            "findability": (0, 1), "portal_quality": (0, 4), "agent_permeability": (0, 4),
            "service_access": (0, 4), "structured_access": (0, 4),
        },
    )

    navigation_efficiency = _compute_navigation_efficiency(len(trace.steps))
    raw = (
        parsed["findability"] * 4
        + parsed["portal_quality"]
        + parsed["agent_permeability"]
        + parsed["service_access"]
        + parsed["structured_access"]
        + navigation_efficiency
    )
    total = round((raw / 24) * 10, 1)

    return AgentScore(
        findability=parsed["findability"], portal_quality=parsed["portal_quality"],
        agent_permeability=parsed["agent_permeability"], service_access=parsed["service_access"],
        structured_access=parsed["structured_access"], navigation_efficiency=navigation_efficiency,
        raw=raw, total=total, justification=parsed["justification"], model=model,
    )
