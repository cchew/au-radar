from au_radar.scorecard import LegislationRow, LegislationScorecard, Scorecard
from au_radar.report import write_findings_summary


def test_write_findings_summary_includes_radar_anchor_and_legislation_table(tmp_path):
    scorecard = Scorecard(chat_mean=7.5, agent_mean=5.0, overall_score=6.25)
    legislation = LegislationScorecard(rows=[
        LegislationRow(comparator_id="legislation_lex_au", chat_score=9.0, agent_score=8.0),
        LegislationRow(comparator_id="legislation_austlii", chat_score=6.0, agent_score=5.0),
    ])
    out_path = tmp_path / "findings-summary.md"

    write_findings_summary(scorecard, legislation, str(out_path))

    content = out_path.read_text()
    assert "6.25" in content
    assert "7.24" in content  # RADAR anchor score must appear for comparability
    assert "legislation_lex_au" in content
    assert "legislation_austlii" in content
    assert "Single model" in content  # limitations must be stated, not just the numbers
    assert "no external validation anchor" in content  # legislation-extension caveat
