"""Live data-collection run. Makes real Anthropic API calls and, for agent
tasks, drives a real Chromium browser against real public government sites.
Never run via pytest. This is the "separate, manual, human-approved live
data-collection run" the implementation plan explicitly scoped out of the
automated build -- run it deliberately, watch the output.

Usage (pilot -- one agent task, one trial, no chat calls, no legislation):

    python scripts/run_live_collection.py \\
        --services none --agent-tasks passport_agent --n-trials 1

Usage (full run -- everything in the catalogue, legislation included):

    python scripts/run_live_collection.py --include-legislation

Spec guardrails implemented here (not in the harness itself, by design --
see FUTURE.md): retries capped at --max-retries (spec §7's "<=3 retries per
task"), and an honest identifying User-Agent (spec §7's "no impersonation to
evade detection").
"""
import argparse
import os

import anthropic
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

import au_radar
from au_radar.aggregate_agent import aggregate_agent_scores, write_agent_results
from au_radar.aggregate_chat import aggregate_chat_scores, write_chat_results
from au_radar.agent_harness import run_agent_task
from au_radar.catalogue import load_catalogue
from au_radar.charts import plot_guidance_to_reach_gap, plot_service_scores
from au_radar.chat_harness import run_chat_conversation
from au_radar.judge import judge_agent_trace, judge_chat_transcript
from au_radar.legislation import expand_legislation_tasks
from au_radar.report import write_findings_summary
from au_radar.scorecard import build_legislation_scorecard, build_scorecard

MODEL = "claude-sonnet-5"
JUDGE_MODEL = "claude-sonnet-5"
CATALOGUE_PATH = "src/au_radar/data/catalogue.yaml"
CONTACT_NOTE = "au-radar-research/{version} (+contact: ching.chew@gmail.com; non-authenticating research benchmark, see spec §7)"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--services", default="all", help="comma-separated chat service ids, 'all', or 'none'")
    parser.add_argument("--agent-tasks", default="all", help="comma-separated agent task ids, 'all', or 'none'")
    parser.add_argument("--include-legislation", action="store_true", help="also run the lex-au/Federal Register/AustLII legislation trio")
    parser.add_argument("--legislation-provision", default="Fair Work Act 2009 s 65")
    parser.add_argument("--n-trials", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--max-retries", type=int, default=3, help="spec §7: <=3 retries per task")
    parser.add_argument("--out-dir", default="results")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


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


def _build_user_agent(browser) -> str:
    context = browser.new_context()
    page = context.new_page()
    default_ua = page.evaluate("navigator.userAgent")
    context.close()
    return f"{default_ua} {CONTACT_NOTE.format(version=au_radar.__version__)}"


def _with_retries(label, max_retries, fn):
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            print(f"    [retry {attempt}/{max_retries}] {label}: {exc}")
    raise last_exc


def _run_chat_service(client, service, args, results):
    print(f"[chat] {service.id}")
    scores = []
    for trial in range(args.n_trials):
        transcript = _with_retries(
            f"chat {service.id} trial {trial}", args.max_retries,
            lambda: run_chat_conversation(client, service, country="Australia", model=MODEL, trial=trial),
        )
        score = _with_retries(
            f"judge {service.id} trial {trial}", args.max_retries,
            lambda: judge_chat_transcript(client, transcript, model=JUDGE_MODEL),
        )
        print(f"    trial {trial}: total={score.total}")
        scores.append(score)
    results.append(aggregate_chat_scores(service.id, scores))


def _run_agent_task(browser, client, task, user_agent, args, results):
    print(f"[agent] {task.id}")
    scores = []
    for trial in range(args.n_trials):
        def _one_attempt():
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            try:
                return run_agent_task(page, client, task, model=MODEL, max_steps=args.max_steps)
            finally:
                context.close()

        trace = _with_retries(f"agent {task.id} trial {trial}", args.max_retries, _one_attempt)
        print(f"    trial {trial}: outcome={trace.outcome} steps={len(trace.steps)}")
        score = _with_retries(
            f"judge {task.id} trial {trial}", args.max_retries,
            lambda: judge_agent_trace(client, trace, model=JUDGE_MODEL),
        )
        print(f"    trial {trial}: total={score.total}")
        scores.append(score)
    results.append(aggregate_agent_scores(task.id, scores))


def main():
    load_dotenv()
    args = parse_args()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    catalogue = load_catalogue(CATALOGUE_PATH)

    chat_services = _select(catalogue.chat_services, args.services)
    agent_tasks = _select(catalogue.agent_tasks, args.agent_tasks)

    legislation_chat_services, legislation_agent_tasks = [], []
    if args.include_legislation:
        legislation_chat_services, legislation_agent_tasks = expand_legislation_tasks(
            catalogue, args.legislation_provision,
        )

    os.makedirs(args.out_dir, exist_ok=True)

    chat_results = []
    for service in chat_services + legislation_chat_services:
        _run_chat_service(client, service, args, chat_results)
    write_chat_results(chat_results, os.path.join(args.out_dir, "chat-legibility.json"))
    print(f"Wrote {len(chat_results)} chat result(s) to {args.out_dir}/chat-legibility.json")

    agent_results = []
    all_agent_tasks = agent_tasks + legislation_agent_tasks
    if all_agent_tasks:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=args.headless)
            try:
                user_agent = _build_user_agent(browser)
                print(f"User-Agent: {user_agent}")
                for task in all_agent_tasks:
                    _run_agent_task(browser, client, task, user_agent, args, agent_results)
            finally:
                browser.close()
    write_agent_results(agent_results, os.path.join(args.out_dir, "agent-operability.json"))
    print(f"Wrote {len(agent_results)} agent result(s) to {args.out_dir}/agent-operability.json")

    non_legislation_chat = [r for r in chat_results if r.service_id not in {s.id for s in legislation_chat_services}]
    non_legislation_agent = [r for r in agent_results if r.task_id not in {t.id for t in legislation_agent_tasks}]
    if not non_legislation_chat or not non_legislation_agent:
        print("Partial run (missing chat or non-legislation agent results) -- skipping scorecard/charts/report.")
        return

    legislation_task_ids = {t.id for t in legislation_agent_tasks}
    legislation_service_ids = {s.id for s in legislation_chat_services}
    scorecard = build_scorecard(chat_results, agent_results, legislation_task_ids, legislation_service_ids)
    print(f"Overall AU score: {scorecard.overall_score} (chat {scorecard.chat_mean}, agent {scorecard.agent_mean})")

    legislation_scorecard = None
    if legislation_chat_services:
        legislation_chat_results = [r for r in chat_results if r.service_id in legislation_service_ids]
        legislation_agent_results = [r for r in agent_results if r.task_id in legislation_task_ids]
        legislation_scorecard = build_legislation_scorecard(legislation_chat_results, legislation_agent_results)

    plot_service_scores(non_legislation_chat, os.path.join(args.out_dir, "service-scores.png"))
    task_to_chat_id = {t.id: t.chat_service_id for t in agent_tasks}
    plot_guidance_to_reach_gap(
        non_legislation_chat, non_legislation_agent,
        os.path.join(args.out_dir, "guidance-to-reach-gap.png"), task_to_chat_id,
    )

    if legislation_scorecard is not None:
        write_findings_summary(
            scorecard, legislation_scorecard, chat_results, agent_results,
            os.path.join(args.out_dir, "findings-summary.md"),
        )
        print(f"Wrote findings summary to {args.out_dir}/findings-summary.md")
    else:
        print("Skipped findings-summary.md (needs --include-legislation for the full legislation scorecard).")


if __name__ == "__main__":
    main()
