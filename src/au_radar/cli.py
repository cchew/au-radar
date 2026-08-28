"""au-radar command-line interface.

Runs the live data-collection benchmark: real Anthropic API calls and, for
agent tasks, a real Chromium browser driven against real public websites. Point
it at the bundled AU federal-services catalogue (the default) or at your own
domain list with --catalogue (see examples/catalogue.example.yaml for the
schema).

This is the "separate, manual, human-approved live data-collection run" the
implementation plan scoped out of the automated build. Never run it from
pytest. Invoke it deliberately and watch the output.

Examples:

    au-radar --list
    au-radar --dry-run
    au-radar --services none --agent-tasks passport_agent --contact you@example.org
    au-radar --catalogue my-domains.yaml --agent-tasks none
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import au_radar
from au_radar.catalogue import load_catalogue

DEFAULT_MODEL = "claude-sonnet-5"
CONTACT_ENV = "AU_RADAR_CONTACT"
API_KEY_ENV = "ANTHROPIC_API_KEY"
USER_AGENT_NOTE = "au-radar/{version} (+contact: {contact}; non-authenticating research benchmark, see spec §7)"

HOVER_CAVEAT = (
    "Caveat: au-radar's agent has no `hover` tool. Any task whose only path to a "
    "service runs through a hover-to-open menu is unreachable by design, so a low "
    "agent score on such a task reflects a harness capability gap as much as a site "
    "problem. Name this wherever those scores are quoted."
)


def bundled_catalogue_path() -> Path:
    """The AU federal-services catalogue shipped inside the package."""
    return Path(au_radar.__file__).resolve().parent / "data" / "catalogue.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="au-radar",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--catalogue", type=Path, default=None,
        help="path to a catalogue YAML (default: the bundled AU federal-services "
             "catalogue). See examples/catalogue.example.yaml for the schema.",
    )
    parser.add_argument("--services", default="all", help="comma-separated chat service ids, 'all', or 'none'")
    parser.add_argument("--agent-tasks", default="all", help="comma-separated agent task ids, 'all', or 'none'")
    parser.add_argument("--include-legislation", action="store_true", help="also run the legislation comparator trio")
    parser.add_argument("--legislation-provision", default="Fair Work Act 2009 s 65")
    parser.add_argument("--n-trials", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--max-retries", type=int, default=3, help="spec §7: <=3 retries per task")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--judge-model", default=None, help="defaults to --model")
    parser.add_argument(
        "--contact", default=None,
        help=f"identifying contact for the crawler User-Agent, or set ${CONTACT_ENV}. "
             "Required for agent runs (spec §7: no impersonation).",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("results"))
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--list", action="store_true", dest="list_catalogue", help="print the catalogue and exit")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="validate config, print the run plan and an upper-bound API-call estimate, make no calls",
    )
    return parser


def _select(all_items, selector, id_attr="id"):
    if selector == "none":
        return []
    if selector == "all":
        return list(all_items)
    wanted = {s.strip() for s in selector.split(",") if s.strip()}
    selected = [item for item in all_items if getattr(item, id_attr) in wanted]
    missing = wanted - {getattr(item, id_attr) for item in selected}
    if missing:
        raise ValueError(f"unknown id(s) not in catalogue: {sorted(missing)}")
    return selected


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _print_catalogue(catalogue) -> None:
    print("Chat services:")
    for s in catalogue.chat_services:
        print(f"  {s.id:<28} {s.name}")
    print("\nAgent tasks:")
    for t in catalogue.agent_tasks:
        print(f"  {t.id:<28} {t.name}")
    print("\nLegislation comparators:")
    for c in catalogue.legislation_comparators:
        print(f"  {c.id:<28} {c.name}")


def _legislation_items(catalogue, provision: str):
    from au_radar.legislation import expand_legislation_tasks

    return expand_legislation_tasks(catalogue, provision)


def _build_plan(args, catalogue, chat_services, agent_tasks) -> dict:
    leg_chat, leg_agent = ([], [])
    if args.include_legislation:
        leg_chat, leg_agent = _legislation_items(catalogue, args.legislation_provision)

    all_chat = list(chat_services) + list(leg_chat)
    all_agent = list(agent_tasks) + list(leg_agent)

    chat_calls = sum(args.n_trials * (len(s.turns) + 1) for s in all_chat)  # turns + 1 judge
    agent_calls = len(all_agent) * args.n_trials * (args.max_steps + 1)      # upper bound: max_steps + 1 judge

    return {
        "catalogue_path": str(args.catalogue or bundled_catalogue_path()),
        "catalogue_sha256": _sha256(args.catalogue or bundled_catalogue_path()),
        "model": args.model,
        "judge_model": args.judge_model or args.model,
        "chat_ids": [s.id for s in all_chat],
        "agent_ids": [t.id for t in all_agent],
        "include_legislation": args.include_legislation,
        "n_trials": args.n_trials,
        "chat_calls": chat_calls,
        "agent_calls": agent_calls,
    }


def _print_plan(plan: dict, *, dry_run: bool) -> None:
    print("Run plan")
    print(f"  catalogue      : {plan['catalogue_path']}")
    print(f"  catalogue sha  : {plan['catalogue_sha256'][:16]}…")
    print(f"  model / judge  : {plan['model']} / {plan['judge_model']}")
    print(f"  chat services  : {len(plan['chat_ids'])}  ({', '.join(plan['chat_ids']) or '—'})")
    print(f"  agent tasks    : {len(plan['agent_ids'])}  ({', '.join(plan['agent_ids']) or '—'})")
    print(f"  legislation    : {'included' if plan['include_legislation'] else 'not included'}")
    print(f"  trials / item  : {plan['n_trials']}")
    print(
        f"  API calls (UB) : ~{plan['chat_calls'] + plan['agent_calls']} "
        f"(chat ~{plan['chat_calls']}, agent ~{plan['agent_calls']})"
    )
    if dry_run:
        print("\ndry run — no API calls made, nothing written.")


def _run_metadata(args, catalogue_path: Path, judge_model: str, contact) -> dict:
    return {
        "au_radar_version": au_radar.__version__,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "judge_model": judge_model,
        "catalogue_path": str(catalogue_path),
        "catalogue_sha256": _sha256(catalogue_path),
        "n_trials": args.n_trials,
        "max_steps": args.max_steps,
        "max_retries": args.max_retries,
        "include_legislation": args.include_legislation,
        "legislation_provision": args.legislation_provision if args.include_legislation else None,
        "services_selector": args.services,
        "agent_tasks_selector": args.agent_tasks,
        "contact": contact,
    }


def _write_json(path: Path, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    catalogue_path = args.catalogue or bundled_catalogue_path()
    if not catalogue_path.exists():
        parser.error(f"catalogue not found: {catalogue_path}")
    try:
        catalogue = load_catalogue(str(catalogue_path))
    except Exception as exc:  # noqa: BLE001 - surface any load failure as a clean CLI error
        parser.error(f"could not load catalogue {catalogue_path}: {exc}")

    if args.list_catalogue:
        _print_catalogue(catalogue)
        return 0

    try:
        chat_services = _select(catalogue.chat_services, args.services)
        agent_tasks = _select(catalogue.agent_tasks, args.agent_tasks)
    except ValueError as exc:
        parser.error(str(exc))

    runs_agent = bool(agent_tasks) or (args.include_legislation and bool(catalogue.legislation_comparators))
    contact = args.contact or os.environ.get(CONTACT_ENV)
    if runs_agent and not contact:
        parser.error(
            f"agent runs need an identifying contact for the crawler User-Agent (spec §7). "
            f"Pass --contact or set ${CONTACT_ENV}. Use --agent-tasks none (and omit "
            f"--include-legislation) for a chat-only run."
        )

    judge_model = args.judge_model or args.model
    plan = _build_plan(args, catalogue, chat_services, agent_tasks)

    if args.dry_run:
        _print_plan(plan, dry_run=True)
        return 0

    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        parser.error(f"${API_KEY_ENV} not set")

    _print_plan(plan, dry_run=False)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_dir / "run-metadata.json", _run_metadata(args, catalogue_path, judge_model, contact))

    _run(args, catalogue, chat_services, agent_tasks, api_key, judge_model, contact)
    print("\n" + HOVER_CAVEAT, file=sys.stderr)
    return 0


# --------------------------------------------------------------------------- #
# Live run path. Everything below imports anthropic / playwright / matplotlib,
# so it is kept out of module import time (--list, --dry-run, and the test
# suite never touch it).
# --------------------------------------------------------------------------- #

def _with_retries(label, max_retries, fn):
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - retry wrapper, re-raised below
            last_exc = exc
            print(f"    [retry {attempt}/{max_retries}] {label}: {exc}")
    raise last_exc


def _build_user_agent(browser, contact: str) -> str:
    context = browser.new_context()
    page = context.new_page()
    default_ua = page.evaluate("navigator.userAgent")
    context.close()
    note = USER_AGENT_NOTE.format(version=au_radar.__version__, contact=contact)
    return f"{default_ua} {note}"


def _run_chat_service(client, service, args, judge_model, results):
    from au_radar.aggregate_chat import aggregate_chat_scores
    from au_radar.chat_harness import run_chat_conversation
    from au_radar.judge import judge_chat_transcript

    print(f"[chat] {service.id}")
    scores = []
    for trial in range(args.n_trials):
        transcript = _with_retries(
            f"chat {service.id} trial {trial}", args.max_retries,
            lambda: run_chat_conversation(client, service, country="Australia", model=args.model, trial=trial),
        )
        score = _with_retries(
            f"judge {service.id} trial {trial}", args.max_retries,
            lambda: judge_chat_transcript(client, transcript, model=judge_model),
        )
        print(f"    trial {trial}: total={score.total}")
        scores.append(score)
    results.append(aggregate_chat_scores(service.id, scores))


def _run_agent_task(browser, client, task, user_agent, args, judge_model, results):
    from au_radar.aggregate_agent import aggregate_agent_scores
    from au_radar.agent_harness import run_agent_task
    from au_radar.judge import judge_agent_trace

    print(f"[agent] {task.id}")
    scores = []
    for trial in range(args.n_trials):
        def _one_attempt():
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            try:
                return run_agent_task(page, client, task, model=args.model, max_steps=args.max_steps)
            finally:
                context.close()

        trace = _with_retries(f"agent {task.id} trial {trial}", args.max_retries, _one_attempt)
        print(f"    trial {trial}: outcome={trace.outcome} steps={len(trace.steps)}")
        score = _with_retries(
            f"judge {task.id} trial {trial}", args.max_retries,
            lambda: judge_agent_trace(client, trace, model=judge_model),
        )
        print(f"    trial {trial}: total={score.total}")
        scores.append(score)
    results.append(aggregate_agent_scores(task.id, scores))


def _run(args, catalogue, chat_services, agent_tasks, api_key, judge_model, contact):
    import anthropic
    from playwright.sync_api import sync_playwright

    from au_radar.aggregate_agent import write_agent_results
    from au_radar.aggregate_chat import write_chat_results
    from au_radar.charts import plot_guidance_to_reach_gap, plot_service_scores
    from au_radar.legislation import expand_legislation_tasks
    from au_radar.report import write_findings_summary
    from au_radar.scorecard import build_legislation_scorecard, build_scorecard

    client = anthropic.Anthropic(api_key=api_key)
    out_dir = str(args.out_dir)

    leg_chat, leg_agent = ([], [])
    if args.include_legislation:
        leg_chat, leg_agent = expand_legislation_tasks(catalogue, args.legislation_provision)

    chat_results = []
    for service in list(chat_services) + list(leg_chat):
        _run_chat_service(client, service, args, judge_model, chat_results)
    write_chat_results(chat_results, os.path.join(out_dir, "chat-legibility.json"))
    print(f"Wrote {len(chat_results)} chat result(s) to {out_dir}/chat-legibility.json")

    agent_results = []
    all_agent_tasks = list(agent_tasks) + list(leg_agent)
    if all_agent_tasks:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=args.headless)
            try:
                user_agent = _build_user_agent(browser, contact)
                print(f"User-Agent: {user_agent}")
                for task in all_agent_tasks:
                    _run_agent_task(browser, client, task, user_agent, args, judge_model, agent_results)
            finally:
                browser.close()
    write_agent_results(agent_results, os.path.join(out_dir, "agent-operability.json"))
    print(f"Wrote {len(agent_results)} agent result(s) to {out_dir}/agent-operability.json")

    leg_service_ids = {s.id for s in leg_chat}
    leg_task_ids = {t.id for t in leg_agent}
    non_leg_chat = [r for r in chat_results if r.service_id not in leg_service_ids]
    non_leg_agent = [r for r in agent_results if r.task_id not in leg_task_ids]
    if not non_leg_chat or not non_leg_agent:
        print("Partial run (missing chat or non-legislation agent results) — skipping scorecard/charts/report.")
        return

    scorecard = build_scorecard(chat_results, agent_results, leg_task_ids, leg_service_ids)
    print(f"Overall AU score: {scorecard.overall_score} (chat {scorecard.chat_mean}, agent {scorecard.agent_mean})")

    legislation_scorecard = None
    if leg_chat:
        legislation_scorecard = build_legislation_scorecard(
            [r for r in chat_results if r.service_id in leg_service_ids],
            [r for r in agent_results if r.task_id in leg_task_ids],
        )

    plot_service_scores(non_leg_chat, os.path.join(out_dir, "service-scores.png"))
    task_to_chat_id = {t.id: t.chat_service_id for t in agent_tasks}
    plot_guidance_to_reach_gap(
        non_leg_chat, non_leg_agent, os.path.join(out_dir, "guidance-to-reach-gap.png"), task_to_chat_id,
    )

    if legislation_scorecard is not None:
        write_findings_summary(
            scorecard, legislation_scorecard, chat_results, agent_results,
            os.path.join(out_dir, "findings-summary.md"),
        )
        print(f"Wrote findings summary to {out_dir}/findings-summary.md")
    else:
        print("Skipped findings-summary.md (needs --include-legislation for the full legislation scorecard).")


if __name__ == "__main__":
    sys.exit(main())
