from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ChatService:
    id: str
    name: str
    domain: str
    agency: str
    turns: list[str]


@dataclass
class AgentTask:
    id: str
    name: str
    description: str
    target_hint: str
    stop_condition: str


@dataclass
class LegislationComparator:
    id: str
    name: str
    base_url: str


@dataclass
class Catalogue:
    chat_services: list[ChatService]
    agent_tasks: list[AgentTask]
    legislation_comparators: list[LegislationComparator]


def load_catalogue(path: str) -> Catalogue:
    raw = yaml.safe_load(Path(path).read_text())

    chat_services = [
        ChatService(
            id=s["id"], name=s["name"], domain=s["domain"],
            agency=s["agency"], turns=s["turns"],
        )
        for s in raw["chat_services"]
    ]
    agent_tasks = [
        AgentTask(
            id=t["id"], name=t["name"], description=t["description"],
            target_hint=t["target_hint"], stop_condition=t["stop_condition"],
        )
        for t in raw["agent_tasks"]
    ]
    legislation_comparators = [
        LegislationComparator(id=c["id"], name=c["name"], base_url=c["base_url"])
        for c in raw["legislation_comparators"]
    ]
    return Catalogue(
        chat_services=chat_services,
        agent_tasks=agent_tasks,
        legislation_comparators=legislation_comparators,
    )
