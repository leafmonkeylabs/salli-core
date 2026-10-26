"""
Moving books between servers (docs/self-host.md, "Moving your books"): the
golden households exported from one database and restored into a new
person on a fresh one export again the same, but for who they are and the
hashes that cover it; their ledger verifies and their figures agree. A
restore goes into empty books only, checks the export's chain, and is one
transaction.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import zipfile
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.encoders import jsonable_encoder

from salli.application import acting
from salli.application.permissions import Actor
from salli.application.ports import RestoreCollision
from salli.application.services.baseline_service import BaselineService
from salli.application.services.data_portability_service import BooksNotEmpty
from salli.application.services.fi_service import FiService
from salli.application.services.insights_service import InsightsService
from salli.application.services.ledger_service import LedgerService
from salli.application.services.report_service import ReportService
from salli.application.services.tax_service import TaxService
from salli.config import Settings
from salli.domain.accounting.models import Direction
from salli.domain.export.restore import ExportRefused
from salli.migrations.support import CORE_SCRIPT_LOCATION, upgrade
from tests.golden import household as h
from tests.integration.conftest import as_app_role
from tests.integration.pg import requires_postgres, scratch_database
from tests.integration.test_tax_service import remitland
from tests.unit.domain.test_fi_odds import pack

pytestmark = [requires_postgres, pytest.mark.asyncio]

ANA, BEA = "ana-on-the-hosted-server", "bea-on-her-own"


def _services(url: str, storage: Any) -> Any:
    from salli.composition import build_services

    settings = Settings(
        _env_file=None,
        database_url=url,
        salli_storage_dir=str(storage),
        mcp_signing_secret="s" * 48,
    )
    return build_services(settings)


@pytest.fixture
def fresh_db(db, monkeypatch) -> Iterator[str]:
    """A second server's database, as fresh as the first."""
    with scratch_database() as url:
        other = as_app_role(url)
        monkeypatch.setenv("DATABASE_URL", other)
        upgrade(CORE_SCRIPT_LOCATION)
        yield other


@pytest.fixture
def servers(db, fresh_db, tmp_path) -> tuple[Any, Any]:
    """The server the books are on, and a fresh one, each with its own
    database and files."""
    return _services(db, tmp_path / "a"), _services(fresh_db, tmp_path / "b")


async def _profile(svc: Any, user: str, **fields: Any) -> None:
    with acting.acting_as(user):
        async with svc.ledger._uow_factory() as uow:  # noqa: SLF001
            await uow.user_profiles.upsert(user, fields)


async def _household(svc: Any, user: str) -> None:
    """The golden household (tests/golden/household.py), and something of
    every kind a restore takes."""
    await _profile(
        svc, user, base_currency=h.BASE, books_start=dt.date(2026, 3, 31), time_zone="Europe/Rome"
    )
    ids = {
        a.id: await svc.ledger.add_account(
            user, a.code, a.name, a.type, a.currency, asset_role=a.asset_role
        )
        for a in h.ACCOUNTS
    }
    for e in h.ENTRIES:
        await svc.ledger.add_entry(
            user,
            e.entry_date,
            e.description,
            e.source,
            [
                {
                    "account_id": ids[p.account_id],
                    "direction": p.direction,
                    "amount": p.amount,
                    "currency": p.currency,
                    "fx_rate": None if p.currency == h.BASE else p.fx_rate,
                    "tags": dict(p.tags),
                }
                for p in e.postings
            ],
            e.external_ref,
        )
    entries = await svc.ledger.get_entries(user)
    await svc.ledger.reverse_entry(user, entries[-1].id, "Booked twice")
    with acting.acting_as(user):
        async with svc.ledger._uow_factory() as uow:  # noqa: SLF001
            await uow.reconciliations.set_cleared(user, [entries[0].postings[0].id], True)
    await svc.ledger.set_lock_date(user, "2026-04-30")
    await svc.debt.add_debt(
        user,
        {
            "name": "Car loan",
            "principal": "10200",
            "apr": "0.059",
            "minimum_payment": "350",
            "account_id": ids["loan"],
        },
    )
    await svc.debt.add_debt(
        user,
        {"name": "Student loan", "principal": "8000", "apr": "0.045", "minimum_payment": "120"},
    )
    await svc.fi.create_goal(
        user, {"name": "Rainy day", "kind": "emergency_fund", "target_amount": "9000"}
    )
    holding = await svc.portfolio.add_holding(
        user,
        {"symbol": "WRLD", "name": "World fund", "asset_class": "equity", "account_id": ids["brk"]},
    )
    await svc.portfolio.add_transaction(
        user, holding, {"kind": "buy", "date": "2026-04-26", "quantity": "10", "price": "50"}
    )
    await svc.portfolio.set_price(user, {"symbol": "WRLD", "close": "52.5", "date": "2026-10-09"})
    await svc.principles.add(user, {"label": "Six months put by", "check": "emergency_months >= 6"})
    await svc.reminders.create_reminder(user, "Renew the car insurance", "2026-12-01")
    await svc.budget.create_budget(
        user, "2026-10-01", "2026-10-31", [{"account_id": ids["food"], "limit_amount": "450"}]
    )
    await svc.fi.import_cma_pack(user, pack())
    await svc.documents.save_file(user, "lease.pdf", b"%PDF the lease", "application/pdf")
    await svc.notifications.set_preferences(user, {"cadence": "monthly", "hour": 8})


