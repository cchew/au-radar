import json

import pytest

from au_radar.agent_harness import AgentStep, AgentTrace
from au_radar.chat_harness import ChatTranscript
from au_radar.judge import judge_agent_trace, judge_chat_transcript


class FakeMessage:
    def __init__(self, text):
        self.content = [type("Block", (), {"type": "text", "text": text})()]


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
    assert score.model == "claude-sonnet-5"  # recorded from the argument, not the judge's own reply


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


def test_judge_chat_transcript_rejects_out_of_range_score():
    transcript = ChatTranscript(
        service_id="x", trial=0, model="m",
        turns=[{"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"}],
    )
    judge_reply = json.dumps({
        "verifiability": 5, "specificity": 2, "depth": 2, "transparency": 1,  # verifiability out of 0-3 range
        "justification": "j",
    })
    client = FakeClient(judge_reply)

    with pytest.raises(ValueError, match="verifiability"):
        judge_chat_transcript(client, transcript, model="m")


def test_judge_chat_transcript_parses_markdown_fenced_json():
    transcript = ChatTranscript(
        service_id="x", trial=0, model="m",
        turns=[{"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"}],
    )
    fenced_reply = "```json\n" + json.dumps({
        "verifiability": 3, "specificity": 2, "depth": 2, "transparency": 1,
        "justification": "fenced but valid",
    }) + "\n```"
    client = FakeClient(fenced_reply)

    score = judge_chat_transcript(client, transcript, model="m")

    assert score.total == 8.0
    assert score.justification == "fenced but valid"


def test_judge_chat_transcript_parses_json_with_leading_prose():
    transcript = ChatTranscript(
        service_id="x", trial=0, model="m",
        turns=[{"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"}],
    )
    prefaced_reply = "Looking at this conversation, here is my evaluation:\n\n" + json.dumps({
        "verifiability": 3, "specificity": 2, "depth": 2, "transparency": 1,
        "justification": "prefaced but valid",
    })
    client = FakeClient(prefaced_reply)

    score = judge_chat_transcript(client, transcript, model="m")

    assert score.total == 8.0
    assert score.justification == "prefaced but valid"


def test_judge_chat_transcript_raises_clear_error_on_unparseable_reply():
    transcript = ChatTranscript(
        service_id="x", trial=0, model="m",
        turns=[{"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"}],
    )
    client = FakeClient("Sorry, I can't evaluate this conversation.")

    with pytest.raises(ValueError):
        judge_chat_transcript(client, transcript, model="m")


def test_judge_agent_trace_applies_radar_formula():
    trace = AgentTrace(
        task_id="passport_agent", model="claude-sonnet-5", outcome="reached_auth_boundary",
        steps=[AgentStep(action="navigate", args={}, observation="landed on official portal")],
        evidence=["reached the myGov login screen after 2 clicks"],
    )
    judge_reply = json.dumps({
        "findability": 1, "portal_quality": 3, "agent_permeability": 3,
        "service_access": 3, "structured_access": 0,
        "justification": "Clean two-click path to the auth boundary.",
    })
    client = FakeClient(judge_reply)

    score = judge_agent_trace(client, trace, model="claude-sonnet-5")

    # navigation_efficiency is computed from len(trace.steps) == 1 -> 4 (<=3 band)
    # raw = (1*4) + 3 + 3 + 3 + 0 + 4 = 17 ; total = round((17/24)*10, 1) = 7.1
    assert score.findability == 1
    assert score.navigation_efficiency == 4
    assert score.raw == 17
    assert score.total == 7.1
    assert score.model == "claude-sonnet-5"


def test_judge_agent_trace_formula_zero_case():
    trace = AgentTrace(task_id="x", model="m", outcome="inaccessible", steps=[], evidence=["no site found"])
    judge_reply = json.dumps({
        "findability": 0, "portal_quality": 0, "agent_permeability": 0,
        "service_access": 0, "structured_access": 0,
        "justification": "No service found.",
    })
    client = FakeClient(judge_reply)

    score = judge_agent_trace(client, trace, model="m")

    # navigation_efficiency is computed from len(trace.steps) == 0 -> 4 (<=3 band)
    # raw = 0 + 0 + 0 + 0 + 0 + 4 = 4 ; total = round((4/24)*10, 1) = 1.7
    assert score.navigation_efficiency == 4
    assert score.raw == 4
    assert score.total == 1.7


def test_judge_agent_trace_rejects_out_of_range_score():
    trace = AgentTrace(task_id="x", model="m", outcome="inaccessible", steps=[], evidence=[])
    judge_reply = json.dumps({
        "findability": 1, "portal_quality": 9, "agent_permeability": 0,  # portal_quality out of 0-4 range
        "service_access": 0, "structured_access": 0, "justification": "j",
    })
    client = FakeClient(judge_reply)

    with pytest.raises(ValueError, match="portal_quality"):
        judge_agent_trace(client, trace, model="m")


def test_judge_agent_trace_parses_markdown_fenced_json():
    trace = AgentTrace(task_id="x", model="m", outcome="inaccessible", steps=[], evidence=[])
    fenced_reply = "```json\n" + json.dumps({
        "findability": 1, "portal_quality": 2, "agent_permeability": 2,
        "service_access": 2, "structured_access": 0, "justification": "fenced but valid",
    }) + "\n```"
    client = FakeClient(fenced_reply)

    score = judge_agent_trace(client, trace, model="m")

    assert score.justification == "fenced but valid"
