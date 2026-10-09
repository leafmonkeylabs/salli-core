"""Which model runs a task, from the models an account can use. No model name
is fixed in Salli: these feed it catalogues and check what it picks."""

from __future__ import annotations

import pytest

from salli.domain.llm import LLMNotConfigured
from salli.domain.model_choice import CatalogModel, api_catalogue, choose, is_fast, plan_catalogue

PLAN = {
    "models": [
        {"slug": "gpt-6.1-sol", "display_name": "GPT-6.1 Sol", "visibility": "list"},
        {"slug": "gpt-6.1-hidden", "display_name": "Hidden", "visibility": "hide"},
        {"slug": "gpt-6.1-mini", "display_name": "GPT-6.1 mini", "visibility": "list"},
        {"slug": "gpt-6", "display_name": "GPT-6", "visibility": "list"},
    ]
}


def test_a_plans_catalogue_keeps_the_listed_models_in_the_servers_order():
    assert [m.id for m in plan_catalogue(PLAN)] == ["gpt-6.1-sol", "gpt-6.1-mini", "gpt-6"]
    assert plan_catalogue(PLAN)[0].name == "GPT-6.1 Sol"


def test_best_is_the_first_full_model_and_fast_the_first_small_one():
    assert choose(plan_catalogue(PLAN)) == {"best": "gpt-6.1-sol", "fast": "gpt-6.1-mini"}


def test_with_no_small_model_fast_is_the_best_one():
    models = [CatalogModel("gpt-7", "GPT-7"), CatalogModel("gpt-6", "GPT-6")]
    assert choose(models) == {"best": "gpt-7", "fast": "gpt-7"}


def test_a_small_model_listed_first_is_still_not_best():
    models = [CatalogModel("gpt-7-nano", "nano"), CatalogModel("gpt-7", "GPT-7")]
    assert choose(models) == {"best": "gpt-7", "fast": "gpt-7-nano"}


def test_the_users_own_choice_wins():
    picks = choose(plan_catalogue(PLAN), {"best": "gpt-6", "fast": None})
    assert picks == {"best": "gpt-6", "fast": "gpt-6.1-mini"}


def test_a_coding_model_is_not_picked_while_a_general_one_exists():
    models = [CatalogModel("gpt-7-codex", "Codex"), CatalogModel("gpt-7", "GPT-7")]
    assert choose(models)["best"] == "gpt-7"
    assert choose([CatalogModel("gpt-7-codex", "Codex")])["best"] == "gpt-7-codex"


@pytest.mark.parametrize(
    ("model", "fast"),
    [
        ("gpt-5-mini", True),
        ("o4-mini", True),
        ("gpt-4.1-nano", True),
        ("gpt-6.1-sol", False),
        ("gpt-6", False),
        ("gemini-flash", True),
        ("minimal-reasoner", False),
    ],
)
def test_what_counts_as_a_small_fast_variant(model, fast):
    assert is_fast(CatalogModel(model, model)) is fast


def test_an_account_with_no_models_is_told_so():
    with pytest.raises(LLMNotConfigured):
        choose([])


def test_an_api_keys_catalogue_is_the_chat_models_newest_first():
    body = {
        "object": "list",
        "data": [
            {"id": "gpt-5", "created": 300},
            {"id": "gpt-5-2025-08-07", "created": 290},  # a snapshot of an alias it has
            {"id": "gpt-5-mini", "created": 310},
            {"id": "gpt-6", "created": 500},
            {"id": "gpt-6-pro", "created": 510},  # premium, never picked by itself
            {"id": "text-embedding-3-large", "created": 600},
            {"id": "gpt-4o-mini-tts", "created": 700},
            {"id": "gpt-image-1", "created": 800},
            {"id": "whisper-1", "created": 900},
            {"id": "omni-moderation-latest", "created": 950},
            {"id": "o4-mini", "created": 400},
            {"id": "gpt-5-chat-latest", "created": 520},
            {"id": "dall-e-3", "created": 100},
        ],
    }

    models = api_catalogue(body)

    assert [m.id for m in models] == ["gpt-6", "o4-mini", "gpt-5-mini", "gpt-5"]
    assert choose(models) == {"best": "gpt-6", "fast": "o4-mini"}
