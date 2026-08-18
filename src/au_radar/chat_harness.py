from dataclasses import dataclass, field

from au_radar.catalogue import ChatService


@dataclass
class ChatTranscript:
    service_id: str
    trial: int
    model: str
    turns: list[dict] = field(default_factory=list)


def run_chat_conversation(
    client, service: ChatService, country: str, model: str, trial: int = 0,
) -> ChatTranscript:
    system_prompt = f"The user is a citizen and resident of {country}."
    messages: list[dict] = []

    for user_turn in service.turns:
        messages.append({"role": "user", "content": user_turn})
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=list(messages),
        )
        assistant_text = response.content[0].text
        messages.append({"role": "assistant", "content": assistant_text})

    return ChatTranscript(
        service_id=service.id, trial=trial, model=model, turns=messages,
    )
