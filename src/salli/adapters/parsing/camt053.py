"""
ISO 20022 camt.053 statements (BankToCustomerStatement).

The XML statement European banks provide in place of MT940, and more banks
elsewhere every year. Each <Ntry> is one booking: its amount (with the
currency as an attribute), whether it is a credit or a debit, its booking
date, remittance text and the bank's reference. Versions .02 to .13 differ in
namespace and in small details (the status became <Sts><Cd>BOOK</Cd></Sts>),
so elements are matched by local name, never by a fixed namespace.

The file is untrusted. A document that declares a DTD is refused outright: a
bank statement has no use for one, and a DTD is how entity tricks (billion
laughs, external entities) get in. ElementTree resolves no external entities
in any case.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from decimal import Decimal
from typing import NoReturn
from xml.parsers import expat

from salli.adapters.parsing.support import (
    Extraction,
    RefKind,
    StatementLine,
    join_description,
    real_date,
    too_large,
)

# Statuses of entries that are not bookings yet. A statement should hold only
# booked entries, but some banks add pending ones, which would be posted a
# second time once they are booked.
_NOT_BOOKED = {"PDNG", "INFO", "FUTR"}

_AMOUNT = re.compile(r"\d+(?:\.\d+)?")
_NO_REFERENCE = {"", "NONREF", "NOTPROVIDED"}


class _Refused(Exception):
    pass


def extract_from_camt053(data: bytes) -> Extraction:
    """Every booked entry in a camt.053 document's statements."""
    try:
        _refuse_dtd(data)
        root = ET.fromstring(data)
    except _Refused as refusal:
        return Extraction(errors=[str(refusal)])
    except (ET.ParseError, expat.ExpatError) as exc:
        return Extraction(errors=[f"This is not a readable XML file: {exc}"])

    statements = root.find("{*}BkToCstmrStmt")
    if root.tag.rpartition("}")[2] != "Document" or statements is None:
        return Extraction(errors=["This XML file is not a camt.053 bank statement"])

    result = Extraction()
    for statement in statements.iterfind("{*}Stmt"):
        account_currency = (statement.findtext("{*}Acct/{*}Ccy") or "").strip() or None
        account = (
            statement.findtext("{*}Acct/{*}Id/{*}IBAN")
            or statement.findtext("{*}Acct/{*}Id/{*}Othr/{*}Id")
            or ""
        ).strip()
        if account and account not in result.accounts:
            result.accounts.append(account)
        for number, entry in enumerate(statement.iterfind("{*}Ntry"), 1):
            _add(entry, number, account_currency, account, result)
    return result


def _refuse_dtd(data: bytes) -> None:
    """Raise `_Refused` if `data` declares a DTD, before anything in it is used.

    Read with expat, the parser ElementTree itself uses, so the check sees
    the document exactly as ElementTree would, in whatever encoding it is in.
    """

    def refuse(*_: object) -> NoReturn:
        raise _Refused("This XML file declares a DTD, which a bank statement never needs; refused")

    parser = expat.ParserCreate()
    parser.StartDoctypeDeclHandler = refuse
    parser.Parse(data, True)


def _add(
    entry: ET.Element,
    number: int,
    account_currency: str | None,
    account: str,
    result: Extraction,
) -> None:
    reference, kind = _reference(entry)
    label = f"camt.053 entry {reference or number}"

    status = (entry.findtext("{*}Sts/{*}Cd") or entry.findtext("{*}Sts") or "").strip().upper()
    if status in _NOT_BOOKED:
        result.errors.append(f"{label}: not booked yet ({status}); skipped")
        return
    date = _date(entry)
    if date is None:
        result.errors.append(f"{label}: no booking or value date; skipped")
        return
    amount_element = entry.find("{*}Amt")
    amount_text = (amount_element.text or "").strip() if amount_element is not None else ""
    if amount_element is None or not _AMOUNT.fullmatch(amount_text):
        result.errors.append(f"{label}: {amount_text!r} is not an amount; skipped")
        return
    indicator = (entry.findtext("{*}CdtDbtInd") or "").strip().upper()
    if indicator not in ("CRDT", "DBIT"):
        result.errors.append(f"{label}: {indicator!r} is neither credit nor debit; skipped")
        return
    amount = Decimal(amount_text)
    if too_large(amount):
        result.errors.append(f"{label}: {amount_text!r} is not an amount; skipped")
        return
    if amount == 0:
        return

    # A reversal (<RvslInd>true</RvslInd>) needs no special handling: its
    # indicator already says which way the money moved this time.
    credit = indicator == "CRDT"
    result.lines.append(
        StatementLine(
            date=date,
            description=_description(entry, credit),
            amount=amount,
            credit_flag=credit,
            currency=(amount_element.get("Ccy") or "").strip() or account_currency,
            bank_ref=reference,
            ref_kind=kind,
            account=account,
        )
    )


def _date(entry: ET.Element) -> str | None:
    """The booking date, else the value date. A date-time is taken as the
    bank wrote it, in its own time zone, which is the day its statement shows."""
    for path in ("{*}BookgDt/{*}Dt", "{*}BookgDt/{*}DtTm", "{*}ValDt/{*}Dt", "{*}ValDt/{*}DtTm"):
        text = (entry.findtext(path) or "").strip()
        if text:
            # 9999-12-31 and the like are placeholders, no booking's date.
            match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text[:10])
            return real_date(*(int(g) for g in match.groups())) if match else None
    return None


def _description(entry: ET.Element, credit: bool) -> str:
    """Who the money came from or went to, then what it was for."""
    # The other side of the payment: whoever paid money in, or was paid. In
    # .02 the name is <Dbtr><Nm>, from .08 on it is <Dbtr><Pty><Nm>.
    party = entry.findtext(
        f"{{*}}NtryDtls/{{*}}TxDtls/{{*}}RltdPties/{{*}}{'Dbtr' if credit else 'Cdtr'}//{{*}}Nm"
    )
    remittance = " ".join(
        text.strip()
        for text in (
            element.text for element in entry.iterfind("{*}NtryDtls/{*}TxDtls/{*}RmtInf/{*}Ustrd")
        )
        if text and text.strip()
    )
    return join_description(party or "", remittance or entry.findtext("{*}AddtlNtryInf") or "")


def _reference(entry: ET.Element) -> tuple[str, RefKind]:
    """The servicing bank's own reference for the entry (an id), else the
    entry's reference within this statement (NtryRef, often just 1, 2, 3...:
    text, which identifies nothing on its own)."""
    paths: tuple[tuple[str, RefKind], ...] = (("{*}AcctSvcrRef", "id"), ("{*}NtryRef", "text"))
    for path, kind in paths:
        text = (entry.findtext(path) or "").strip()
        if text.upper() not in _NO_REFERENCE:
            return text, kind
    return "", "id"
