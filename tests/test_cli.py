import au_radar
import pytest

from au_radar.catalogue import load_catalogue
from au_radar.cli import _build_plan, bundled_catalogue_path, build_parser, main, _run_metadata


def test_bundled_catalogue_exists():
    assert bundled_catalogue_path().exists()


def test_list_exits_zero_and_needs_no_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AU_RADAR_CONTACT", raising=False)

    assert main(["--list"]) == 0

    out = capsys.readouterr().out
    assert "passport" in out
    assert "Legislation comparators:" in out


def test_dry_run_chat_only_needs_no_contact_no_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AU_RADAR_CONTACT", raising=False)

    assert main(["--dry-run", "--services", "passport", "--agent-tasks", "none"]) == 0

    out = capsys.readouterr().out
    assert "dry run" in out.lower()
    assert "passport" in out
    assert "est. API calls" in out


def test_agent_run_without_contact_is_rejected(monkeypatch):
    monkeypatch.delenv("AU_RADAR_CONTACT", raising=False)

    with pytest.raises(SystemExit) as exc:
        main(["--dry-run", "--services", "none", "--agent-tasks", "passport_agent"])

    assert exc.value.code == 2


def test_agent_run_accepts_contact_from_env(monkeypatch, capsys):
    monkeypatch.setenv("AU_RADAR_CONTACT", "someone@example.org")

    assert main(["--dry-run", "--services", "none", "--agent-tasks", "passport_agent"]) == 0
    assert "dry run" in capsys.readouterr().out.lower()


def test_dry_run_never_enters_the_run_path(monkeypatch):
    import au_radar.cli as cli

    monkeypatch.setenv("AU_RADAR_CONTACT", "someone@example.org")
    monkeypatch.setattr(cli, "_run", lambda *a, **k: pytest.fail("_run must not be called for --dry-run"))

    assert main(["--dry-run"]) == 0


def test_custom_catalogue_is_loaded(tmp_path, capsys):
    catalogue = tmp_path / "mine.yaml"
    catalogue.write_text(
        "chat_services:\n"
        "  - id: only_one\n"
        "    name: Only service\n"
        "    domain: Test\n"
        "    agency: Test\n"
        "    turns: ['a', 'b', 'c']\n"
        "agent_tasks: []\n"
        "legislation_comparators: []\n"
    )

    assert main(["--dry-run", "--catalogue", str(catalogue), "--agent-tasks", "none"]) == 0
    assert "only_one" in capsys.readouterr().out


def test_custom_catalogue_plan_flags_not_radar_anchored(tmp_path, capsys):
    catalogue = tmp_path / "mine.yaml"
    catalogue.write_text(
        "chat_services:\n"
        "  - {id: s1, name: S1, domain: D, agency: A, turns: ['a','b','c']}\n"
        "agent_tasks: []\n"
        "legislation_comparators: []\n"
    )
    assert main(["--dry-run", "--catalogue", str(catalogue), "--agent-tasks", "none"]) == 0
    out = capsys.readouterr().out
    assert "NOT anchored to RADAR" in out


def test_malformed_catalogue_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("chat_services: [oops\n")  # invalid YAML
    with pytest.raises(SystemExit) as exc:
        main(["--dry-run", "--catalogue", str(bad)])
    assert exc.value.code == 2


def test_two_turn_catalogue_is_rejected(tmp_path):
    bad = tmp_path / "twoturn.yaml"
    bad.write_text(
        "chat_services:\n"
        "  - {id: s1, name: S1, domain: D, agency: A, turns: ['a','b']}\n"
        "agent_tasks: []\n"
        "legislation_comparators: []\n"
    )
    with pytest.raises(SystemExit) as exc:
        main(["--dry-run", "--catalogue", str(bad), "--agent-tasks", "none"])
    assert exc.value.code == 2


def test_nothing_selected_is_rejected():
    with pytest.raises(SystemExit) as exc:
        main(["--dry-run", "--services", "none", "--agent-tasks", "none"])
    assert exc.value.code == 2


def test_missing_catalogue_is_rejected(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["--dry-run", "--catalogue", str(tmp_path / "nope.yaml")])
    assert exc.value.code == 2


def test_unknown_service_id_is_rejected():
    with pytest.raises(SystemExit) as exc:
        main(["--dry-run", "--services", "not_a_real_service", "--agent-tasks", "none"])
    assert exc.value.code == 2


def test_run_metadata_shape():
    args = build_parser().parse_args(["--model", "m1", "--judge-model", "m2", "--n-trials", "3"])
    catalogue = load_catalogue(str(bundled_catalogue_path()))
    chat_services = list(catalogue.chat_services)
    agent_tasks = list(catalogue.agent_tasks)
    plan = _build_plan(args, catalogue, chat_services, agent_tasks)
    metadata = _run_metadata(args, plan, "m2", "c@example.org")

    assert metadata["au_radar_version"] == au_radar.__version__
    assert metadata["model"] == "m1"
    assert metadata["judge_model"] == "m2"
    assert metadata["n_trials"] == 3
    assert metadata["contact"] == "c@example.org"
    assert metadata["completed"] is False
    assert metadata["radar_anchored"] is True
    assert metadata["resolved_chat_ids"] == [s.id for s in chat_services]
    assert len(metadata["catalogue_sha256"]) == 64
    assert len(metadata["harness_source_sha256"]) == 64
    assert metadata["python_version"] == __import__("platform").python_version()
    assert "git_sha" in metadata and "git_dirty" in metadata
    assert metadata["timestamp_utc"].endswith("+00:00")


def test_console_entrypoint_is_importable():
    from au_radar.cli import main as entrypoint

    assert callable(entrypoint)
