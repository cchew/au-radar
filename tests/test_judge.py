import json

from au_radar.agent_harness import AgentStep, AgentTrace
from au_radar.chat_harness import ChatTranscript
from au_radar.judge import judge_agent_trace, judge_chat_transcript


class FakeMessage:
    def __init__(self, text):
        self.content = [type("Block", (), {"text": text})()]


class FakeMessagesAPI:
    def __init__(self, reply_text):
        self.reply_text = reply_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeMessage(self.reply_text)


class FakeClient:
    def __init__(self, reply_text):
        self.messages = FakeMessagesAPI(reply_text)


def test_judge_chat_transcript_parses_scores():
    transcript = ChatTranscript(
        service_id="passport", trial=0, model="claude-sonnet-5",
        turns=[
            {"role": "user", "content": "How do I renew my passport?"},
            {"role": "assistant", "content": "Visit passports.gov.au to renew online."},
        ],
    )
    judge_reply = json.dumps({
        "verifiability": 3, "specificity": 2, "depth": 2, "transparency": 1,
        "justification": "Cites the official domain, gives a clear channel.",
    })
    client = FakeClient(judge_reply)

    score = judge_chat_transcript(client, transcript, model="claude-sonnet-5")

    assert score.verifiability == 3
    assert score.specificity == 2
    assert score.depth == 2
    assert score.transparency == 1
    assert score.total == 8.0
    assert "official domain" in score.justification


def test_judge_prompt_includes_only_the_answer_text_not_judge_own_knowledge():
    transcript = ChatTranscript(
        service_id="x", trial=0, model="m",
        turns=[
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
        ],
    )
    judge_reply = json.dumps({
        "verifiability": 0, "specificity": 0, "depth": 0, "transparency": 0, "justification": "no sources",
    })
    client = FakeClient(judge_reply)

    judge_chat_transcript(client, transcript, model="m")

    sent_prompt = client.messages.calls[0]["messages"][0]["content"]
    assert "u1" in sent_prompt
    assert "a1" in sent_prompt


def test_judge_agent_trace_applies_radar_formula():
    trace = AgentTrace(
        task_id="passport_agent", model="claude-sonnet-5", outcome="reached_auth_boundary",
        steps=[AgentStep(action="navigate", args={}, observation="landed on official portal")],
        evidence=["reached the myGov login screen after 2 clicks"],
    )
    judge_reply = json.dumps({
        "findability": 1, "portal_quality": 3, "agent_permeability": 3,
        "service_access": 3, "structured_access": 0, "navigation_efficiency": 3,
        "justification": "Clean two-click path to the auth boundary.",
    })
    client = FakeClient(judge_reply)

    score = judge_agent_trace(client, trace, model="claude-sonnet-5")

    # raw = (1*4) + 3 + 3 + 3 + 0 + 3 = 16 ; total = round((16/24)*10, 1) = 6.7
    assert score.findability == 1
    assert score.raw == 16
    assert score.total == 6.7


def test_judge_agent_trace_formula_zero_case():
    trace = AgentTrace(task_id="x", model="m", outcome="inaccessible", steps=[], evidence=["no site found"])
    judge_reply = json.dumps({
        "findability": 0, "portal_quality": 0, "agent_permeability": 0,
        "service_access": 0, "structured_access": 0, "navigation_efficiency": 0,
        "justification": "No service found.",
    })
    client = FakeClient(judge_reply)

    score = judge_agent_trace(client, trace, model="m")

    assert score.raw == 0
    assert score.total == 0.0
