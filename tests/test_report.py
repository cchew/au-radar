from au_radar.aggregate_agent import DISAGREEMENT_THRESHOLD, TaskAgentResult
from au_radar.aggregate_chat import ServiceChatResult
from au_radar.scorecard import LegislationRow, LegislationScorecard, Scorecard
from au_radar.report import write_findings_summary


def test_write_findings_summary_includes_radar_anchor_and_legislation_table(tmp_path):
    scorecard = Scorecard(chat_mean=7.5, agent_mean=5.0, overall_score=6.25)
    legislation = LegislationScorecard(rows=[
        LegislationRow(comparator_id="legislation_lex_au", chat_score=9.0, agent_score=8.0),
        LegislationRow(comparator_id="legislation_austlii", chat_score=6.0, agent_score=5.0),
    ])
    chat_results = [
        ServiceChatResult(service_id="passport", mean_total=8.0, spread=0.5, trial_count=2),
        ServiceChatResult(service_id="file_tax", mean_total=7.0, spread=0.3, trial_count=2),
    ]
    agent_results = [
        TaskAgentResult(
            task_id="passport_agent", mean_total=6.0, spread=1.0,
            disagreement_flagged=False, trial_count=2,
        ),
        TaskAgentResult(
            task_id="ato_agent", mean_total=4.4, spread=4.6,
            disagreement_flagged=True, trial_count=2,
        ),
    ]
    out_path = tmp_path / "findings-summary.md"

    write_findings_summary(scorecard, legislation, chat_results, agent_results, str(out_path))

    content = out_path.read_text()
    assert "6.25" in content
    assert "7.24" in content  # RADAR anchor score must appear for comparability
    assert "legislation_lex_au" in content
    assert "legislation_austlii" in content
    assert "Single model" in content  # limitations must be stated, not just the numbers
    assert "no external validation anchor" in content  # legislation-extension caveat

    # Per-service/per-task mean +/- spread table
    assert "passport" in content and "8.0" in content
    assert f"DISAGREEMENT_THRESHOLD = {DISAGREEMENT_THRESHOLD}" in content

    # Disagreement section: flagged task appears, non-flagged does not appear there
    assert "Runs that disagreed" in content
    assert "ato_agent" in content
    disagreement_section = content.split("### Runs that disagreed")[1].split("## Limitations")[0]
    assert "ato_agent" in disagreement_section
    assert "passport_agent" not in disagreement_section


def test_write_findings_summary_states_no_disagreement_when_none_flagged(tmp_path):
    scorecard = Scorecard(chat_mean=7.5, agent_mean=5.0, overall_score=6.25)
    legislation = LegislationScorecard(rows=[])
    chat_results = [ServiceChatResult(service_id="passport", mean_total=8.0, spread=0.5, trial_count=2)]
    agent_results = [
        TaskAgentResult(
            task_id="passport_agent", mean_total=6.0, spread=0.5,
            disagreement_flagged=False, trial_count=2,
        ),
    ]
    out_path = tmp_path / "findings-summary.md"

    write_findings_summary(scorecard, legislation, chat_results, agent_results, str(out_path))

    content = out_path.read_text()
    assert "No disagreement flagged across repeated trials." in content
