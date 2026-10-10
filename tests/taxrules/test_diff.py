"""What changed between two versions of a rule set, as the review shows it."""

from __future__ import annotations

from salli.domain.taxrules.diff import diff_documents
from tests.taxrules.documents import minimal


def _paths(old, new) -> dict[str, tuple[str, object, object]]:
    return {c.path: (c.kind, c.before, c.after) for c in diff_documents(old, new).changes}


def test_identical_documents_have_no_changes():
    assert diff_documents(minimal(), minimal()).changes == ()


def test_a_respelled_figure_is_not_a_change():
    new = minimal()
    new["blocks"][0]["amount"] = "5000.00"
    new["band_tables"]["main"]["bands"][0]["rate"] = "0.10"
    assert diff_documents(minimal(), new).changes == ()


def test_a_changed_figure_names_its_path_and_the_source_behind_it():
    new = minimal()
    new["blocks"][0]["amount"] = "6000"
    diff = diff_documents(minimal(), new)
    [change] = diff.changes
    assert change.path == "blocks[key=allowance].amount"
    assert (change.kind, change.before, change.after) == ("changed", "5000", "6000")
    assert change.figure is True
    assert change.source == "law"
    assert diff.sources["law"]["url"] == "https://example.org/law"


def test_a_band_rate_cites_its_table_s_source():
    new = minimal()
    new["band_tables"]["main"]["bands"][1]["rate"] = "0.25"
    [change] = diff_documents(minimal(), new).changes
    assert change.path == "band_tables.main.bands[1].rate"
    assert change.source == "law"


def test_reordering_named_items_is_not_a_change():
    new = minimal()
    new["blocks"].reverse()
    new["roles"].reverse()
    assert diff_documents(minimal(), new).changes == ()


def test_added_and_removed_items_are_reported_whole():
    new = minimal()
    removed = new["blocks"].pop(2)
    new["lines"].append({"key": "extra", "label": "Extra", "expr": "line.tax * 2"})
    changes = _paths(minimal(), new)
    assert changes["blocks[key=withholding]"] == ("removed", removed, None)
    assert changes["lines[key=extra]"][0] == "added"


def test_a_change_of_text_is_not_a_figure():
    new = minimal()
    new["lines"][0]["expr"] = "line.tax - line.withholding + 0"
    [change] = diff_documents(minimal(), new).changes
    assert change.path == "lines[key=balance].expr"
    assert change.figure is False


def test_keys_that_are_not_plain_names_are_quoted():
    old, new = minimal(), minimal()
    old["examples"][0]["expected"] = {"lines": {"allowance.remaining": "20000"}}
    new["examples"][0]["expected"] = {"lines": {"allowance.remaining": "20001"}}
    new["examples"][0]["name"] = old["examples"][0]["name"] = "Salary of 25,000"
    [change] = diff_documents(old, new).changes
    assert change.path == 'examples[name="Salary of 25,000"].expected.lines["allowance.remaining"]'
    assert change.source == "law"


def test_a_change_of_type_is_a_change():
    old, new = minimal(), minimal()
    old["examples"][0]["inputs"]["flag"] = True
    new["examples"][0]["inputs"]["flag"] = 1
    [change] = diff_documents(old, new).changes
    assert change.kind == "changed"


def test_with_nothing_before_everything_is_added():
    changes = diff_documents(None, minimal()).changes
    assert {c.kind for c in changes} == {"added"}
    assert [c.path for c in changes][:4] == ["schema", "jurisdiction", "year", "currency"]
