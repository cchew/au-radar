import pytest

from au_radar.anthropic_utils import extract_text


class FakeThinkingBlock:
    type = "thinking"
    thinking = "reasoning about the answer..."


class FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, content):
        self.content = content


def test_extract_text_finds_text_block_after_leading_thinking_block():
    response = FakeResponse([FakeThinkingBlock(), FakeTextBlock("the real answer")])

    assert extract_text(response) == "the real answer"


def test_extract_text_raises_when_no_text_block_present():
    response = FakeResponse([FakeThinkingBlock()])

    with pytest.raises(ValueError):
        extract_text(response)
