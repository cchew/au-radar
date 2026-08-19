from au_radar.aggregate_chat import ServiceChatResult
from au_radar.aggregate_agent import TaskAgentResult
from au_radar.charts import plot_service_scores, plot_guidance_to_reach_gap


def test_plot_service_scores_creates_file(tmp_path):
    results = [
        ServiceChatResult(service_id="passport", mean_total=8.0, spread=0.5, trial_count=2),
        ServiceChatResult(service_id="file_tax", mean_total=7.0, spread=0.3, trial_count=2),
    ]
    out_path = tmp_path / "service-scores.png"

    plot_service_scores(results, str(out_path))

    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_guidance_to_reach_gap_creates_file(tmp_path):
    chat_results = [ServiceChatResult(service_id="passport", mean_total=8.0, spread=0.5, trial_count=2)]
    agent_results = [
        TaskAgentResult(
            task_id="passport_agent", mean_total=5.0, spread=0.5,
            disagreement_flagged=False, trial_count=2,
        )
    ]
    out_path = tmp_path / "gap.png"

    match_count = plot_guidance_to_reach_gap(
        chat_results, agent_results, str(out_path), task_to_chat_id={"passport_agent": "passport"},
    )

    assert out_path.exists()
    assert out_path.stat().st_size > 0
    assert match_count > 0
    assert match_count == 1


def test_plot_guidance_to_reach_gap_zero_matches_returns_zero(tmp_path):
    chat_results = [ServiceChatResult(service_id="passport", mean_total=8.0, spread=0.5, trial_count=2)]
    agent_results = [
        TaskAgentResult(
            task_id="passport_agent", mean_total=5.0, spread=0.5,
            disagreement_flagged=False, trial_count=2,
        )
    ]
    out_path = tmp_path / "gap-empty.png"

    match_count = plot_guidance_to_reach_gap(
        chat_results, agent_results, str(out_path), task_to_chat_id={},
    )

    assert match_count == 0
