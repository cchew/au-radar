# Future work / known gaps

Not blocking the current plan (docs/superpowers/plans/2026-08-16-au-radar-legibility.md
in the executive-assistant repo). Everything here is deferred because this plan only
builds and tests the harness against a local fixture server — no automated task in
this plan ever touches a real government site. Address before the separate, manual,
human-approved live data-collection run.

## Hard-stop guardrail coverage (from Task 7 review, 2026-08-19)

`_page_has_login_field()` in `src/au_radar/agent_harness.py` only checks
`input[type="password"]` in the page's main frame, synchronously, with no
wait/settle logic. Two real gaps before this harness ever drives a real browser
against a real government portal:

1. **Cross-origin/iframe SSO widgets.** AU government login flows commonly use
   an identity-provider redirect or embedded widget (myGovID-style) that may
   render its password field inside an `<iframe>` the current check won't see.
2. **Async-rendered login fields.** A login field injected by client-side JS
   after `page.goto()`/`.click()` returns, but before the harness's next check,
   falls in a narrow but real timing gap.

Neither is a bug in what Task 7 built — it matches the plan/spec exactly and
passes its fixture tests. But the constraint's own bar ("terminate the instant
a password field is detected") has only been proven for the same-frame,
synchronously-rendered case. Harden the detector (frame-walking, a short
explicit settle/wait, and/or a periodic re-check independent of action
completion) before pointing this at anything but the local fixture server.

## `content[0]` assumes a leading tool_use block

`run_agent_task()` reads `response.content[0]` and assumes it's always a
`tool_use` block. A real Claude response can legitimately emit a text block
before the tool_use block (e.g. the model reasoning aloud). That will raise
`AttributeError` rather than execute anything unsafe — it fails loud, not
silently — but it will break the harness against the real Anthropic API even
though the hand-rolled fake test client never triggers it. Fix: scan
`response.content` for the first `tool_use` block instead of indexing `[0]`.
