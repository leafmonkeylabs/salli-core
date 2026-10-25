# Risk profile

Salli's risk profile has three parts, kept apart: **tolerance** (how much
loss and uncertainty you say you can stomach), **capacity** (how much loss
your finances can take) and **need** (the return your plan asks for). The
profile is the lower of tolerance and capacity; need is shown beside it,
never folded in. Every part is figures: no part names a product.

```
salli ips risk --json
```

Every read carries `method`: the score buckets and the equity and need
bands below, so the cut-offs a profile came from are shown beside it.

## Tolerance

The items follow the structure of the risk-tolerance scale Grable and
Lytton published (J. E. Grable and R. H. Lytton, "Financial risk tolerance
revisited: the development of a risk assessment instrument", *Financial
Services Review* 8(3), 1999, 163–181), an instrument free to use: several
items, grouped in three factors, each answer scored and the scores summed
without weights. Salli's wording is its own; none of the scale's item text
is used.

| Factor | Items |
|---|---|
| Investment risk | `drawdown_reaction`, `loss_tolerance`, `past_behaviour` |
| Risk comfort | `certainty`, `volatility_comfort`, `self_rating` |
| Speculative risk | `loss_focus` |

Where Salli departs from the scale, and why:

- **Experience is recorded, not scored.** The scale counts experience
  with risk comfort; Salli does not, because knowing markets is not
  wanting risk, and a newcomer's tolerance should not read as low for it.
- **Capacity questions are not tolerance.** The horizon, income stability
  and dependents are asked with the tolerance items but scored as capacity.

### Weights

Every item is worth **0 to 4 points**, the same for each:

- the 1-5 items score their answer less one (1 → 0, 5 → 4);
- `drawdown_reaction` scores `sell_all` 0, `sell_some` 1, `hold` 3,
  `buy_more` 4. It has no middle answer, so nothing scores 2: holding
  through a fall is nearer buying more than selling some.

Equal weights because the scale sums its items unweighted, and because no
weighting Salli could choose would be better grounded: a weight would be a
judgement no one could check. Only `drawdown_reaction` must be answered; the
score is the points' share of the most the **answered** items could make
(0-100), so an unanswered item neither helps nor hurts.

The score is bucketed: under 40 `conservative`, under 70 `balanced`, else
`aggressive`.

## Capacity

Five measures from your own figures, each worth 0 to 25 points, the score
their share of the most the measures present could make:

| Measure | 25 | Less |
|---|---|---|
| Emergency months (cash and savings ÷ monthly spending) | 6 or more | 15 from 3, 5 from 1, else 0 |
| Income stability (variation of monthly income, three months at least) | under 10% | 15 under 25%, 8 under 50%, else 0 |
| Horizon (years until the money is needed) | 15 or more | 20 from 10, 12 from 5, 5 from 2, else 0 |
| Debt service (debt payments ÷ income) | under 10% | 18 under 20%, 8 under 35%, else 0 |
| Dependents | none | 15 for one or two, else 5 |

Equal weights again: each measure is one way a loss would hurt, and none is
known to matter more for everyone. A measure without figures is left out
and named (`missing`), not scored zero. The bands are part of Salli's
method, not any country's figures.

## Need

The yearly real return your asset base and monthly saving need to reach
your FI number within your horizon, and the category it asks for. A need
above the profile says the plan asks more than you can or will take.
