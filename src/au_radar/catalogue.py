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
    chat_service_id: str = ""


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
    if not isinstance(raw, dict):
        raise ValueError(f"catalogue {path} is not a YAML mapping")
    for key in ("chat_services", "agent_tasks", "legislation_comparators"):
        if key not in raw or raw[key] is None:
            raise ValueError(f"catalogue {path} is missing required key '{key}' (use [] if empty)")

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
            chat_service_id=t.get("chat_service_id", ""),
        )
        for t in raw["agent_tasks"]
    ]
    legislation_comparators = [
        LegislationComparator(id=c["id"], name=c["name"], base_url=c["base_url"])
        for c in raw["legislation_comparators"]
    ]

    _validate(chat_services, agent_tasks, legislation_comparators, path)
    return Catalogue(
        chat_services=chat_services,
        agent_tasks=agent_tasks,
        legislation_comparators=legislation_comparators,
    )


def _validate(chat_services, agent_tasks, legislation_comparators, path: str) -> None:
    for group_name, items in (
        ("chat_services", chat_services),
        ("agent_tasks", agent_tasks),
        ("legislation_comparators", legislation_comparators),
    ):
        ids = [i.id for i in items]
        if any(not i for i in ids):
            raise ValueError(f"catalogue {path}: every {group_name} entry needs a non-empty id")
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"catalogue {path}: duplicate {group_name} id(s): {sorted(dupes)}")

    # RADAR's chat protocol is exactly three turns (spec §3.1). Enforced so a
    # bring-your-own catalogue can't silently run a different instrument.
    for service in chat_services:
        if not isinstance(service.turns, list) or len(service.turns) != 3:
            raise ValueError(
                f"catalogue {path}: chat service '{service.id}' must have exactly 3 turns "
                f"(has {len(service.turns) if isinstance(service.turns, list) else 'non-list'})"
            )
