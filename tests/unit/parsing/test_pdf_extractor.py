"""
The PDF extractor: statements printed as tables, read like any other table
of cells, and statements printed as lines of text. The PDFs are built here,
by hand: a page of text lines needs nothing more.
"""

from __future__ import annotations

from decimal import Decimal

from salli.adapters.parsing.csv_import import Table, extract_from_tables
from salli.adapters.parsing.pdf_extractor import extract_from_pdf


def _pdf(lines: list[str]) -> bytes:
    """A one-page PDF with these lines of text on it, and no table."""
    shown = " ".join(
        "(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj T*"
        for line in lines
    )
    content = f"BT /F1 10 Tf 14 TL 40 760 Td {shown} ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        " /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    out += f"startxref\n{xref}\n%%EOF\n".encode()
    return out


def test_a_text_statement_is_read_line_by_line():
    result = extract_from_pdf(
        _pdf(
            [
                "Date Description Amount Balance",
                "01/10/2026 SALARY OCTOBER 300,000.00 Cr 450,000.00",
                "05/10/2026 ATM WITHDRAWAL 10,000.00 Dr 440,000.00",
                "13/10/2026 SUPERMARKET (2,450.50) 437,549.50",
                "20/10/2026 INTEREST 125.40 437,674.90",
            ]
        )
    )

    assert [(r.date, r.description, r.amount, r.credit_flag) for r in result.lines] == [
        ("2026-10-01", "SALARY OCTOBER", Decimal("300000.00"), True),
        ("2026-10-05", "ATM WITHDRAWAL", Decimal("10000.00"), False),
        ("2026-10-13", "SUPERMARKET", Decimal("2450.50"), False),  # bracketed: money out
        ("2026-10-20", "INTEREST", Decimal("125.40"), True),
    ]
    assert {r.source_page for r in result.lines} == {1}
    # The running balance says which way the unmarked INTEREST went.
    assert result.errors == []


def test_a_text_statement_in_us_dates_and_european_amounts():
    us = extract_from_pdf(_pdf(["10/28/2026 RENT 1,200.00 Dr", "10/01/2026 PAY 3,250.00 Cr"]))
    assert [r.date for r in us.lines] == ["2026-10-28", "2026-10-01"]
    european = extract_from_pdf(_pdf(["01.10.2026 MIETE 1.200,00 Dr 340,12"]))
    assert [r.amount for r in european.lines] == [Decimal("1200.00")]


def test_a_statement_table_as_sri_lankan_banks_print_it():
    # What pdfplumber hands over for a table: rows of cells, None where empty.
    table = Table(
        [
            ["Date", "Description", "Debit", "Credit", "Ref"],
            ["25/04/2025", "SALARY CREDIT", "", "300,000.00", "REF001"],
            ["01/05/2025", "ATM WITHDRAWAL", "10,000.00", "", "REF002"],
            ["", "", "", "", ""],
            ["not-a-date", "Mystery row", "100.00", "", ""],
        ],
        label="Page 1, row",
        page=1,
    )

    result = extract_from_tables([table], infer=False)

    assert result is not None
    assert [(r.date, r.amount, r.credit_flag, r.bank_ref) for r in result.lines] == [
        ("2025-04-25", Decimal("300000.00"), True, "REF001"),
        ("2025-05-01", Decimal("10000.00"), False, "REF002"),
    ]


def test_a_table_that_is_not_a_statement_is_passed_over():
    assert (
        extract_from_tables(
            [Table([["Item", "Qty", "Price"], ["Widget", "2", "500.00"]])], infer=False
        )
        is None
    )


def test_a_damaged_pdf_is_said_to_be():
    (error,) = extract_from_pdf(b"%PDF-1.4\nnot really a pdf").errors
    assert error.startswith("This PDF could not be read")


def test_text_amounts_in_currencies_without_two_decimals():
    # ¥12,345 Dr was read as 12.34 money in; KWD 12.345 as 12.34.
    yen = extract_from_pdf(
        _pdf(
            ["13/10/2026 KONBINI 12,345 Dr 100,000 Cr", "14/10/2026 SALARY 250,000 Cr 350,000 Cr"]
        ),
        currency="JPY",
    )
    assert [(r.amount, r.credit_flag) for r in yen.lines] == [
        (Decimal("12345"), False),
        (Decimal("250000"), True),
    ]
    dinar = extract_from_pdf(
        _pdf(["13/10/2026 FEE 12.345 Dr 987.655 Cr", "14/10/2026 PAY 100.000 Cr 1,087.655 Cr"]),
        currency="KWD",
    )
    assert [r.amount for r in dinar.lines] == [Decimal("12.345"), Decimal("100.000")]
    dollars = extract_from_pdf(_pdf(["13/10/2026 COFFEE 4.50 Dr"]), currency="USD")
    assert [(r.amount, r.credit_flag) for r in dollars.lines] == [(Decimal("4.50"), False)]


