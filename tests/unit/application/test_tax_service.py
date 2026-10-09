"""Unit tests for TaxService using in-memory fakes."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from salli.application.services.tax_service import TaxService, _build_ledger_view
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.tax.models import TaxComputation
from tests.fakes import FakeProfiles

# ── In-memory fakes ────────────────────────────────────────────────────────────


class FakeLedgerRepo:
    def __init__(self, entries=None, accounts=None):
        self._entries: list[StoredJournalEntry] = entries or []
        self._accounts: list[Account] = accounts or []

    async def save_account(self, user_id, account):
        self._accounts.append(account)
        return account.id

    async def get_accounts(self, user_id, include_inactive=False):
        return [a for a in self._accounts if a.user_id == user_id]

    async def save_entry(self, user_id, entry):
        return str(uuid.uuid4())

    async def get_entries(self, user_id, from_date=None, to_date=None):
        result = [e for e in self._entries if e.user_id == user_id]
        if from_date:
            result = [e for e in result if e.entry_date >= from_date]
        if to_date:
            result = [e for e in result if e.entry_date <= to_date]
        return result


class FakeTaxComputationRepo:
    def __init__(self):
        self._store: dict[tuple, TaxComputation] = {}

    async def save(self, user_id: str, computation: TaxComputation) -> str:
        self._store[(user_id, computation.pack_year)] = computation
        return str(uuid.uuid4())

    async def get_latest(self, user_id: str, year: str) -> TaxComputation | None:
        return self._store.get((user_id, year))

    async def list_computation_keys(self) -> list[tuple[str, str]]:
        return list(self._store.keys())


class FakeUoW:
    def __init__(self, ledger_repo, tax_repo):
        self.ledger = ledger_repo
        self.tax_computations = tax_repo
        self.user_profiles = FakeProfiles()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def _make_entry(user_id: str, date: str, postings: list[Posting]) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=str(uuid.uuid4()),
        user_id=user_id,
        entry_date=date,
        description="test",
        source="manual",
        postings=postings,
    )


def _make_account(
    user_id: str, code: str, name: str, acc_type: str, tax_role: str | None = None
) -> Account:
    return Account(
        id=str(uuid.uuid4()),
        user_id=user_id,
        code=code,
        name=name,
        type=acc_type,
        tax_role=tax_role,  # type: ignore[arg-type]
        currency="LKR",
    )


# ── _build_ledger_view tests ───────────────────────────────────────────────────


def test_build_ledger_view_income_credit():
    salary_acc = _make_account("u1", "4001", "Employment Income", "income")
    posting = Posting(
        account_id=salary_acc.id,
        direction=Direction.CREDIT,
        amount=Decimal("3_000_000"),
        currency="LKR",
    )
    entry = _make_entry(
        "u1",
        "2025-04-01",
        [
            Posting(
                account_id="asset",
                direction=Direction.DEBIT,
                amount=Decimal("3_000_000"),
                currency="LKR",
            ),
            posting,
        ],
    )
    view = _build_ledger_view([entry], [salary_acc])
    assert view.total_income == Decimal("3_000_000")
    assert view.foreign_service_income == Decimal(0)


def test_build_ledger_view_foreign_service_income():
    fsi_acc = _make_account("u1", "4500", "Foreign Service Income (FSI)", "income", "fsi_income")
    entry = _make_entry(
        "u1",
        "2025-04-01",
        [
            Posting(
                account_id="asset",
                direction=Direction.DEBIT,
                amount=Decimal("500_000"),
                currency="LKR",
            ),
            Posting(
                account_id=fsi_acc.id,
                direction=Direction.CREDIT,
                amount=Decimal("500_000"),
                currency="LKR",
            ),
        ],
    )
    view = _build_ledger_view([entry], [fsi_acc])
    assert view.total_income == Decimal("500_000")
    assert view.foreign_service_income == Decimal("500_000")


def test_build_ledger_view_apit_credit():
    apit_acc = _make_account("u1", "4110", "APIT Receivable", "asset", "apit_credit")
    # DR APIT Receivable = employer has remitted this amount to IRD on our behalf.
    # The offsetting CR is to bank/income (unknown to view → skipped by _build_ledger_view).
    entry = _make_entry(
        "u1",
        "2025-04-01",
        [
            Posting(
                account_id=apit_acc.id,
                direction=Direction.DEBIT,
                amount=Decimal("50_000"),
                currency="LKR",
            ),
            Posting(
                account_id="income-clearing",
                direction=Direction.CREDIT,
                amount=Decimal("50_000"),
                currency="LKR",
            ),
        ],
    )
    view = _build_ledger_view([entry], [apit_acc])
    assert view.apit_withheld == Decimal("50_000")


def test_build_ledger_view_empty():
    view = _build_ledger_view([], [])
    assert view.total_income == Decimal(0)
    assert view.apit_withheld == Decimal(0)
    assert view.foreign_service_income == Decimal(0)


# ── TaxService tests ───────────────────────────────────────────────────────────


def _make_tax_service_with_income(income: Decimal, apit: Decimal = Decimal(0)):
    salary_acc = _make_account("u1", "4001", "Employment Income", "income")
    apit_acc = _make_account("u1", "4110", "APIT Receivable", "asset", "apit_credit")

    # Entry 1: salary received (bank unknown to view → skipped on DR side)
    salary_entry = _make_entry(
        "u1",
        "2025-04-01",
        [
            Posting(account_id="bank", direction=Direction.DEBIT, amount=income, currency="LKR"),
            Posting(
                account_id=salary_acc.id, direction=Direction.CREDIT, amount=income, currency="LKR"
            ),
        ],
    )
    entries = [salary_entry]

    # Entry 2: APIT withheld — DR APIT Receivable (remitted to IRD), CR clearing
    if apit > 0:
        apit_entry = _make_entry(
            "u1",
            "2025-04-01",
            [
                Posting(
                    account_id=apit_acc.id, direction=Direction.DEBIT, amount=apit, currency="LKR"
                ),
                Posting(
                    account_id="clearing", direction=Direction.CREDIT, amount=apit, currency="LKR"
                ),
            ],
        )
        entries.append(apit_entry)

    accounts = [salary_acc, apit_acc]

    ledger_repo = FakeLedgerRepo(entries=entries, accounts=accounts)
    tax_repo = FakeTaxComputationRepo()

    @asynccontextmanager
    async def uow_factory():
        yield FakeUoW(ledger_repo, tax_repo)

    return TaxService(uow_factory), tax_repo


@pytest.mark.asyncio
async def test_compute_tax_below_relief():
    """Income below personal relief → zero tax."""
    svc, _ = _make_tax_service_with_income(Decimal("1_000_000"))
    result = await svc.compute_tax("u1", "2025/26")
    assert result.tax_payable == Decimal(0)
    assert result.taxable_income == Decimal(0)


@pytest.mark.asyncio
async def test_compute_tax_saves_computation():
    svc, tax_repo = _make_tax_service_with_income(Decimal("5_000_000"))
    await svc.compute_tax("u1", "2025/26")
    saved = await tax_repo.get_latest("u1", "2025/26")
    assert saved is not None
    assert saved.pack_country == "LK"


@pytest.mark.asyncio
async def test_compute_tax_pack_version_recorded():
    svc, _ = _make_tax_service_with_income(Decimal("3_000_000"))
    result = await svc.compute_tax("u1", "2025/26")
    assert result.pack_version == "1.0.0"
    assert result.pack_country == "LK"


@pytest.mark.asyncio
async def test_compute_tax_apit_reduces_payable():
    """APIT credit reduces the final tax payable."""
    svc_no_apit, _ = _make_tax_service_with_income(Decimal("4_000_000"))
    svc_with_apit, _ = _make_tax_service_with_income(Decimal("4_000_000"), apit=Decimal("100_000"))

    result_no_apit = await svc_no_apit.compute_tax("u1", "2025/26")
    result_with_apit = await svc_with_apit.compute_tax("u1", "2025/26")

    assert result_with_apit.tax_payable < result_no_apit.tax_payable
    assert result_with_apit.apit_credit == Decimal("100_000")


@pytest.mark.asyncio
async def test_compute_tax_unknown_year_raises():
    svc, _ = _make_tax_service_with_income(Decimal("3_000_000"))
    with pytest.raises(KeyError):
        await svc.compute_tax("u1", "1999/00")


@pytest.mark.asyncio
async def test_get_latest_computation_none_before_compute():
    svc, tax_repo = _make_tax_service_with_income(Decimal("3_000_000"))
    result = await svc.get_latest_computation("u1", "2025/26")
    assert result is None


@pytest.mark.asyncio
async def test_get_latest_computation_after_compute():
    svc, tax_repo = _make_tax_service_with_income(Decimal("3_000_000"))
    await svc.compute_tax("u1", "2025/26")
    saved = await tax_repo.get_latest("u1", "2025/26")
    assert saved is not None


def test_list_packs_includes_lk_2025_26():
    ledger_repo = FakeLedgerRepo()
    tax_repo = FakeTaxComputationRepo()

    @asynccontextmanager
    async def uow_factory():
        yield FakeUoW(ledger_repo, tax_repo)

    svc = TaxService(uow_factory)
    packs = svc.list_packs()
    keys = {(p.country, p.year) for p in packs}
    assert ("LK", "2025/26") in keys


# ── Regression: the seeded chart of accounts ──────────────────────────────────
#
# These tests exist because the previous suite hand-built "APIT Payable" as a
# `liability`, which no real user ever has. Onboarding seeds "4110 APIT
# Receivable" as an `asset`, and the old mapping only inspected liabilities — so
# every onboarded user's withheld tax was silently ignored and the tests passed
# anyway. Anything asserting on tax credits must be built from the same seed
# data the product actually creates.


def _seeded_accounts(user_id: str) -> list[Account]:
    """The accounts `/onboarding/complete` creates for a Sri Lankan resident
    who is employed and has interest and foreign income (`starter_chart`)."""
    from salli.application.services.onboarding_service import starter_chart

    seeds = starter_chart("LK", ("employment", "interest", "foreign"))
    return [
        _make_account(user_id, code, name, acc_type, role) for code, name, acc_type, role in seeds
    ]


def _by_code(accounts: list[Account], code: str) -> Account:
    return next(a for a in accounts if a.code == code)


def test_seeded_apit_account_produces_a_credit():
    """The exact bug: APIT withheld against the seeded (asset) account."""
    accounts = _seeded_accounts("u1")
    salary = _by_code(accounts, "4100")
    apit = _by_code(accounts, "4110")
    bank = _by_code(accounts, "1200")

    entry = _make_entry(
        "u1",
        "2025-04-01",
        [
            Posting(
                account_id=bank.id,
                direction=Direction.DEBIT,
                amount=Decimal("450_000"),
                currency="LKR",
            ),
            Posting(
                account_id=apit.id,
                direction=Direction.DEBIT,
                amount=Decimal("50_000"),
                currency="LKR",
            ),
            Posting(
                account_id=salary.id,
                direction=Direction.CREDIT,
                amount=Decimal("500_000"),
                currency="LKR",
            ),
        ],
    )

    view = _build_ledger_view([entry], accounts)
    assert view.total_income == Decimal("500_000")
    assert view.apit_withheld == Decimal("50_000"), (
        "APIT withheld against the seeded 4110 account must be credited; "
        "this is the defect that overstated every onboarded user's tax."
    )


def test_seeded_qualifying_payment_account_produces_a_deduction():
    accounts = _seeded_accounts("u1")
    donations = _by_code(accounts, "5900")
    bank = _by_code(accounts, "1200")

    entry = _make_entry(
        "u1",
        "2025-06-01",
        [
            Posting(
                account_id=donations.id,
                direction=Direction.DEBIT,
                amount=Decimal("25_000"),
                currency="LKR",
            ),
            Posting(
                account_id=bank.id,
                direction=Direction.CREDIT,
                amount=Decimal("25_000"),
                currency="LKR",
            ),
        ],
    )

    view = _build_ledger_view([entry], accounts)
    assert view.qualifying_payments == Decimal("25_000")


# ── Regression: reversing entries must net out ────────────────────────────────


def _reverse(entry: StoredJournalEntry) -> StoredJournalEntry:
    """Mirror of LedgerService.reverse_entry — flips every posting's direction."""
    return _make_entry(
        entry.user_id,
        entry.entry_date,
        [
            Posting(
                account_id=p.account_id,
                direction=Direction(-p.direction.value),
                amount=p.amount,
                currency=p.currency,
            )
            for p in entry.postings
        ],
    )


