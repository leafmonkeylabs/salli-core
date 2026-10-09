"""
What it means for a supervisor to have finished its turn. Pure domain, no I/O.

Shared for the same reason `style.py` is shared: the alternative is the same
paragraph pasted into both supervisor prompts, and two copies drift. A rule that
holds in Buddy Mode but not for Scrooge is not a rule.

This exists because of a real, reproducible failure. Asked "Why is my tax bill
11.7L?", Salli replied "I'd like to pull up your actual tax position so I can
show you exactly where that 11.7L is coming from. Let me check your ledger and
tax computations.", ran its tools, and ended the turn. The answer only arrived
when the user typed "Go on". Same shape for "What did I spend the most on this
year?".

The cause was an absence rather than a bug. Both prompts say "Delegate
immediately"; neither says the supervisor must then answer. To a model, an
announcement is a perfectly good turn, so it announced and stopped. The
architecture makes this easy to fall into: a supervisor's natural output when it
decides to hand off is a sentence about handing off.

This is the first thing a new user sees, and it is the exact claim the App Store
listing makes, so it is worth an explicit contract rather than hoping a larger
model would not do it.
"""

from __future__ import annotations

#: Appended to every supervisor prompt, after the persona and the guidelines, so
#: it is the last instruction the model reads before the conversation.
FINISH_THE_TURN = """\
Finishing your turn:
- Announcing is not answering. Never end a turn with "let me check", "let me
  pull that up", or "I'll take a look". If you say you are going to look
  something up, look it up and give the answer in the same turn.
- After a specialist or a tool returns, the next thing you produce is the
  answer. Do not stop to narrate what you just did, and do not ask permission
  to continue with something the user already asked for.
- If you need nothing from the user, do not hand the turn back to them. Only
  stop early to ask a question you genuinely cannot proceed without, or to
  request approval for a write action.
- A preamble before a tool call is fine, and one short sentence is plenty. It
  is not a substitute for the answer that has to follow it."""
