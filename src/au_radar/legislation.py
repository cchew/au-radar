from au_radar.catalogue import AgentTask, Catalogue, ChatService, LegislationComparator


def build_legislation_chat_service(comparator: LegislationComparator, provision: str) -> ChatService:
    return ChatService(
        id=f"legislation_{comparator.id}",
        name=f"Legislation lookup via {comparator.name}",
        domain="Legislation",
        agency=comparator.name,
        turns=[
            f"What does {provision} currently say?",
            "Can you point me to the exact official source?",
            "How do I know that's the current, in-force version?",
        ],
    )


def build_legislation_agent_task(comparator: LegislationComparator, provision: str) -> AgentTask:
    return AgentTask(
        id=f"legislation_{comparator.id}",
        name=f"Legislation retrieval via {comparator.name}",
        description=f"Navigate {comparator.name} and retrieve the current text of {provision}.",
        target_hint=comparator.base_url,
        stop_condition=(
            "Stop once the correct, current provision text has been retrieved and confirmed, "
            "or once it's clear this comparator cannot produce it."
        ),
    )


def expand_legislation_tasks(
    catalogue: Catalogue, provision: str,
) -> tuple[list[ChatService], list[AgentTask]]:
    """Generate the three-per-comparator legislation chat services and agent
    tasks (one pair per catalogue.legislation_comparators entry). These are
    NOT stored statically in catalogue.yaml -- they're expanded at run time
    because they're parameterised by `provision`, which changes per run."""
    chat_services = [
        build_legislation_chat_service(comparator, provision)
        for comparator in catalogue.legislation_comparators
    ]
    agent_tasks = [
        build_legislation_agent_task(comparator, provision)
        for comparator in catalogue.legislation_comparators
    ]
    return chat_services, agent_tasks