def test_reversing_an_income_entry_removes_it_from_the_tax_base():
    """Entries are immutable, so a reversal is the only way to correct one.
    The tax view has to honour that or a mistaken income entry stays taxable
    forever."""
    accounts = _seeded_accounts("u1")
    salary = _by_code(accounts, "4100")
    bank = _by_code(accounts, "1200")

    entry = _make_entry(
        "u1",
        "2025-04-01",
        [
            Posting(
                account_id=bank.id,
                direction=Direction.DEBIT,
                amount=Decimal("500_000"),
                currency="LKR",
            ),
            Posting(
                account_id=salary.id,
                direction=Direction.CREDIT,
                amount=Decimal("500_000"),
                currency="LKR",
            ),
        ],
    )

    assert _build_ledger_view([entry], accounts).total_income == Decimal("500_000")

    view = _build_ledger_view([entry, _reverse(entry)], accounts)
    assert view.total_income == Decimal(0), "a reversed income entry must leave the tax base"


def test_reversing_a_donation_removes_the_deduction():
    accounts = _seeded_accounts("u1")
    donations = _by_code(accounts, "5900")
    bank = _by_code(accounts, "1200")

    entry = _make_entry(
        "u1",
        "2025-06-01",
        [
            Posting(
                account_id=donations.id,
                direction=Direction.DEBIT,
                amount=Decimal("25_000"),
                currency="LKR",
            ),
            Posting(
                account_id=bank.id,
                direction=Direction.CREDIT,
                amount=Decimal("25_000"),
                currency="LKR",
            ),
        ],
    )

    view = _build_ledger_view([entry, _reverse(entry)], accounts)
    assert view.qualifying_payments == Decimal(0)


