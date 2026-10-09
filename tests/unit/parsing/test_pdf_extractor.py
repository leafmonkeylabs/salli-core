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
    # The one row nothing says the direction of is read as money in, and said.
    assert result.errors == [
        "Page 1: 2026-10-20 'INTEREST' has no Dr/Cr mark; read as money in, so check it"
    ]


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
