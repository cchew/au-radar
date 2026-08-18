import json

from au_radar.chat_harness import ChatTranscript
from au_radar.judge import judge_chat_transcript


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
