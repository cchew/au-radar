from dataclasses import dataclass

RADAR_ANCHOR_SCORE = 7.24
RADAR_ANCHOR_RANK = 27


@dataclass
class Scorecard:
    chat_mean: float
    agent_mean: float
    overall_score: float
    radar_anchor_score: float | None = RADAR_ANCHOR_SCORE
    radar_anchor_rank: int | None = RADAR_ANCHOR_RANK


def build_scorecard(
    chat_results, agent_results, legislation_task_ids: set[str], legislation_service_ids: set[str],
    *, radar_anchored: bool = True,
) -> Scorecard:
    non_legislation_chat = [r for r in chat_results if r.service_id not in legislation_service_ids]
    chat_mean = round(sum(r.mean_total for r in non_legislation_chat) / len(non_legislation_chat), 2)

    non_legislation_agent = [r for r in agent_results if r.task_id not in legislation_task_ids]
    agent_mean = round(
        sum(r.mean_total for r in non_legislation_agent) / len(non_legislation_agent), 2
    )

    # The published RADAR anchor only means something for a RADAR-style federal
    # basket; a custom catalogue gets an internally consistent score with no
    # anchor claimed.
    return Scorecard(
        chat_mean=chat_mean,
        agent_mean=agent_mean,
        overall_score=round((chat_mean + agent_mean) / 2, 2),
        radar_anchor_score=RADAR_ANCHOR_SCORE if radar_anchored else None,
        radar_anchor_rank=RADAR_ANCHOR_RANK if radar_anchored else None,
    )


@dataclass
class LegislationRow:
    comparator_id: str
    chat_score: float
    agent_score: float


@dataclass
class LegislationScorecard:
    rows: list[LegislationRow]


def build_legislation_scorecard(legislation_chat_results, legislation_agent_results) -> LegislationScorecard:
    agent_by_id = {r.task_id: r.mean_total for r in legislation_agent_results}
    rows = []
    for chat_result in legislation_chat_results:
        if chat_result.service_id not in agent_by_id:
            raise ValueError(
                f"no agent result for legislation comparator {chat_result.service_id}"
            )
        rows.append(
            LegislationRow(
                comparator_id=chat_result.service_id,
                chat_score=chat_result.mean_total,
                agent_score=agent_by_id[chat_result.service_id],
            )
        )
    return LegislationScorecard(rows=rows)
