import json
from dataclasses import dataclass

from au_radar.agent_harness import AgentTrace
from au_radar.chat_harness import ChatTranscript

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
    parsed = json.loads(response.content[0].text)

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
    )


AGENT_JUDGE_RUBRIC = """You are evaluating whether an automated agent could reach a government
service, based on the recorded steps, observations, and outcome below.

Score six dimensions using the evidence in the trace only. Any dimension scored 3 or above
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
6) Navigation efficiency (0-4) - based on step count, fewer steps score higher.

OUTPUT. Respond with JSON only: {"findability": int, "portal_quality": int,
"agent_permeability": int, "service_access": int, "structured_access": int,
"navigation_efficiency": int, "justification": "2-4 sentence justification"}"""


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
    parsed = json.loads(response.content[0].text)

    raw = (
        parsed["findability"] * 4
        + parsed["portal_quality"]
        + parsed["agent_permeability"]
        + parsed["service_access"]
        + parsed["structured_access"]
        + parsed["navigation_efficiency"]
    )
    total = round((raw / 24) * 10, 1)

    return AgentScore(
        findability=parsed["findability"], portal_quality=parsed["portal_quality"],
        agent_permeability=parsed["agent_permeability"], service_access=parsed["service_access"],
        structured_access=parsed["structured_access"], navigation_efficiency=parsed["navigation_efficiency"],
        raw=raw, total=total, justification=parsed["justification"],
    )
