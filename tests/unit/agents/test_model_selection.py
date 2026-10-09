"""
The model a user is charged for must be the model that runs.

These two facts live in different layers — pricing in `domain/billing/credits`,
execution in the agent graph — and nothing structural stops them drifting. The
first version of this feature had exactly that bug: the multiplier was applied
at the router while `_get_agent` still returned a cached Sonnet graph, so
picking Opus cost 5x and changed nothing about the answer.
"""

from __future__ import annotations

import pathlib
import re

from salli.domain.agents.model_factory import CONVERSATION_MODEL, HAIKU
from salli.domain.ai_models import DEFAULT_MODEL, EXTRACTION_MODEL, MODELS


class TestOneCatalogue:
    def test_model_factory_reads_from_the_catalogue(self):
        """There were three hardcoded model tables before this — the factory's
        constants, a tier dict in the Anthropic adapter, and a bare literal in
        the statement classifier. They had already drifted."""
        assert CONVERSATION_MODEL == DEFAULT_MODEL
        assert HAIKU == EXTRACTION_MODEL

    def test_the_adapter_tier_table_reads_from_the_catalogue(self):
        from salli.adapters.llm.anthropic_adapter import _MODEL_TIERS

        assert _MODEL_TIERS["fast"] == EXTRACTION_MODEL
        assert _MODEL_TIERS["best"] == DEFAULT_MODEL

    def test_no_model_id_is_spelled_out_anywhere_else(self):
        """A literal model id outside the catalogue is how the three tables got
        out of sync in the first place. Guarding it the same way
        test_model_key_threading guards model construction."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[3] / "src" / "salli"
        allowed = {"ai_models.py"}
        offenders = []
        for path in root.rglob("*.py"):
            if path.name in allowed:
                continue
            text = path.read_text()
            for marker in ("claude-sonnet", "claude-haiku", "claude-opus", "claude-fable"):
                if marker in text:
                    offenders.append(f"{path.relative_to(root)}: {marker}")
        assert not offenders, (
            f"Model ids must come from domain/ai_models.py, not be written out again: {offenders}"
        )


class TestCacheKeyIncludesModel:
    def test_switching_model_does_not_reuse_the_other_models_graph(self):
        """`_get_agent` caches compiled graphs, and langchain binds the model at
        construction — so without `model` in the key, a user who switched would
        be charged the new multiplier and served the old graph."""
        import inspect

        from salli.application.services.agent_service import AgentService

        source = inspect.getsource(AgentService._get_agent)
        # The key tuple must carry the model alongside persona/date/credential.
        assert "cache_key = (persona" in source
        assert "model)" in source, "model must be part of the agent cache key"

    def test_every_selectable_model_is_a_real_catalogue_entry(self):
        for model_id, model in MODELS.items():
            assert model.id == model_id
            assert model.name
            assert model.blurb


class TestPriceMatchesWhatRuns:
    """
    Every metered site that tells the usage meter which model it will run must
    then actually run that model.

    This has been the same bug twice — once in the agent cache key, once in
    /fi/strategy/generate, both pricing an Opus answer and running Sonnet. The
    two facts live in different layers with nothing structural tying them
    together, so this enumerates the metered sites and asserts the pairing at
    each one. A meter that prices by model (the hosted service's does) is only
    as honest as this pairing.
    """

    _CHARGE = re.compile(r"\.charge\(\s*\w+,\s*AIAction\.(\w+)(?:,\s*model_id=(\w+))?")

    def _metered_sites(self):
        root = pathlib.Path(__file__).resolve().parents[3] / "src" / "salli"
        sites = []
        for path in root.rglob("*.py"):
            for line in path.read_text().splitlines():
                m = self._CHARGE.search(line)
                if m:
                    sites.append(
                        (path.relative_to(root).as_posix(), m.group(1), m.group(2) or "None")
                    )
        return sites

    def test_every_metered_site_is_accounted_for(self):
        """A new one must be classified deliberately, not inherit a default."""
        found = {(action, model_arg) for _, action, model_arg in self._metered_sites()}
        expected = {
            # Run on the user's model — and each of these threads that same id
            # into the call that runs.
            ("CHAT_MESSAGE", "model_id"),
            ("FIRE_STRATEGY", "model_id"),
            # Run at the default, so the meter is told nothing more specific.
            #
            # The two extraction actions are pinned to Haiku in
            # ai_models.EXTRACTION_MODEL regardless.
            ("ADVISOR_RUN", "None"),
            ("STATEMENT_IMPORT", "None"),
            ("ENTRY_PARSE", "None"),
        }
        assert found == expected, (
            "A metered site changed. If you added one, decide whether it runs on "
            "the user's model — and if so, make sure the same id reaches the call "
            "that actually runs. Metering one model and running another is the bug "
            "this test exists to catch."
        )

    def test_sites_metered_on_a_chosen_model_resolve_it_from_the_profile(self):
        """`model_id` must come from the user's stored preference, not be
        invented at the call site."""
        root = pathlib.Path(__file__).resolve().parents[3] / "src" / "salli"
        for rel, _, model_arg in self._metered_sites():
            if model_arg != "model_id":
                continue
            text = (root / rel).read_text()
            assert "get_preferred_model(user_id)" in text, (
                f"{rel} meters a chosen model but never resolves the user's model"
            )


class TestTheModelIsPinned:
    """
    Conversations run on one model, chosen for cost, and users cannot change it.

    The picker is gone from both clients and `PUT /ai-models/selection` is
    deleted, but neither of those is what makes the pin hold — a stored
    preference from before the change, or a hand-rolled request, would both go
    through `get_preferred_model`. These guard the one place that decides.
    """

    def test_the_pinned_model_is_the_cheapest_in_the_catalogue(self):
        """ "Cheapest" is the whole reason for the pin, so it is asserted against
        the catalogue rather than against a second copy of the id. Adding a
        cheaper model without re-pointing DEFAULT_MODEL fails here."""
        cheapest = min(MODELS.values(), key=lambda m: m.relative_cost)
        assert cheapest.id == DEFAULT_MODEL
        assert cheapest.relative_cost == 1

    async def test_a_stored_preference_is_ignored(self):
        """The bug this exists to catch: pinning by changing only the default
        would leave everyone who had already picked Opus running on Opus, and
        being charged x5, forever."""
        from unittest.mock import AsyncMock, MagicMock

        from salli.application.services.user_profile_service import UserProfileService

        uow = MagicMock()
        uow.user_profiles.get = AsyncMock(return_value={"preferred_model": "claude-opus-5"})
        uow.__aenter__ = AsyncMock(return_value=uow)
        uow.__aexit__ = AsyncMock(return_value=False)

        svc = UserProfileService(
            lambda: uow,  # type: ignore[arg-type]
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
        assert await svc.get_preferred_model("user-1") == DEFAULT_MODEL

    def test_there_is_no_way_to_set_a_model(self):
        """Both halves of the removal: the service method and the route."""
        from salli.application.services.user_profile_service import UserProfileService
        from salli.interfaces.api import main

        assert not hasattr(UserProfileService, "set_preferred_model")
        assert not hasattr(main, "ai_models")
