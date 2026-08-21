# au-radar

A RADAR-consistent AU sovereign-legibility benchmark: how well can an LLM *describe*
Australian federal government services versus actually *reach* them, and how does that
compare to a similar test applied to legislation lookup?

> **Status: first full live run complete (2026-08-21).** Overall AU score 5.32/10
> (chat 6.1, agent 4.55) vs RADAR's published Australia score of 7.24. Results,
> charts, and the findings summary are in [`results/`](results/). Known harness
> gaps found during that run are logged in [`FUTURE.md`](FUTURE.md).

## What this measures

Two harnesses, both scored 0-10 via LLM-as-judge:

- **Chat mode (informational legibility).** A three-turn citizen-style conversation
  per service, judged on verifiability, specificity, depth, and transparency.
- **Agent mode (operability).** A tool-using agent tries to navigate to a service's
  entry point, judged on findability, portal quality, agent permeability, service
  access, structured access, and navigation efficiency (the last computed from step
  count, not self-reported). Agent runs stop hard at any login/auth boundary — they
  never authenticate or submit data.

The general-services basket (15 chat services, 4 agent tasks) targets genuinely
federal Australian services, so results are comparable to RADAR's own published
Australia score. A separate legislation-legibility extension applies the same two
rubrics to legislative-provision lookup (lex-au vs the Federal Register of
Legislation vs AustLII) — a domain RADAR never tested — and is reported as a
standalone mini-scorecard, not folded into the overall AU number.

Every prompt runs 2-3 times; results are reported as mean ± spread, and any task
where repeated runs disagree by more than `DISAGREEMENT_THRESHOLD` is itself
reported as a finding, not averaged away.

## RADAR

This project replicates, where possible, the methodology of:

> **RADAR** (*Readiness for AI Discovery and Agentic Reach*), World Bank preprint.
> Jordan, Peixoto, Ramos-Maqueda. July 2026.

RADAR measured whether AI systems can describe and actually reach government
services across 166 countries, finding a positive "guidance-to-reach gap" in every
one. Australia scored 7.24 overall (rank 27/166) under RADAR's own methodology —
used here as a comparability anchor, not a like-for-like replication (this study is
single-model, single-country, a service subset, and weighted differently; see the
limitations section of the generated findings summary).

## Install

```bash
pip install -e .
playwright install chromium
```

## Run tests

```bash
pytest
```

Tests run entirely against local fixtures (`tests/fixtures/`) and fake Anthropic
clients — no network calls, no API key required. A separate manual smoke test
(`scripts/run_live_smoke_test.py`) makes real API calls and is never run via pytest;
see its module docstring before running it.

## License

MIT — see [`LICENSE`](LICENSE).
