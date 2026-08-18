import json
from dataclasses import asdict, dataclass, field

from au_radar.judge import AgentScore

DISAGREEMENT_THRESHOLD = 2.0


@dataclass
class TaskAgentResult:
    task_id: str
    mean_total: float
    spread: float
    disagreement_flagged: bool
    trial_count: int
    trial_scores: list[AgentScore] = field(default_factory=list)


def aggregate_agent_scores(task_id: str, scores: list[AgentScore]) -> TaskAgentResult:
    totals = [s.total for s in scores]
    spread = round(max(totals) - min(totals), 2)
    return TaskAgentResult(
        task_id=task_id,
        mean_total=round(sum(totals) / len(totals), 2),
        spread=spread,
        disagreement_flagged=spread > DISAGREEMENT_THRESHOLD,
        trial_count=len(scores),
        trial_scores=scores,
    )


def write_agent_results(results: list[TaskAgentResult], path: str) -> None:
    with open(path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