async def _taxed(svc: Any, user: str) -> None:
    """Remitland's household: its rules active, its year computed, filed
    and closed (tests/integration/test_filed_years.py)."""
    await _profile(svc, user, base_currency="KWD", tax_residency="GB")
    me = Actor.signed_in(user, "session")
    version = await svc.tax_rules.draft(me, remitland())
    await svc.tax_rules.activate(me, version["id"])
    bank = await svc.ledger.add_account(user, "1000", "Bank", "asset")
    pay = await svc.ledger.add_account(user, "4000", "Salary", "income", tax_role="local_income")
    await svc.ledger.add_entry(
        user,
        "2031-06-30",
        "Salary",
        "manual",
        [
            {"account_id": bank, "direction": Direction.DEBIT, "amount": Decimal("1000.000")},
            {"account_id": pay, "direction": Direction.CREDIT, "amount": Decimal("1000.000")},
        ],
    )
    factory, later = svc.ledger._uow_factory, dt.date(2032, 10, 10)  # noqa: SLF001
    tax = TaxService(factory, svc.tax_rules, clock=lambda: later)
    computation = await tax.compute_tax(user, country="XG", year="2031/32")
    await LedgerService(factory, today=lambda: later).set_lock_date(user, "2032-03-31")
    await tax.record_return(
        user, computation["id"], "filed", reference="XG-123", filed_on=dt.date(2032, 6, 1)
    )


def _archive(svc: Any, user: str) -> Any:
    return svc.data_portability.export_archive(
        user, lambda data: json.dumps(jsonable_encoder(data)).encode()
    )


def _comparable(export: dict[str, Any], user: str, hashes: dict[str, str]) -> Any:
    """An export with what a move changes taken out: who the person is (and
    the storage keys under their folder; the entries say who posted them as
    recorded, the person's id on the server they came from), the entries'
    hashes that cover it,
    when the profile changed, and the audit trail (each server's own)."""
    export = json.loads(json.dumps(jsonable_encoder(export)))
    for key in ("audit_log", "conversations"):
        export.pop(key)
    rows = export["rows"]
    for key in ("audit_logs", "restores"):
        rows.pop(key)
    for key in ("created_at", "updated_at", "email", "id"):
        rows["user_profiles"][0].pop(key)
        export["profile"].pop(key, None)
    # A posting's place among its entry's is not stored: the hash sorts them.
    for entry in export["journal_entries"]:
        entry["postings"].sort(key=lambda p: json.dumps(p, sort_keys=True))
    text = json.dumps(export, sort_keys=True)
    for person in (user, ANA):
        text = text.replace(person, "<person>")
    for old, new in hashes.items():
        text = text.replace(new, old)
    return json.loads(text)


@pytest.mark.parametrize("books", [_household, _taxed])
async def test_moved_books_export_again_the_same_verify_and_say_the_same(servers, books):
    a, b = servers
    await books(a, ANA)
    exported = await a.data_portability.export_all(ANA)
    archive = await _archive(a, ANA)

    result = await b.data_portability.restore(BEA, archive)

    assert result["entries"] == len(exported["rows"]["journal_entries"])
    assert result["files_missing"] == []
    again = await b.data_portability.export_all(BEA)
    hashes = {
        o["hash"]: n["hash"]
        for o, n in zip(
            exported["rows"]["journal_entries"], again["rows"]["journal_entries"], strict=True
        )
    }
    assert _comparable(again, BEA, hashes) == _comparable(exported, ANA, {})
    assert (await b.ledger.verify_chain(BEA))["ok"] is True
    assert result["chain_head"] == again["rows"]["journal_entries"][-1]["hash"]

    # The other server's audit rows, kept apart; and the restore, in this one's.
    (restored,) = again["rows"]["restores"]
    assert restored["audit_rows"] == exported["rows"]["audit_logs"]
    assert restored["source_user_id"] == ANA
    assert [r["action"] for r in again["audit_log"]] == ["books.restore"]
    assert again["audit_log"][0]["params"]["export"] == result["export_hash"]

    # The lock date holds on the new server, from the first entry it closes.
    assert again["profile"]["lock_date"] == exported["profile"]["lock_date"]
    for key in exported["rows"]["agent_documents"]:
        if key.get("storage_key"):
            moved = next(d for d in again["rows"]["agent_documents"] if d["id"] == key["id"])
            assert moved["storage_key"].startswith(f"{BEA}/")
            assert await b.storage.download(moved["storage_key"]) == b"%PDF the lease"


