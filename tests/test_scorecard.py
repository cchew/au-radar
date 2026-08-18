from au_radar.aggregate_chat import ServiceChatResult
from au_radar.aggregate_agent import TaskAgentResult
from au_radar.scorecard import build_scorecard, build_legislation_scorecard

RADAR_ANCHOR_SCORE = 7.24
RADAR_ANCHOR_RANK = 27


def _chat_result(service_id, mean):
    return ServiceChatResult(service_id=service_id, mean_total=mean, spread=0.5, trial_count=2)


def _agent_result(task_id, mean):
    return TaskAgentResult(
        task_id=task_id, mean_total=mean, spread=0.5, disagreement_flagged=False, trial_count=2,
    )


def test_build_scorecard_excludes_legislation_task_from_overall():
    chat_results = [_chat_result("passport", 8.0), _chat_result("file_tax", 7.0)]
    agent_results = [
        _agent_result("passport_agent", 6.0),
        _agent_result("ato_agent", 4.0),
        _agent_result("legislation_lex_au", 9.0),  # must NOT count toward overall
    ]

    scorecard = build_scorecard(
        chat_results, agent_results, legislation_task_ids={"legislation_lex_au"},
    )

    assert scorecard.chat_mean == 7.5
    assert scorecard.agent_mean == 5.0  # mean of 6.0 and 4.0 only
    assert scorecard.overall_score == 6.25  # (7.5 + 5.0) / 2
    assert scorecard.radar_anchor_score == RADAR_ANCHOR_SCORE
    assert scorecard.radar_anchor_rank == RADAR_ANCHOR_RANK


def test_build_legislation_scorecard_is_separate_and_unweighted():
    chat = [_chat_result("legislation_lex_au", 9.0), _chat_result("legislation_austlii", 6.0)]
    agent = [_agent_result("legislation_lex_au", 8.0), _agent_result("legislation_austlii", 5.0)]

    scorecard = build_legislation_scorecard(chat, agent)

    assert len(scorecard.rows) == 2
    lex_au_row = next(r for r in scorecard.rows if r.comparator_id == "legislation_lex_au")
    assert lex_au_row.chat_score == 9.0
    assert lex_au_row.agent_score == 8.0
