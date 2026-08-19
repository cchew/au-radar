import json

from au_radar.judge import AgentScore
from au_radar.aggregate_agent import aggregate_agent_scores, write_agent_results


def _score(total, raw=16):
    return AgentScore(
        findability=1, portal_quality=3, agent_permeability=3, service_access=3,
        structured_access=0, navigation_efficiency=3, raw=raw, total=total, justification="j",
        model="claude-sonnet-5",
    )


def test_aggregate_agent_scores_flags_disagreement():
    scores = [_score(6.7), _score(2.1)]  # large gap between repeat runs

    result = aggregate_agent_scores("passport_agent", scores)

    assert result.task_id == "passport_agent"
    assert result.mean_total == 4.4
    assert result.disagreement_flagged is True  # spread > 2.0 points


def test_aggregate_agent_scores_no_disagreement_when_consistent():
    scores = [_score(6.7), _score(6.5)]

    result = aggregate_agent_scores("passport_agent", scores)

    assert result.disagreement_flagged is False


def test_write_agent_results_produces_valid_json(tmp_path):
    results = [aggregate_agent_scores("passport_agent", [_score(6.7)])]
    out_path = tmp_path / "agent-operability.json"

    write_agent_results(results, str(out_path))

    data = json.loads(out_path.read_text())
    assert data[0]["task_id"] == "passport_agent"
    assert data[0]["trial_scores"][0]["model"] == "claude-sonnet-5"  # model string survives to disk