async def test_the_households_figures_are_the_same_on_the_new_server(servers):
    a, b = servers
    await _household(a, ANA)
    await b.data_portability.restore(BEA, await _archive(a, ANA))

    async def figures(svc: Any, user: str) -> Any:
        factory = svc.ledger._uow_factory  # noqa: SLF001
        today = lambda: h.AS_OF  # noqa: E731
        baselines = BaselineService(factory, fx=h.fx(), today=today)
        fi = FiService(factory, baselines=baselines, today=today)
        insights = InsightsService(factory, today=today, baselines=baselines)
        reports = ReportService(svc.ledger, fi, baselines)
        return (
            await reports.get_balance_sheet(user, h.AS_OF.isoformat()),
            await fi.compute_score(user),
            await insights.safe_to_spend(user),
        )

    sheet, score, safe = await figures(b, BEA)
    assert (sheet, score, safe) == await figures(a, ANA)
    assert sheet["net_worth"] != "0.00"


async def test_a_restore_goes_into_empty_books_only(servers):
    a, b = servers
    await _household(a, ANA)
    archive = await _archive(a, ANA)
    await _profile(b, BEA, base_currency="NZD")
    # The starter chart is fine: it is replaced.
    starter = await b.ledger.add_account(BEA, "1000", "Bank", "asset")
    await b.reminders.create_reminder(BEA, "Something of hers", "2031-01-01")

    with pytest.raises(BooksNotEmpty) as refused:
        await b.data_portability.restore(BEA, archive)
    assert refused.value.found == ["reminders"]

    for r in await b.reminders.list_reminders(BEA):
        await b.reminders.delete_reminder(BEA, r["id"])
    await b.data_portability.restore(BEA, archive)
    accounts = await b.ledger.list_accounts(BEA, include_inactive=True)
    assert starter not in {x.id for x in accounts}
    assert (await b.profile.get_profile(BEA))["base_currency"] == h.BASE

    # Once there, a second restore is refused: the books aren't empty now.
    with pytest.raises(BooksNotEmpty):
        await b.data_portability.restore(BEA, archive)


async def test_books_already_on_the_server_are_not_restored_twice(servers):
    a, _ = servers
    await _household(a, ANA)
    await _profile(a, "cal", base_currency="EUR")
    with pytest.raises(RestoreCollision):
        await a.data_portability.restore("cal", await _archive(a, ANA))
    # Nor does one whose rows point past the books it holds.
    document = json.loads(json.dumps(jsonable_encoder(await a.data_portability.export_all(ANA))))
    document["rows"]["principles"][0]["account_id"] = "someone-elses-account"
    document["rows"]["agent_documents"] = []
    with pytest.raises(RestoreCollision, match=r"principles\.account_id"):
        await a.data_portability.restore("cal", json.dumps(document).encode())
    # Nothing of it stayed: neither rows nor files.
    assert await a.ledger.get_entries("cal") == []
    assert await a.documents.list_documents("cal") == []


async def test_a_broken_chain_a_newer_version_or_missing_files_are_refused(servers):
    a, b = servers
    await _household(a, ANA)
    document = json.loads(json.dumps(jsonable_encoder(await a.data_portability.export_all(ANA))))

    def payload(doc: dict[str, Any]) -> bytes:
        return json.dumps(doc).encode()

    with pytest.raises(ExportRefused, match="stored files: restore the archive"):
        await b.data_portability.restore(BEA, payload(document))

    tampered = json.loads(json.dumps(document))
    tampered["rows"]["journal_entries"][4]["description"] = "Something else"
    with pytest.raises(ExportRefused, match=r"entry 5 \(.*\) fails its hash chain \(content\)"):
        await b.data_portability.restore(BEA, payload(tampered))

    newer = {**document, "export_version": 3}
    with pytest.raises(ExportRefused, match="newer than this server knows"):
        await b.data_portability.restore(BEA, payload(newer))
    old = {k: v for k, v in document.items() if k not in ("rows", "export_version")}
    with pytest.raises(ExportRefused, match="version 1"):
        await b.data_portability.restore(BEA, payload(old))

    # An archive without one of its files keeps the record, and says so.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("export.json", payload(document))
    result = await b.data_portability.restore(BEA, buffer.getvalue())
    assert len(result["files_missing"]) == 1
