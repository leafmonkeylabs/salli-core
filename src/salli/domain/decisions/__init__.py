"""
The decision lab's decisions: principles, the decision journal and reviews
(docs/decisions.md). Pure: no I/O, no model, Decimal throughout.

- `figures`: the fixed, documented set of figures a principle's check reads,
  computed from a scenario's outlook (or the baseline's own).
- `principles`: `salli.principle/1`, the user's own rules of thumb, as checks
  in the tax rules' safe expression language; checking says which an option
  keeps, breaks or can't tell, never a ranking.
- `projection`: what an option projected, month by month, in each month's
  own money: what a review compares against.
- `journal`: `salli.decision/1` entries, their notes and reviews, content
  hashes over their canonical JSON, and the journal as JSON or Markdown.
- `review`: what the chosen option projected at a month's end, against the
  baseline as of that day.
"""