def test_buckets_never_go_negative():
    """A stray reversal with no original must not manufacture a refund."""
    accounts = _seeded_accounts("u1")
    apit = _by_code(accounts, "4110")
    bank = _by_code(accounts, "1200")

    orphan_reversal = _make_entry(
        "u1",
        "2025-04-01",
        [
            Posting(
                account_id=apit.id,
                direction=Direction.CREDIT,
                amount=Decimal("50_000"),
                currency="LKR",
            ),
            Posting(
                account_id=bank.id,
                direction=Direction.DEBIT,
                amount=Decimal("50_000"),
                currency="LKR",
            ),
        ],
    )

    view = _build_ledger_view([orphan_reversal], accounts)
    assert view.apit_withheld == Decimal(0)


# ── Backfill: re-running stored computations after an engine fix ──────────────


def _service_with_seeded_ledger(apit: Decimal):
    """A TaxService whose ledger has salary plus APIT withheld against the
    seeded (asset) 4110 account."""
    accounts = _seeded_accounts("u1")
    salary = _by_code(accounts, "4100")
    apit_acc = _by_code(accounts, "4110")
    bank = _by_code(accounts, "1200")
    income = Decimal("3_000_000")

    entry = _make_entry(
        "u1",
        "2025-04-01",
        [
            Posting(
                account_id=bank.id, direction=Direction.DEBIT, amount=income - apit, currency="LKR"
            ),
            Posting(account_id=apit_acc.id, direction=Direction.DEBIT, amount=apit, currency="LKR"),
            Posting(
                account_id=salary.id, direction=Direction.CREDIT, amount=income, currency="LKR"
            ),
        ],
    )
    ledger = FakeLedgerRepo(entries=[entry], accounts=accounts)
    tax_repo = FakeTaxComputationRepo()

    @asynccontextmanager
    async def uow_factory():
        yield FakeUoW(ledger, tax_repo)

    return TaxService(uow_factory), tax_repo


