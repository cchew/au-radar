"""Rebuild `findings-summary.md` from the committed `chat-legibility.json` and
`agent-operability.json` in a results directory, using the current report
generator. Offline, no API key. Use it to refresh the rendered summary after a
report-format change without re-running a live collection.

    python scripts/regenerate_findings_summary.py [results_dir]
"""
import json
import sys
from pathlib import Path

from au_radar.aggregate_agent import TaskAgentResult
from au_radar.aggregate_chat import ServiceChatResult
from au_radar.report import write_findings_summary
from au_radar.scorecard import build_legislation_scorecard, build_scorecard

LEGISLATION_PREFIX = "legislation_"


def _load(path: Path, cls, keep):
    return [cls(**{k: v for k, v in row.items() if k in keep}) for row in json.loads(path.read_text())]


def main() -> int:
    results_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
    chat_results = _load(
        results_dir / "chat-legibility.json", ServiceChatResult,
        {"service_id", "mean_total", "spread", "trial_count"},
    )
    agent_results = _load(
        results_dir / "agent-operability.json", TaskAgentResult,
        {"task_id", "mean_total", "spread", "disagreement_flagged", "trial_count"},
    )

    leg_service_ids = {r.service_id for r in chat_results if r.service_id.startswith(LEGISLATION_PREFIX)}
    leg_task_ids = {r.task_id for r in agent_results if r.task_id.startswith(LEGISLATION_PREFIX)}

    scorecard = build_scorecard(chat_results, agent_results, leg_task_ids, leg_service_ids)
    legislation = None
    if leg_service_ids:
        legislation = build_legislation_scorecard(
            [r for r in chat_results if r.service_id in leg_service_ids],
            [r for r in agent_results if r.task_id in leg_task_ids],
        )

    out = results_dir / "findings-summary.md"
    write_findings_summary(scorecard, legislation, chat_results, agent_results, str(out))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
