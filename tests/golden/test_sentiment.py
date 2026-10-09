"""
Golden tests for the sentiment heuristic — hand-picked example messages.
"""

from salli.domain.agents.sentiment import classify_sentiment, tone_instruction

# ── classify_sentiment ───────────────────────────────────────────────────────


def test_frustrated_keyword():
    assert classify_sentiment("This is so frustrating, nothing is working") == "frustrated"


def test_frustrated_fed_up():
    assert classify_sentiment("I'm fed up with this app, it's ridiculous") == "frustrated"


def test_frustrated_heavy_exclamation():
    assert classify_sentiment("Why is this broken again!!!") == "frustrated"


def test_anxious_keyword():
    assert classify_sentiment("I'm really worried about my savings right now") == "anxious"


def test_anxious_help_me():
    assert classify_sentiment("Help me, I don't know what to do about this debt") == "anxious"


def test_positive_thanks():
    assert classify_sentiment("Thank you so much, this is exactly what I needed") == "positive"


def test_positive_excited():
    assert classify_sentiment("Awesome, I'm so excited about my FIRE progress!") == "positive"


def test_neutral_plain_question():
    assert classify_sentiment("What's my current account balance?") == "neutral"


def test_neutral_empty_string():
    assert classify_sentiment("") == "neutral"


def test_frustrated_takes_priority_over_positive():
    """Thanks for the help, but still frustrated — frustration wins."""
    text = "Thanks, but I'm so frustrated this keeps happening every month"
    assert classify_sentiment(text) == "frustrated"


def test_case_insensitive():
    assert classify_sentiment("I AM SO FRUSTRATED RIGHT NOW") == "frustrated"


# ── tone_instruction ─────────────────────────────────────────────────────────


def test_tone_instruction_neutral_is_empty():
    assert tone_instruction("neutral") == ""


def test_tone_instruction_frustrated_mentions_acknowledge():
    assert "acknowledge" in tone_instruction("frustrated").lower()


def test_tone_instruction_anxious_mentions_reassuring():
    assert "reassur" in tone_instruction("anxious").lower()


def test_tone_instruction_positive_mentions_momentum():
    assert "momentum" in tone_instruction("positive").lower()


def test_tone_instruction_all_non_neutral_are_nonempty():
    for sentiment in ("frustrated", "anxious", "positive"):
        assert tone_instruction(sentiment) != ""
