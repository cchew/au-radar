def extract_text(response) -> str:
    """Return the first text block's content from an Anthropic response.

    Claude may emit a leading ThinkingBlock (extended thinking) before the
    TextBlock, so the text block is never reliably at content[0]. If the
    response was cut off by max_tokens before any text block was emitted
    (e.g. the thinking block alone exhausted the budget), no text block
    exists at all -- surfaced here with the stop_reason so it reads as a
    token-budget problem, not a mystery empty response.
    """
    for block in response.content:
        if block.type == "text":
            return block.text
    stop_reason = getattr(response, "stop_reason", "unknown")
    raise ValueError(
        f"response contained no text block (stop_reason={stop_reason!r}); "
        "if stop_reason is 'max_tokens', raise max_tokens for this call"
    )


def extract_tool_use(response):
    """Return the first tool_use block from an Anthropic response.

    Claude may emit a leading ThinkingBlock or TextBlock (reasoning aloud)
    before the tool_use block, so it is never reliably at content[0].
    """
    for block in response.content:
        if block.type == "tool_use":
            return block
    stop_reason = getattr(response, "stop_reason", "unknown")
    raise ValueError(
        f"response contained no tool_use block (stop_reason={stop_reason!r}); "
        "if stop_reason is 'max_tokens', raise max_tokens for this call"
    )