@pytest.mark.asyncio
async def test_compute_tax_persist_false_does_not_record():
    svc, repo = _service_with_seeded_ledger(Decimal("50_000"))
    result = await svc.compute_tax("u1", "2025/26", persist=False)
    assert result.apit_credit == Decimal("50_000")
    assert await repo.get_latest("u1", "2025/26") is None, "preview must not write"


@pytest.mark.asyncio
async def test_recompute_stored_reports_the_correction_without_applying():
    """A computation stored by the old engine credited no APIT. A dry run must
    surface the difference and change nothing."""
    svc, repo = _service_with_seeded_ledger(Decimal("50_000"))

    # Simulate a pre-fix stored row: same income, but no credit recognised.
    stale = await svc.compute_tax("u1", "2025/26", persist=False)
    repo._store[("u1", "2025/26")] = {
        **{k: str(v) for k, v in (("tax_payable", stale.tax_payable + Decimal("50_000")),)},
        "total_credits": "0",
    }

    report = await svc.recompute_stored(apply=False)
    assert len(report) == 1
    row = report[0]
    assert row["changed"] is True
    assert row["applied"] is False
    assert row["old_credits"] == "0"
    assert row["new_credits"] == "50000"
    # Still the stale dict — a dry run writes nothing.
    assert isinstance(await repo.get_latest("u1", "2025/26"), dict)


