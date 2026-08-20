"""Manual smoke test only. Never run via pytest. Makes real Anthropic API
calls and launches a real browser against real public pages. Run by hand:

    python scripts/run_live_smoke_test.py

before committing to a full data-collection run, to sanity-check that the
harnesses work end-to-end with real responses on a single service/task.
"""
import os

import anthropic
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from au_radar.catalogue import load_catalogue
from au_radar.chat_harness import run_chat_conversation
from au_radar.judge import judge_chat_transcript

MODEL = "claude-sonnet-5"


def main():
    load_dotenv()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    catalogue = load_catalogue("src/au_radar/data/catalogue.yaml")
    service = catalogue.chat_services[0]

    transcript = run_chat_conversation(client, service, country="Australia", model=MODEL)
    print(f"Transcript for {service.id}:")
    for turn in transcript.turns:
        print(f"  {turn['role']}: {turn['content'][:120]}")

    score = judge_chat_transcript(client, transcript, model=MODEL)
    print(f"Score: verifiability={score.verifiability} specificity={score.specificity} "
          f"depth={score.depth} transparency={score.transparency} total={score.total}")


if __name__ == "__main__":
    main()
