import json

from au_radar.judge import ChatScore
from au_radar.aggregate_chat import aggregate_chat_scores, write_chat_results


def test_aggregate_chat_scores_computes_mean_and_spread():
    scores = [
        ChatScore(verifiability=3, specificity=2, depth=2, transparency=1, total=8.0, justification="j1", model="claude-sonnet-5"),
        ChatScore(verifiability=2, specificity=2, depth=2, transparency=1, total=7.0, justification="j2", model="claude-sonnet-5"),
        ChatScore(verifiability=3, specificity=3, depth=2, transparency=1, total=9.0, justification="j3", model="claude-sonnet-5"),
    ]

    result = aggregate_chat_scores("passport", scores)

    assert result.service_id == "passport"
    assert result.mean_total == 8.0
    assert result.spread == 2.0  # max - min
    assert result.trial_count == 3
    assert all(s.model == "claude-sonnet-5" for s in result.trial_scores)


def test_write_chat_results_produces_valid_json(tmp_path):
    results = [aggregate_chat_scores("passport", [
        ChatScore(verifiability=3, specificity=2, depth=2, transparency=1, total=8.0, justification="j", model="claude-sonnet-5"),
    ])]
    out_path = tmp_path / "chat-legibility.json"

    write_chat_results(results, str(out_path))

    data = json.loads(out_path.read_text())
    assert data[0]["service_id"] == "passport"
    assert data[0]["mean_total"] == 8.0
    assert data[0]["trial_scores"][0]["model"] == "claude-sonnet-5"  # model string survives to disk
