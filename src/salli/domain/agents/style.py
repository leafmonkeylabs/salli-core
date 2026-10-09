"""
How Salli writes. Pure domain, no I/O.

One shared block appended to every prompt whose output a user reads, for the
same reason `ai_models.py` exists: the alternative is the same paragraph pasted
into seven prompts, and seven copies drift. A rule that holds in Buddy Mode but
not in the daily briefing is not a rule.

Note the punctuation of this module and of the prompts that import it. A model
takes its register from the text it is given, so an instruction against em
dashes inside a prompt full of them is an instruction the examples contradict.
The prompts were rewritten to stop using them at the same time this was added.
"""

from __future__ import annotations

#: Appended to every user-facing agent prompt. Kept short on purpose: a style
#: section longer than the instructions it qualifies gets ignored.
WRITING_STYLE = """\
How to write:
- Never use an em dash. Use a full stop, a comma, or a colon instead.
- Short sentences. Length is not thoroughness, so say the thing and stop.
- Plain words over formal ones. If a shorter word works, use it.
- An emoji is fine where it adds warmth. Sparingly, at most one, and never in
  a figure, a warning, or a tax explanation: those need to read as exact."""
