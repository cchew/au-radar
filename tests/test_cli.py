import au_radar
import pytest

from au_radar.cli import bundled_catalogue_path, build_parser, main, _run_metadata


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
    assert "API calls (UB)" in out


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
    metadata = _run_metadata(args, bundled_catalogue_path(), "m2", "c@example.org")

    assert metadata["au_radar_version"] == au_radar.__version__
    assert metadata["model"] == "m1"
    assert metadata["judge_model"] == "m2"
    assert metadata["n_trials"] == 3
    assert metadata["contact"] == "c@example.org"
    assert len(metadata["catalogue_sha256"]) == 64
    assert metadata["timestamp_utc"].endswith("+00:00")


def test_console_entrypoint_is_importable():
    from au_radar.cli import main as entrypoint

    assert callable(entrypoint)
