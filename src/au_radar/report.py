from au_radar.aggregate_agent import DISAGREEMENT_THRESHOLD, TaskAgentResult
from au_radar.aggregate_chat import ServiceChatResult
from au_radar.scorecard import LegislationScorecard, Scorecard


def write_findings_summary(
    scorecard: Scorecard,
    legislation: LegislationScorecard,
    chat_results: list[ServiceChatResult],
    agent_results: list[TaskAgentResult],
    output_path: str,
) -> None:
    lines = [
        "# AU Sovereign Legibility — Findings Summary",
        "",
        f"**Overall AU score:** {scorecard.overall_score} "
        f"(chat mean {scorecard.chat_mean}, agent mean {scorecard.agent_mean})",
        "",
        f"**RADAR anchor (Australia, published):** {scorecard.radar_anchor_score}, "
        f"rank {scorecard.radar_anchor_rank}/166. Methodological differences from this study "
        "(single-model, single-country, service-subset, different weighting) apply whenever "
        "these two numbers are compared — see spec limitations (§9).",
        "",
        "## Legislation legibility",
        "",
        "| Comparator | Chat score | Agent score |",
        "|---|---|---|",
    ]
    for row in legislation.rows:
        lines.append(f"| {row.comparator_id} | {row.chat_score} | {row.agent_score} |")

    lines += [
        "",
        "Legislation-legibility scores are exploratory: unlike the general-services basket, "
        "there is no published RADAR result for legislation lookup, so no external validation "
        "anchor exists for this comparison.",
        "",
        "## Reliability across repeated trials",
        "",
        f"Every chat and agent prompt runs 2-3 times (spec §3.2); results below are reported as "
        f"mean ± spread per service/task, not a single point score. A task's spread is flagged as "
        f"disagreement when it exceeds `DISAGREEMENT_THRESHOLD = {DISAGREEMENT_THRESHOLD}` "
        "(see `aggregate_agent.py`).",
        "",
        "### Chat services (mean ± spread)",
        "",
        "| Service | Mean | Spread |",
        "|---|---|---|",
    ]
    for chat_result in chat_results:
        lines.append(f"| {chat_result.service_id} | {chat_result.mean_total} | ± {chat_result.spread} |")

    lines += [
        "",
        "### Agent tasks (mean ± spread)",
        "",
        "The agent has no `hover` tool: a task whose only path to a service runs through "
        "a hover-to-open menu is unreachable by design, so a low agent score there "
        "reflects a harness capability gap as much as a site problem.",
        "",
        "| Task | Mean | Spread |",
        "|---|---|---|",
    ]
    for agent_result in agent_results:
        lines.append(f"| {agent_result.task_id} | {agent_result.mean_total} | ± {agent_result.spread} |")

    lines += [
        "",
        "### Runs that disagreed",
        "",
    ]
    disagreements = [r for r in agent_results if r.disagreement_flagged]
    if disagreements:
        lines.append(
            f"Repeated agent trials disagreed by more than {DISAGREEMENT_THRESHOLD} points "
            "(inconsistent navigation, not averaged away) on:"
        )
        lines.append("")
        for r in disagreements:
            lines.append(f"- `{r.task_id}` — spread {r.spread} across {r.trial_count} trials")
    else:
        lines.append("No disagreement flagged across repeated trials.")

    lines += [
        "",
        "## Limitations",
        "",
        "- Single model (Claude only) — no cross-model corroboration; self-evaluation-bias risk "
        "is real without RADAR's cross-model judge design.",
        "- Single country — reliability rests on repeated-trial averaging, not RADAR's "
        "166-country aggregation.",
        "- English-only chat prompts — no AU-community-language legibility signal.",
        "- Agent runs from a single network vantage point.",
        "- No manual ground-truth verification of judge or agent scores.",
        "- The agent has no `hover` tool, so hover-only navigation menus are unreachable "
        "by design; affected agent scores understate real-world reachability.",
    ]

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")
