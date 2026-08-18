from pathlib import Path

from au_radar.catalogue import load_catalogue

CATALOGUE_PATH = Path(__file__).parent.parent / "src" / "au_radar" / "data" / "catalogue.yaml"


def test_catalogue_counts_match_spec():
    catalogue = load_catalogue(str(CATALOGUE_PATH))
    assert len(catalogue.chat_services) == 15
    assert len(catalogue.agent_tasks) == 5
    assert len(catalogue.legislation_comparators) == 3


def test_every_chat_service_has_exactly_three_turns():
    catalogue = load_catalogue(str(CATALOGUE_PATH))
    for service in catalogue.chat_services:
        assert len(service.turns) == 3, f"{service.id} has {len(service.turns)} turns, expected 3"


def test_chat_service_ids_are_unique():
    catalogue = load_catalogue(str(CATALOGUE_PATH))
    ids = [s.id for s in catalogue.chat_services]
    assert len(ids) == len(set(ids))


def test_agent_task_has_stop_condition():
    catalogue = load_catalogue(str(CATALOGUE_PATH))
    for task in catalogue.agent_tasks:
        assert task.stop_condition, f"{task.id} missing stop_condition"
