# Entitlements by tier (example)

A reference `EntitlementPolicy` (`policy.py`) for a hosted deployment's own
extension: plan tiers mapped to the hypotheses in
[business/thesis.md](../../business/thesis.md). It is an example, not part of
Salli: the open core has no plans and shows everything (`FullAccess`), and
`src/` holds no plan or payment words (`tests/contract/test_no_commercial_vocabulary.py`).

| Tier | What it sees | The thesis row it tests |
|---|---|---|
| `self_hosted` | everything | What is sold: the self-hosted open core |
| `pilot` | everything | The design-partner pilot: activation and retention, not limits |
| `hosted_person` | everything | Who pays: salaried professionals keeping their own books |
| `hosted_household` | everything | Who pays: households in two currencies |
| `trial` (and anyone unplaced) | the books in full; FI projections to five years; the briefing without its notes | Pricing hypotheses: which depth people pay for |

Salli computes the whole, truthful payload every time; the policy only
leaves parts out, and lists them in `withheld`, so no figure shown is ever a
different one. Only the shapeable surfaces (`Surface` in
`salli.application.ports`: FI projections and the briefing) can be shaped.

Where a person's tier comes from is the deployment's: give `TierPolicy` an
async `tier_of(user_id)` reading its own records. To try it, register `spec`
under the `salli.extensions` entry-point group in a package of your own and
name it in `SALLI_EXTENSIONS` (see `salli/extensions.py`). The tests are
`tests/unit/extensions/test_entitlements_example.py`.
