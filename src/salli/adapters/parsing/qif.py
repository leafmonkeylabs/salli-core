"""
QIF statements (Quicken Interchange Format).

QIF is old and loose, but many banks still offer it beside CSV. A file is a
run of sections, each opened by a "!Type:" line, holding records of
one-letter fields that end with "^": D date, T (or U) amount, P payee, M memo,
N number, and others not needed here (categories, splits, addresses). Bank,
card and cash registers are read; investment and other-account registers, and
the account and category lists, are not.

QIF names no currency, so its rows are in the currency the caller gives. Its
dates are ambiguous (10/01/2026, 10/1'26, 1.10.2026), so their order is
decided from the whole file at once (see dates.py), and so is the decimal mark.
"""

from __future__ import annotations

from collections import Counter

from salli.adapters.parsing.amounts import detect_decimal_separator, parse_decimal
from salli.adapters.parsing.dates import DateOrder, detect_date_order, parse_date
from salli.adapters.parsing.support import Extraction, StatementLine, decode_text, join_description

_REGISTERS = {"bank", "ccard", "cash"}

# What an "!Account" record's T says the account is.
_ACCOUNT_KINDS = {
    "bank": "bank account",
    "ccard": "credit card",
    "cash": "cash",
    "invst": "investment account",
    "oth a": "other asset",
    "oth l": "other liability",
}

# Registers that hold money but are not read. Saying so means a file that
# imports nothing, or less than expected, is not a mystery.
_UNREAD_REGISTERS = {"invst": "investment", "oth a": "other asset", "oth l": "other liability"}


def extract_from_qif(
    data: bytes, *, date_order: DateOrder | None = None, prefer_order: DateOrder = "DMY"
) -> Extraction:
    """Every transaction in a QIF file's bank, card and cash registers, each
    with the account its register is for (an "!Account" record names it).

    `date_order` overrides the order detected from the file's dates;
    `prefer_order` is taken when they read either way.
    """
    result = Extraction()
    records: list[tuple[int, dict[str, str], str]] = []  # (line it starts on, fields, account)
    unread: Counter[str] = Counter()
    section: str | None = None
    fields: dict[str, str] = {}
    start = 0
    account = ""  # the account the registers that follow are for

    def close(fields: dict[str, str]) -> None:
        nonlocal account
        if section == "account" and fields.get("N"):
            # An account record: the registers after it are its.
            account = fields["N"]
            kind = _ACCOUNT_KINDS.get(fields.get("T", "").strip().lower(), "")
            if kind:
                result.account_kinds[account] = kind
        elif fields and section in _REGISTERS:
            records.append((start, fields, account))
        elif fields and section in _UNREAD_REGISTERS:
            unread[section] += 1

    for number, raw in enumerate(decode_text(data).splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("!"):
            header = line[1:].strip().lower()
            if header.startswith("type:"):
                section = header[5:].strip()
            elif header.startswith("account"):
                section = "account"  # account records: which account follows
            elif not header.startswith(("option:", "clear:")):
                section = header
            fields = {}
        elif line.startswith("^"):
            close(fields)
            fields = {}
        else:
            if not fields:
                start = number
            # The first of each field counts. Splits repeat S, E and $, but
            # never the date, amount, payee, memo or number.
            fields.setdefault(line[0], line[1:].strip())
    close(fields)  # a last record without its "^"
    # The accounts the file holds transactions for (an AutoSwitch list names
    # every account Quicken has, used or not).
    result.accounts = list(dict.fromkeys(a for _, _, a in records if a))
    result.account_kinds = {a: k for a, k in result.account_kinds.items() if a in result.accounts}

    for kind, count in unread.items():
        result.errors.append(
            f"Skipped {count} record(s) in the {_UNREAD_REGISTERS[kind]} register: "
            "only bank, card and cash registers are imported"
        )

    def amount_text(record: dict[str, str]) -> str:
        return record.get("T") or record.get("U") or ""

    mark = detect_decimal_separator(amount_text(f) for _, f, _ in records) or "."
    if date_order is None:
        date_order, notice = detect_date_order(
            (f.get("D", "") for _, f, _ in records), prefer=prefer_order
        )
        if notice:
            result.errors.append(notice)

    for first_line, record, on in records:
        label = f"QIF record at line {first_line}"
        date = parse_date(record.get("D", ""), date_order)
        if date is None:
            result.errors.append(f"{label}: {record.get('D', '')!r} is not a date; skipped")
            continue
        try:
            amount = parse_decimal(amount_text(record), mark)
        except ValueError:
            result.errors.append(f"{label}: {amount_text(record)!r} is not an amount; skipped")
            continue
        if amount == 0:
            continue
        result.lines.append(
            StatementLine(
                date=date,
                description=join_description(record.get("P", ""), record.get("M", "")),
                amount=abs(amount),
                credit_flag=amount > 0,
                # N is a cheque number, or a word Quicken uses in its place
                # (ATM, DEP, EFT): something the user wrote, never the bank's
                # id for the transaction.
                bank_ref=record.get("N", ""),
                ref_kind="text",
                account=on,
            )
        )
    return result