def test_balance_lines_are_not_transactions():
    result = extract_from_pdf(
        _pdf(
            [
                "13/10/2026 BALANCE B/F 166,100.00 Cr",
                "14/10/2026 GROCER 3,900.00 162,200.00",
                "31/10/2026 CLOSING BALANCE 162,200.00 Cr",
            ]
        )
    )
    # B/F set the balance, so the grocer's change in it says money out.
    assert [(r.description, r.amount, r.credit_flag) for r in result.lines] == [
        ("GROCER", Decimal("3900.00"), False)
    ]


def test_the_amount_is_the_one_before_the_balance():
    # The foreign amount in the description used to win.
    result = extract_from_pdf(
        _pdf(
            [
                "13/10/2026 OPENING BALANCE 170,000.00 Cr",
                "14/10/2026 NETFLIX USD 12.99 3,900.00 Dr 166,100.00 Cr",
            ]
        )
    )
    assert [(r.description, r.amount, r.credit_flag) for r in result.lines] == [
        ("NETFLIX USD 12.99", Decimal("3900.00"), False)
    ]


def test_lines_that_cannot_be_read_are_reported():
    result = extract_from_pdf(
        _pdf(
            [
                "13/10/2026 COFFEE 4.50 Dr",
                "14/10/2026 SOMETHING WITHOUT AN AMOUNT",
                "31/02/2026 BAD 1.00 Dr",
            ]
        )
    )
    assert [r.description for r in result.lines] == ["COFFEE"]
    assert any("has a date but no amount" in e for e in result.errors)
    assert any("'31/02/2026'" in e and "is not a date" in e for e in result.errors)


def test_a_long_run_of_spaces_is_read_quickly():
    import time

    started = time.perf_counter()
    extract_from_pdf(_pdf(["13/10/2026 A" + " " * 1600 + "B 1.00x"]))
    assert time.perf_counter() - started < 2


class _FakeTable:
    def __init__(self, rows):
        self.rows, self.bbox = rows, (0, 0, 1, 1)

    def extract(self):
        return self.rows


class _FakePage:
    def __init__(self, tables, outside_text):
        self.tables, self.outside_text = tables, outside_text

    def find_tables(self):
        return self.tables

    def outside_bbox(self, bbox):
        return self

    def extract_text(self):
        return self.outside_text


def _fake_pdf(monkeypatch, pages):
    import contextlib

    import pdfplumber

    @contextlib.contextmanager
    def fake_open(_):
        yield type("Pdf", (), {"pages": pages})()

    monkeypatch.setattr(pdfplumber, "open", fake_open)


def test_a_boxed_summary_does_not_hide_the_transactions_printed_as_text(monkeypatch):
    # A page with any table was never read as text: the summary box hid
    # every transaction, silently.
    summary = _FakeTable([["Opening balance", "1,000.00"], ["Closing balance", "995.50"]])
    _fake_pdf(monkeypatch, [_FakePage([summary], "13/10/2026 COFFEE 4.50 Dr 995.50 Cr")])
    result = extract_from_pdf(b"%PDF-")
    assert [(r.description, r.amount) for r in result.lines] == [("COFFEE", Decimal("4.50"))]
    assert any("a table could not be read" in e for e in result.errors)


def test_a_continuation_table_of_another_width_is_reported(monkeypatch):
    first = _FakeTable(
        [["Date", "Description", "Debit", "Credit"], ["13/10/2026", "Rent", "1,200.00", ""]]
    )
    wider = _FakeTable([["14/10/2026", "Pay", "", "3,000.00", "4,000.00", "x"]])
    _fake_pdf(monkeypatch, [_FakePage([first], ""), _FakePage([wider], "")])
    result = extract_from_pdf(b"%PDF-")
    assert [r.description for r in result.lines] == ["Rent"]
    assert any(e.startswith("Page 2: a table could not be read") for e in result.errors)
