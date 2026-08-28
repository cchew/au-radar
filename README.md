# au-radar

A RADAR-consistent AU sovereign-legibility benchmark: how well can an LLM *describe*
Australian federal government services versus actually *reach* them, and how does that
compare to a similar test applied to legislation lookup?

> **Status: v0.2.0 — packaged as an open benchmark with recorded run provenance.**
> First full live run (2026-08-21, v0.1.2) scored Australia 5.32/10 (chat 6.1,
> agent 4.55) against RADAR's published 7.24. Results, charts, and the findings
> summary are in [`results/`](results/). v0.2.0 adds a real CLI, a run-metadata
> record, a bring-your-own-catalogue path, and hardened auth-boundary detection —
> see [Versions](#versions). Known gaps are in [`FUTURE.md`](FUTURE.md).

## What this measures

Two harnesses, both scored 0-10 via LLM-as-judge:

- **Chat mode (informational legibility).** A three-turn citizen-style conversation
  per service, judged on verifiability, specificity, depth, and transparency.
- **Agent mode (operability).** A tool-using agent tries to navigate to a service's
  entry point, judged on findability, portal quality, agent permeability, service
  access, structured access, and navigation efficiency (the last computed from step
  count, not self-reported). Agent runs stop hard at any login/auth boundary — they
  never authenticate or submit data.

The bundled general-services basket (15 chat services, 4 agent tasks) targets
genuinely federal Australian services and is scored the way RADAR scored its own,
so the overall number is a *comparability anchor* against RADAR's published
Australia score — not a like-for-like replication (single-model, service subset,
different weighting; see [RADAR](#radar) and the generated findings summary). A
separate legislation-legibility extension applies the same two rubrics to
legislative-provision lookup (lex-au vs the Federal Register of Legislation vs
AustLII) — a domain RADAR never tested — and is reported as a standalone
mini-scorecard, not folded into the overall number.

One agent sub-score, navigation efficiency, uses a project-defined
step-count-to-0-4 mapping rather than a RADAR-specified formula.

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

## Run the benchmark

```bash
au-radar --list          # show the catalogue (chat services, agent tasks, comparators)
au-radar --dry-run --agent-tasks none   # validate config + print the run plan, no API calls
```

A real run needs `ANTHROPIC_API_KEY` (a `.env` file in the working directory is
loaded automatically). Agent runs additionally need an identifying contact for the
crawler User-Agent (`--contact you@example.org` or `$AU_RADAR_CONTACT`) — the
harness will not hit a government site anonymously.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export AU_RADAR_CONTACT="you@example.org"

# Pilot: one agent task, one trial.
au-radar --services none --agent-tasks passport_agent --n-trials 1

# Full run, legislation extension included (--legislation-provision sets the clause).
au-radar --include-legislation
```

`au-radar --help` lists every flag (`--model`, `--judge-model`, `--n-trials`,
`--max-steps`, `--max-retries`, `--out-dir`, `--headless/--no-headless`,
`--legislation-provision`).

Outputs land in `--out-dir` (default `results/`): `chat-legibility.json`,
`agent-operability.json`, `findings-summary.md`, two PNG charts, and
`run-metadata.json` (see [Reproducibility](#reproducibility)).
`scripts/regenerate_findings_summary.py` re-renders the summary from the two
JSON files offline.

`python -m au_radar ...` is equivalent to `au-radar ...`.
`scripts/run_live_collection.py` is a deprecated shim kept for old invocations.

This is a deliberate, human-supervised run. Never invoke it from pytest; watch the
output while it runs.

## Point it at your own domain list

`--catalogue PATH` swaps the bundled AU basket for your own. Copy
[`examples/catalogue.example.yaml`](examples/catalogue.example.yaml) — it documents
every field — and edit it:

```bash
au-radar --catalogue my-catalogue.yaml --agent-tasks none        # chat only
au-radar --catalogue my-catalogue.yaml --contact you@example.org  # + agent runs
```

A catalogue has three top-level lists (any may be empty):

| Key | Purpose | Item fields |
|---|---|---|
| `chat_services` | informational-legibility conversations | `id`, `name`, `domain`, `agency`, `turns` (exactly 3) |
| `agent_tasks` | agentic-operability navigation tasks | `id`, `name`, `description`, `target_hint`, `stop_condition`, optional `chat_service_id` |
| `legislation_comparators` | optional `--include-legislation` trio | `id`, `name`, `base_url` |

Scores are only comparable to RADAR's published country numbers if the basket is
built the way RADAR built theirs (design spec §3–§4). With a custom `--catalogue`,
au-radar drops the RADAR anchor from the scorecard and report, retitles the
summary, and prints a reminder on `--dry-run` and after the run: you get an
internally consistent score, not a RADAR-anchored one.

## Reproducibility

Every run writes `results/run-metadata.json`: au-radar version, git SHA and
dirty flag, Python / platform / `anthropic` / `playwright` / Chromium versions, a
hash of the prompt-and-rubric source, the model and judge-model ids, the catalogue
path and SHA-256, the resolved service/task id list, `DISAGREEMENT_THRESHOLD`,
every run parameter, and a `completed` flag (set true only when the run finished).

What is **not** pinned, and moves scores run-to-run regardless: LLM temperature
(left at the Anthropic API default), the model itself (recorded as an alias, not a
dated snapshot), and any non-determinism in the judge. Raw transcripts and agent
traces are not retained. So a re-run reproduces a *configuration* and should land
close, not a byte-identical *result*; treat the metadata as provenance, not a
guarantee. A score is only comparable to another run when the model, the prompts
(`harness_source_sha256`), and the catalogue (`catalogue_sha256`) are held
constant.

## Known caveats in the output

- **No `hover` tool.** A task whose only path to a service runs through a
  hover-to-open menu is unreachable by design, so a low agent score there reflects
  a harness capability gap as much as a site problem — it substantially depressed
  `passport_agent` in the reference AU run. Surfaced in every generated
  `findings-summary.md` and on stderr at the end of an agent run. (The committed
  `results/findings-summary.md` is regenerated from the v0.1.2 data and carries
  the caveat.)
- **Navigation efficiency** is a project-defined mapping, not a RADAR formula.
- **Single model, English only, single network vantage point, no ground-truth
  verification.** See the Limitations section of `findings-summary.md`.

## Run tests

```bash
pytest
```

Tests run entirely against local fixtures (`tests/fixtures/`) and fake Anthropic
clients — no network calls, no API key required.

## Versions

| Version | Notes |
|---|---|
| 0.2.0 | `au-radar` CLI (`--list`, `--dry-run`, `--catalogue`, `--model`, `--judge-model`, `--contact`); `run-metadata.json` with full provenance; bring-your-own-catalogue (drops the RADAR anchor); catalogue schema validation; hardened auth-boundary detection (late-injected fields, one-time-code inputs, parsed-URL OIDC/SAML matching, settle-on-failed-action); hover-tool + nav-efficiency caveats in every generated report. |
| 0.1.2 | First full live run (AU 5.32 vs RADAR 7.24); multi-tool-use and agent-loop token-budget fixes. |
| 0.1.1 | Live-run crash fixes (thinking blocks, judge JSON parsing, `max_tokens` truncation). |
| 0.1.0 | Benchmark harness complete (chat + agent legibility, RADAR scoring, legislation extension, charts, findings report). No live data. |

## License

MIT — see [`LICENSE`](LICENSE).
