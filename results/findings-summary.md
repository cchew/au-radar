# AU Sovereign Legibility — Findings Summary

**Overall AU score:** 5.32 (chat mean 6.1, agent mean 4.55)

**RADAR anchor (Australia, published):** 7.24, rank 27/166. Methodological differences from this study (single-model, single-country, service-subset, different weighting) apply whenever these two numbers are compared — see spec limitations (§9).

## Legislation legibility

| Comparator | Chat score | Agent score |
|---|---|---|
| legislation_lex_au | 8.0 | 1.7 |
| legislation_federal_register | 7.5 | 2.3 |
| legislation_austlii | 7.0 | 1.45 |

Legislation-legibility scores are exploratory: unlike the general-services basket, there is no published RADAR result for legislation lookup, so no external validation anchor exists for this comparison.

## Reliability across repeated trials

Every chat and agent prompt runs 2-3 times (spec §3.2); results below are reported as mean ± spread per service/task, not a single point score. A task's spread is flagged as disagreement when it exceeds `DISAGREEMENT_THRESHOLD = 2.0` (see `aggregate_agent.py`).

### Chat services (mean ± spread)

| Service | Mean | Spread |
|---|---|---|
| passport | 5.0 | ± 2.0 |
| pbs_medication | 5.5 | ± 1.0 |
| gp_appointment | 7.5 | ± 1.0 |
| diagnostics | 6.5 | ± 3.0 |
| job_search | 6.0 | ± 2.0 |
| training | 7.0 | ± 0.0 |
| jobseeker | 6.5 | ± 1.0 |
| parental_leave_pay | 5.5 | ± 1.0 |
| file_tax | 4.5 | ± 1.0 |
| contest_tax | 6.5 | ± 1.0 |
| tax_refund | 6.5 | ± 5.0 |
| tax_deductions | 4.0 | ± 0.0 |
| myGov | 7.5 | ± 1.0 |
| abn | 6.0 | ± 2.0 |
| medicare_enrolment | 7.0 | ± 0.0 |
| legislation_lex_au | 8.0 | ± 2.0 |
| legislation_federal_register | 7.5 | ± 1.0 |
| legislation_austlii | 7.0 | ± 0.0 |

### Agent tasks (mean ± spread)

| Task | Mean | Spread |
|---|---|---|
| passport_agent | 1.7 | ± 0.0 |
| ato_agent | 3.35 | ± 2.5 |
| medicare_agent | 6.45 | ± 0.5 |
| abn_agent | 6.7 | ± 0.0 |
| legislation_lex_au | 1.7 | ± 0.0 |
| legislation_federal_register | 2.3 | ± 0.4 |
| legislation_austlii | 1.45 | ± 0.5 |

### Runs that disagreed

Repeated agent trials disagreed by more than 2.0 points (inconsistent navigation, not averaged away) on:

- `ato_agent` — spread 2.5 across 2 trials

## Limitations

- Single model (Claude only) — no cross-model corroboration; self-evaluation-bias risk is real without RADAR's cross-model judge design.
- Single country — reliability rests on repeated-trial averaging, not RADAR's 166-country aggregation.
- English-only chat prompts — no AU-community-language legibility signal.
- Agent runs from a single network vantage point.
- No manual ground-truth verification of judge or agent scores.
