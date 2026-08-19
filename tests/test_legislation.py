from au_radar.catalogue import Catalogue, LegislationComparator
from au_radar.legislation import (
    build_legislation_agent_task,
    build_legislation_chat_service,
    expand_legislation_tasks,
)


def test_build_legislation_chat_service_has_three_turns_naming_the_provision():
    comparator = LegislationComparator(id="lex_au", name="lex-au", base_url="https://lex.au")

    service = build_legislation_chat_service(comparator, provision="Fair Work Act 2009 s 65")

    assert service.id == "legislation_lex_au"
    assert len(service.turns) == 3
    assert any("Fair Work Act 2009 s 65" in t for t in service.turns)


def test_build_legislation_agent_task_targets_the_comparator():
    comparator = LegislationComparator(
        id="austlii", name="AustLII", base_url="https://www.austlii.edu.au",
    )

    task = build_legislation_agent_task(comparator, provision="Fair Work Act 2009 s 65")

    assert task.id == "legislation_austlii"
    assert "AustLII" in task.description
    assert "Fair Work Act 2009 s 65" in task.description
    assert task.stop_condition  # non-empty


def test_expand_legislation_tasks_produces_three_per_comparator():
    comparators = [
        LegislationComparator(id="lex_au", name="lex-au", base_url="https://lex.au"),
        LegislationComparator(
            id="federal_register", name="Federal Register of Legislation",
            base_url="https://www.legislation.gov.au",
        ),
        LegislationComparator(id="austlii", name="AustLII", base_url="https://www.austlii.edu.au"),
    ]
    catalogue = Catalogue(chat_services=[], agent_tasks=[], legislation_comparators=comparators)

    chat_services, agent_tasks = expand_legislation_tasks(catalogue, provision="Fair Work Act 2009 s 65")

    assert len(chat_services) == 3
    assert len(agent_tasks) == 3
    assert sorted(s.id for s in chat_services) == [
        "legislation_austlii", "legislation_federal_register", "legislation_lex_au",
    ]
    assert sorted(t.id for t in agent_tasks) == [
        "legislation_austlii", "legislation_federal_register", "legislation_lex_au",
    ]
