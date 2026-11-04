"""Seed a local Salli server with a clearly fake Sri Lankan household, so the
phone app's long LKR figures and every screen can be looked at.

    SALLI_SEED_EMAIL=nimali@example.com SALLI_SEED_PASSWORD=... \
        python3 packages/mobile/scripts/seed-sample-household.py [http://localhost:8000]

Needs only httpx (`uv run python ...` has it). The person must exist already
(`salli-server setup --currency LKR`). Run it once on a fresh database.
"""

from __future__ import annotations

import datetime as dt
import os
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
TODAY = dt.date.today()


def day(back: int) -> str:
    return (TODAY - dt.timedelta(days=back)).isoformat()


def main() -> None:
    http = httpx.Client(base_url=BASE, timeout=60)
    session = http.post(
        "/v1/auth/sessions",
        json={"email": os.environ["SALLI_SEED_EMAIL"], "password": os.environ["SALLI_SEED_PASSWORD"]},
    )
    session.raise_for_status()
    http.headers["authorization"] = "Bearer " + session.json()["token"]

    def call(method: str, path: str, **kw):
        r = http.request(method, path, **kw)
        if r.status_code >= 400:
            sys.exit(f"{method} {path}: {r.status_code} {r.text[:400]}")
        return r.json() if r.content else None

    call("PATCH", "/v1/onboarding/profile", json={"books_start": day(60)})
    # Opening balances: net worth well over 1,000,000 LKR, with decimals.
    call(
        "POST",
        "/v1/onboarding/balance-sheet",
        json={
            "balances": [
                {"code": "1200", "name": "Bank Account", "type": "asset", "asset_role": "cash", "amount": "1284560.75"},
                {"code": "1100", "name": "Cash", "type": "asset", "asset_role": "cash", "amount": "18450.00"},
                {"code": "1300", "name": "Savings (fixed deposit)", "type": "asset", "asset_role": "savings", "amount": "3250000.40"},
                {"code": "2100", "name": "Credit card", "type": "liability", "amount": "87320.55", "rate": "0.24", "minimum_payment": "8732.06"},
                {"code": "2200", "name": "Car loan", "type": "liability", "amount": "2150000.00", "rate": "0.14", "minimum_payment": "62500.00"},
            ]
        },
    )
    call("POST", "/v1/onboarding/income", json={"incomes": [{"code": "4100", "name": "Salary", "deposit_account_code": "1200"}]})
    accounts = {a["name"]: a["id"] for a in call("GET", "/v1/accounts/")}

    def entry(back: int, text: str, debit: str, credit: str, amount: str) -> None:
        call(
            "POST",
            "/v1/entries/",
            json={
                "entry_date": day(back),
                "description": text,
                "postings": [
                    {"account_id": accounts[debit], "direction": 1, "amount": amount},
                    {"account_id": accounts[credit], "direction": -1, "amount": amount},
                ],
            },
        )

    expense = {}
    for code, name in [("5100", "Rent"), ("5200", "Electricity"), ("5300", "Groceries"), ("5400", "Transport"), ("5500", "Dining out")]:
        expense[name] = call("POST", "/v1/accounts/", json={"code": code, "name": name, "type": "expense", "currency": "LKR"})["id"]
    accounts.update(expense)
    entry(3, "Salary", "Bank Account", "Employment Income", "245000.00")
    entry(2, "Rent", "Rent", "Bank Account", "55000.00")
    entry(2, "Electricity (CEB)", "Electricity", "Bank Account", "6400.00")
    entry(1, "Groceries, Keells", "Groceries", "Bank Account", "21850.50")
    entry(1, "Groceries, Cargills", "Groceries", "Cash", "9400.00")
    entry(1, "Fuel and bus", "Transport", "Bank Account", "14250.00")
    entry(0, "Dinner out", "Dining out", "Credit card", "18900.00")

    this_month = TODAY.replace(day=1)
    next_month = (this_month + dt.timedelta(days=32)).replace(day=1)
    call(
        "PUT",
        "/v1/budget/monthly",
        json={
            "lines": [
                {"account_id": expense["Rent"], "limit_amount": "55000.00"},
                {"account_id": expense["Groceries"], "limit_amount": "25000.00"},
                {"account_id": expense["Dining out"], "limit_amount": "12000.00"},
                {"account_id": expense["Transport"], "limit_amount": "20000.00"},
            ]
        },
    )
    del this_month, next_month

    for name, target, years in [("Emergency fund", "1500000.00", 1), ("Family trip to Galle", "420000.00", 1), ("Deposit for a house", "6500000.00", 5)]:
        call("POST", "/v1/fi/goals", json={"name": name, "kind": "savings", "target_amount": target, "target_date": day(-365 * years)})

    call("POST", "/v1/reminders/", json={"kind": "Renew vehicle revenue licence", "due_date": day(4)})
    call("POST", "/v1/reminders/", json={"kind": "Pay the water bill", "due_date": day(-6)})

    call(
        "POST",
        "/v1/decisions",
        json={
            "question": "Prepay the car loan or keep the cash?",
            "options": [{"schema": "salli.scenario/1", "label": "Keep the cash", "as_of": day(60), "changes": []}],
            "chosen": "Keep the cash",
            "reasons": "Sample decision: I want six months in hand first.",
            "review_on": day(5),
        },
    )

    merchants = [
        ("Keells Super", "6420.00"), ("Uber trip", "1850.00"), ("Dialog bill", "3100.00"),
        ("Cargills Food City", "11870.25"), ("Pharmacy", "2350.00"), ("Fuel, Ceypetco", "9000.00"),
        ("Water board", "1240.00"), ("Salary", "245000.00"), ("Netflix", "1990.00"),
        ("Odel", "15400.00"), ("Lunch, Barista", "2650.00"), ("Internet, SLT", "5400.00"),
    ]
    call(
        "POST",
        "/v1/statements/drafts",
        json={
            "account_id": accounts["Bank Account"],
            "source": "sample-statement.csv",
            "transactions": [
                {"date": day(i + 1), "description": m, "amount": a, "credit_flag": m == "Salary", "bank_ref": f"S{i:03d}"}
                for i, (m, a) in enumerate(merchants)
            ],
        },
    )
    call("POST", "/v1/reminders/sync-alerts")
    print("seeded")


main()
