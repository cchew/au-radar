from au_radar.scorecard import LegislationScorecard, Scorecard


def write_findings_summary(scorecard: Scorecard, legislation: LegislationScorecard, output_path: str) -> None:
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
        "## Limitations",
        "",
        "- Single model (Claude only) — no cross-model corroboration; self-evaluation-bias risk "
        "is real without RADAR's cross-model judge design.",
        "- Single country — reliability rests on repeated-trial averaging, not RADAR's "
        "166-country aggregation.",
        "- English-only chat prompts — no AU-community-language legibility signal.",
        "- Agent runs from a single network vantage point.",
        "- No manual ground-truth verification of judge or agent scores.",
    ]

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")
