"""
Supervisors must be told to finish their turn.

Both supervisor prompts said "Delegate immediately" and neither said what to do
afterwards, so the model treated the announcement as the whole turn: it said
"Let me check your ledger and tax computations", ran its tools, and stopped. The
answer only arrived if the user typed "Go on".

The rule itself lives in one place, and these tests exist to keep it that way
and to keep it attached to both supervisors. They deliberately assert on the
shared constant rather than on wording, so rephrasing the guidance does not
break them, but deleting it or detaching it from a prompt does.
"""

from __future__ import annotations

from salli.application.services.agent_service import GRAPH_RECURSION_LIMIT
from salli.domain.agents.buddy_agent import BUDDY_SYSTEM_PROMPT
from salli.domain.agents.manager_agent import MANAGER_SYSTEM_PROMPT
from salli.domain.agents.turn_contract import FINISH_THE_TURN


def test_both_supervisors_carry_the_turn_contract():
    """A new supervisor that forgets this will stall the same way."""
    assert FINISH_THE_TURN in BUDDY_SYSTEM_PROMPT
    assert FINISH_THE_TURN in MANAGER_SYSTEM_PROMPT


def test_the_contract_forbids_ending_on_an_announcement():
    """The specific failure, not just the presence of some text."""
    assert "Announcing is not answering" in FINISH_THE_TURN
    assert "let me check" in FINISH_THE_TURN.lower()


def test_the_contract_is_the_last_word_in_the_prompt():
    """Ordering is load-bearing.

    It is appended after the persona and the guidelines so it is the last thing
    the model reads before the conversation starts. Guideline 1 tells it to
    delegate immediately; this has to come after that, not before.
    """
    for prompt in (BUDDY_SYSTEM_PROMPT, MANAGER_SYSTEM_PROMPT):
        assert prompt.rstrip().endswith(FINISH_THE_TURN.rstrip())


def test_recursion_limit_clears_a_realistic_supervisor_turn():
    """25 is LangGraph's default and a two-specialist turn can exceed it.

    Hitting the ceiling truncates the turn rather than answering it, which is
    indistinguishable from the model deciding to stop. The limit should be a
    runaway backstop, not something a normal question reaches.
    """
    assert GRAPH_RECURSION_LIMIT > 25
