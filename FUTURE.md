# Future work / known gaps

Not blocking the current plan (docs/superpowers/plans/2026-08-16-au-radar-legibility.md
in the executive-assistant repo). Address before the separate, manual,
human-approved live data-collection run.

## Fixed (2026-08-21)

Both gaps below were closed before the first live run, verified against the
real Anthropic API (not just fixture-based mocks) and against new fixture
tests (`iframe_login.html`, `async_login.html`, `test_agent_extracts_tool_use_past_a_leading_thinking_block`):

- **`content[0]` assumed the first content block.** True for chat, judge, and
  agent responses — Claude Sonnet 5 reliably emits a leading `ThinkingBlock`
  before the real content. Fixed via `au_radar/anthropic_utils.py`'s
  `extract_text()` / `extract_tool_use()`, which scan for the block by type
  instead of assuming position.
- **Hard-stop guardrail only checked the main frame, synchronously.**
  `_page_has_login_field()` now walks every frame (catches iframe-embedded
  SSO widgets), and `run_agent_task()` waits `LOGIN_FIELD_SETTLE_MS` (500ms)
  after each action before the next guardrail check (catches async-injected
  login fields). Frame checks that raise (a frame detaching mid-check) are
  treated as inconclusive for that frame, never as license to proceed.

## Fixed after the pilot runs, before the full run (2026-08-21)

- **Click/type_text targets were paraphrased, not quoted.** The model
  described elements in its own words instead of copying real page text,
  so `page.get_by_text(...)` never matched. Fixed via explicit verbatim-quote
  instructions in the `click`/`type_text` tool descriptions and system
  prompt.
- **A failed action crashed the whole trial.** One bad click (e.g. a
  hover-only nav item, an invisible element) raised an unhandled exception
  and discarded every prior real API call in that trial. Fixed: action
  failures are now caught and fed back to the model as an observation
  ("Action failed: ..." plus current page content), so it can adapt instead
  of the trial dying.

## Fixed after the full live run (2026-08-21)

Both found live, mid-collection, on the actual full run (18 chat services +
4 general + 3 legislation agent tasks, 2 trials each) — auto-recovered by
the script's retry wrapper both times, so no result from that run is
invalid, but both wasted real retries and would eventually exhaust the
retry budget on a large enough run:

- **Orphaned `tool_use` blocks.** When Claude emitted more than one
  `tool_use` block in a single turn, the harness only executed and replied
  to the first, leaving the second's id without a `tool_result` -- the API
  rejects the *next* call outright when that happens
  (`invalid_request_error: tool_use ids were found without tool_result
  blocks`). Fixed: every extra `tool_use` id in a turn now gets an explicit
  "not executed" `tool_result`, not just the one that was actually acted on.
- **`max_tokens=1024` was too tight for the agent loop's own action-selection
  calls**, same root cause as the judge-call fix from the pilot stage --
  thinking tokens can exhaust the budget before a `tool_use` block is
  emitted at all. Raised to 2048, matching `judge.py`.

## Auth-boundary detection hardening (2026-08-28, v0.2.0)

`_page_has_login_field()` and the post-action settle were widened:

- The single fixed 500ms wait became `_settle_for_login_field()`: the 500ms
  baseline still runs (page content must render before it's read), then a
  250ms poll continues up to `LOGIN_FIELD_SETTLE_MAX_MS` (2000ms), returning
  the instant a field appears. Catches SSO widgets injected after the old
  window. Cost: a step that never surfaces a login field now pays the full
  2000ms cap.
- Detection beyond `input[type="password"]`: also
  `input[autocomplete="current-password"]`, `input[autocomplete="one-time-code"]`
  (OTP / MFA screens).
- `_url_looks_like_auth()` matches the *parsed* page/frame URL (not raw
  substrings, which false-positived on IdP-hosted info pages and dev docs
  quoting an OAuth URL): known IdP hosts (`login.microsoftonline.com`,
  `*.okta.com`, `*.auth0.com`, `myid.gov.au`, `login.my.gov.au`), auth path
  markers (`/oauth2|oauth|connect/authorize`, `/saml2/idp`, `/adfs/ls`,
  `/protocol/openid-connect/auth`), `SAMLRequest=` in the query, or
  `response_type=code|token` when the path is an `/authorize` endpoint.
- The post-action settle/poll now also runs when the action *raised* (a
  failed click can still have started a redirect to a slow SSO page).

## Still open before trusting this at larger scale

- The poll + URL matcher is stronger than a fixed wait, still not a proof.
  A novel IdP matching no host/path marker and rendering its field slower
  than 2000ms could still slip through; nothing here replaces watching runs.
- `_AUTH_HOSTS` / `_AUTH_PATH_MARKERS` are hand-maintained lists of known
  providers, not a general federated-auth detector. Not covered:
  passkey-only (`autocomplete="webauthn"`) screens with no password field,
  closed shadow-DOM login widgets, and IdPs outside the lists (Keycloak on a
  custom path, Ping, Shibboleth, POST-binding SAML).
- No `hover` tool exists, so menu items that only render on hover (not
  click) are unreachable by design -- this showed up as a real, legitimate
  low `passport_agent` score (1.7) rather than a harness bug, but it means
  that score reflects a harness capability gap as much as a site problem.
  Worth naming explicitly wherever `passport_agent`'s score is reported.
