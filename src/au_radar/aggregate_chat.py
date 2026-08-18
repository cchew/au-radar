import json
from dataclasses import asdict, dataclass, field

from au_radar.judge import ChatScore


@dataclass
class ServiceChatResult:
    service_id: str
    mean_total: float
    spread: float
    trial_count: int
    trial_scores: list[ChatScore] = field(default_factory=list)


def aggregate_chat_scores(service_id: str, scores: list[ChatScore]) -> ServiceChatResult:
    totals = [s.total for s in scores]
    return ServiceChatResult(
        service_id=service_id,
        mean_total=round(sum(totals) / len(totals), 2),
        spread=round(max(totals) - min(totals), 2),
        trial_count=len(scores),
        trial_scores=scores,
    )


def write_chat_results(results: list[ServiceChatResult], path: str) -> None:
    with open(path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