@pytest.mark.asyncio
async def test_recompute_stored_applies_the_correction():
    svc, repo = _service_with_seeded_ledger(Decimal("50_000"))
    fresh = await svc.compute_tax("u1", "2025/26", persist=False)
    repo._store[("u1", "2025/26")] = {"tax_payable": "999999", "total_credits": "0"}

    report = await svc.recompute_stored(apply=True)
    assert report[0]["applied"] is True

    stored = await repo.get_latest("u1", "2025/26")
    assert not isinstance(stored, dict), "the corrected result replaced the stale row"
    assert stored.tax_payable == fresh.tax_payable
    assert stored.apit_credit == Decimal("50_000")


@pytest.mark.asyncio
async def test_recompute_stored_skips_rows_that_do_not_move():
    """Re-running must not pile up identical history entries."""
    svc, repo = _service_with_seeded_ledger(Decimal("50_000"))
    await svc.compute_tax("u1", "2025/26", persist=True)

    report = await svc.recompute_stored(apply=True)
    assert report[0]["changed"] is False
    assert report[0]["applied"] is False


@pytest.mark.asyncio
async def test_recompute_ignores_a_pure_scale_difference():
    """Credit totals carry the fx_rate's Numeric(20,8) scale, so the same amount
    can be written "250000" or "250000.00000000". That must not count as a
    change, or every sweep would rewrite every row forever."""
    svc, repo = _service_with_seeded_ledger(Decimal("50_000"))
    fresh = await svc.compute_tax("u1", "2025/26", persist=False)
    # Same numbers, written with the 8-dp scale the fx_rate column imposes.
    scaled = Decimal("0.00000001")
    repo._store[("u1", "2025/26")] = {
        "tax_payable": str(fresh.tax_payable.quantize(scaled)),
        "total_credits": str(fresh.total_credits.quantize(scaled)),
    }

    report = await svc.recompute_stored(apply=True)
    assert report[0]["changed"] is False
    assert report[0]["applied"] is False


def test_money_report_strings_are_trimmed():
    from salli.application.services.tax_service import _fmt_money

    assert _fmt_money("250000.00000000") == "250000"
    assert _fmt_money(Decimal("0")) == "0"
    assert _fmt_money("1234.50") == "1234.5"
    # A value that was never recorded passes through untouched.
    assert _fmt_money("—") == "—"
