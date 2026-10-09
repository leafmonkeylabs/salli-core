"""
Duplicate detection: an import against earlier imports (exact, count for
count) and against the ledger (fuzzy, for review) — never against itself.
"""

from __future__ import annotations

from decimal import Decimal

from salli.domain.accounting.models import Direction, Posting, StoredJournalEntry
from salli.domain.dedup.matcher import (
    Candidate,
    DedupStatus,
    Imported,
    Verdict,
    dedup_key,
    find_duplicates,
)
from salli.domain.rules.engine import Facts
from salli.domain.rules.history import Booked

UNIQUE = Verdict(DedupStatus.UNIQUE)


def row(
    description: str = "BLUE BOTTLE COFFEE",
    amount: str = "4.50",
    date: str = "2026-10-02",
    money_in: bool = False,
    bank_ref: str = "",
    currency: str = "USD",
) -> Candidate:
    return Candidate(date, Decimal(amount), currency, money_in, description, bank_ref)


def earlier(id_: str, candidate: Candidate, account_id: str = "checking") -> Imported:
    return Imported(id_, candidate, account_id)


def booked(
    entry_id: str,
    description: str,
    amount: str = "4.50",
    date: str = "2026-10-02",
    money_in: bool = False,
    money_account: str = "checking",
    counter: str = "food",
    external_ref: str | None = None,
) -> Booked:
    money_direction = Direction.DEBIT if money_in else Direction.CREDIT
    other_direction = Direction.CREDIT if money_in else Direction.DEBIT
    entry = StoredJournalEntry(
        id=entry_id,
        user_id="u1",
        entry_date=date,
        description=description,
        source="manual",
        external_ref=external_ref,
        postings=[
            Posting(
                account_id=money_account,
                direction=money_direction,
                amount=Decimal(amount),
                currency="USD",
            ),
            Posting(
                account_id=counter,
                direction=other_direction,
                amount=Decimal(amount),
                currency="USD",
            ),
        ],
    )
    facts = Facts(description, Decimal(amount), "in" if money_in else "out", "USD")
    return Booked(entry, facts, money_account, counter)


# ── Within one import ─────────────────────────────────────────────────────────


def test_two_identical_coffees_in_one_statement_are_two_coffees():
    assert find_duplicates([row(), row()], account_id="checking") == [UNIQUE, UNIQUE]


# ── Against earlier imports ───────────────────────────────────────────────────


def test_a_reimport_is_found_by_the_banks_reference():
    before = earlier("p1", row("POS 4821 BLUE BOTTLE", bank_ref="FIT-1"))
    # The bank tidied its description since, and booked it a day later.
    again = row("BLUE BOTTLE COFFEE SF", date="2026-10-03", bank_ref="FIT-1")

    assert find_duplicates([again], account_id="checking", imported=[before]) == [
        Verdict(DedupStatus.EXACT_DUPLICATE, "p1")
    ]


def test_a_reference_reused_for_another_amount_is_another_transaction():
    before = earlier("p1", row(amount="4.50", bank_ref="1043"))
    assert find_duplicates([row(amount="99.00", bank_ref="1043")], imported=[before]) == [UNIQUE]


def test_a_reimport_without_references_is_matched_count_for_count():
    # Two coffees now, one imported before: one of the two is new.
    verdicts = find_duplicates(
        [row(), row()], account_id="checking", imported=[earlier("p1", row())]
    )
    assert verdicts == [Verdict(DedupStatus.EXACT_DUPLICATE, "p1"), UNIQUE]

    both = find_duplicates(
        [row(), row()],
        account_id="checking",
        imported=[earlier("p1", row()), earlier("p2", row())],
    )
    assert both == [
        Verdict(DedupStatus.EXACT_DUPLICATE, "p1"),
        Verdict(DedupStatus.EXACT_DUPLICATE, "p2"),
    ]


def test_identity_ignores_case_and_punctuation_but_nothing_else():
    before = [earlier("p1", row("Blue Bottle Coffee."))]
    assert find_duplicates([row("BLUE BOTTLE COFFEE")], imported=before)[0].duplicate_of == "p1"
    for different in (
        row(amount="4.51"),
        row(date="2026-10-03"),
        row(money_in=True),
        row(currency="EUR"),
        row("BLUE BOTTLE TEA"),
    ):
        assert find_duplicates([different], imported=before) == [UNIQUE]


