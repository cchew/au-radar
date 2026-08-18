import json
from dataclasses import dataclass

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
