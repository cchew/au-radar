from au_radar.catalogue import ChatService, Catalogue
from au_radar.chat_harness import run_chat_conversation, run_all_chat_trials


class FakeMessage:
    def __init__(self, text):
        self.content = [type("Block", (), {"type": "text", "text": text})()]


class FakeMessagesAPI:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeMessage(self.replies.pop(0))


class FakeClient:
    def __init__(self, replies):
        self.messages = FakeMessagesAPI(replies)


def test_run_chat_conversation_makes_three_turns_with_system_prompt():
    service = ChatService(
        id="passport", name="Passport renewal", domain="Public administration",
        agency="Australian Passport Office",
        turns=["How do I renew my passport?", "Is there a website?", "Do I need to pay?"],
    )
    client = FakeClient(replies=["reply1", "reply2", "reply3"])

    transcript = run_chat_conversation(client, service, country="Australia", model="claude-sonnet-5")

    assert len(client.messages.calls) == 3
    assert client.messages.calls[0]["system"] == "The user is a citizen and resident of Australia."
    assert transcript.service_id == "passport"
    assert transcript.model == "claude-sonnet-5"
    assert [t["content"] for t in transcript.turns if t["role"] == "user"] == service.turns
    assert [t["content"] for t in transcript.turns if t["role"] == "assistant"] == [
        "reply1", "reply2", "reply3",
    ]


def test_third_call_includes_full_prior_history():
    service = ChatService(
        id="x", name="x", domain="x", agency="x",
        turns=["turn1", "turn2", "turn3"],
    )
    client = FakeClient(replies=["r1", "r2", "r3"])

    run_chat_conversation(client, service, country="Australia", model="claude-sonnet-5")

    third_call_messages = client.messages.calls[2]["messages"]
    assert len(third_call_messages) == 5  # user,assistant,user,assistant,user
    assert third_call_messages[-1]["content"] == "turn3"


def test_run_all_chat_trials_covers_every_service_n_times():
    services = [
        ChatService(id="a", name="A", domain="d", agency="ag", turns=["1", "2", "3"]),
        ChatService(id="b", name="B", domain="d", agency="ag", turns=["1", "2", "3"]),
    ]
    catalogue = Catalogue(chat_services=services, agent_tasks=[], legislation_comparators=[])
    client = FakeClient(replies=["r"] * (3 * 2 * 2))  # 3 turns x 2 trials x 2 services

    transcripts = run_all_chat_trials(client, catalogue, n_trials=2, country="Australia", model="claude-sonnet-5")

    assert len(transcripts) == 4  # 2 services x 2 trials
    assert sorted((t.service_id, t.trial) for t in transcripts) == [
        ("a", 0), ("a", 1), ("b", 0), ("b", 1),
    ]