def test_rows_the_bank_gave_different_references_are_different():
    before = [earlier("p1", row(bank_ref="FIT-1"))]
    assert find_duplicates([row(bank_ref="FIT-2")], imported=before) == [UNIQUE]
    # A reference on one side only does not stop the match.
    assert find_duplicates([row(bank_ref="FIT-2")], imported=[earlier("p1", row())]) == [
        Verdict(DedupStatus.EXACT_DUPLICATE, "p1")
    ]


def test_another_account_is_not_matched():
    before = [earlier("p1", row(bank_ref="FIT-1"), account_id="savings")]
    assert find_duplicates([row(bank_ref="FIT-1")], account_id="checking", imported=before) == [
        UNIQUE
    ]
    # When either side does not say which account it is on, it may match.
    assert find_duplicates([row(bank_ref="FIT-1")], imported=before)[0].duplicate_of == "p1"
    unknown = [earlier("p1", row(), account_id="")]
    assert find_duplicates([row()], account_id="checking", imported=unknown)[0].duplicate_of == (
        "p1"
    )


# ── Against the ledger ────────────────────────────────────────────────────────


def test_an_entry_booked_by_hand_is_flagged_not_dropped():
    manual = booked("e1", "Blue Bottle coffee", date="2026-10-04")

    (verdict,) = find_duplicates([row()], account_id="checking", booked=[manual])

    assert (verdict.status, verdict.duplicate_of) == (DedupStatus.FUZZY_MATCH, "e1")
    assert verdict.similarity is not None and verdict.similarity >= 80


def test_the_ledger_match_needs_the_money_the_days_and_the_words():
    for unlike in (
        booked("e1", "Blue Bottle coffee", amount="5.00"),
        booked("e1", "Blue Bottle coffee", money_in=True),
        booked("e1", "Blue Bottle coffee", date="2026-10-06"),  # four days
        booked("e1", "Electricity bill"),
    ):
        assert find_duplicates([row()], booked=[unlike]) == [UNIQUE]


def test_an_entry_on_another_account_is_not_matched():
    on_card = booked("e1", "BLUE BOTTLE COFFEE", money_account="card")
    assert find_duplicates([row()], account_id="checking", booked=[on_card]) == [UNIQUE]
    # Any money account, when the import does not say which it is on.
    assert find_duplicates([row()], booked=[on_card])[0].duplicate_of == "e1"


def test_an_entry_stands_for_one_row():
    manual = booked("e1", "BLUE BOTTLE COFFEE")
    verdicts = find_duplicates([row(), row()], account_id="checking", booked=[manual])
    assert [v.status for v in verdicts] == [DedupStatus.FUZZY_MATCH, DedupStatus.UNIQUE]


def test_an_entry_posted_from_a_matched_import_is_not_matched_again():
    # p1 was imported and posted as e1. The re-import matches p1; e1 is that
    # same transaction, so it must not also flag the second coffee.
    posted = booked("e1", "BLUE BOTTLE COFFEE", external_ref="p1")
    verdicts = find_duplicates(
        [row(), row()], account_id="checking", imported=[earlier("p1", row())], booked=[posted]
    )
    assert verdicts == [Verdict(DedupStatus.EXACT_DUPLICATE, "p1"), UNIQUE]


def test_a_transfer_shows_on_both_accounts():
    transfer = booked("e1", "Transfer to savings", amount="500.00", counter="savings")
    arrived = row("TRANSFER TO SAVINGS", amount="500.00", money_in=True)
    (verdict,) = find_duplicates(
        [arrived], account_id="savings", booked=[transfer], money_accounts={"checking", "savings"}
    )
    assert (verdict.status, verdict.duplicate_of) == (DedupStatus.FUZZY_MATCH, "e1")


def test_the_dedup_key_is_the_identity():
    assert dedup_key(row("Blue Bottle Coffee")) == dedup_key(row("BLUE BOTTLE COFFEE"))
    assert dedup_key(row(amount="4.5")) == dedup_key(row(amount="4.50"))
    assert dedup_key(row()) != dedup_key(row(amount="4.51"))
    assert len(dedup_key(row())) == 64
