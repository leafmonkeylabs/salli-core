from salli.application.services.debt_service import _by_rate
from salli.interfaces.api.routers.debt import DebtList


def _debt(name: str, apr: str, principal: str) -> dict[str, str]:
    return {"name": name, "apr": apr, "principal": principal}


def test_debts_read_by_rate_then_balance_then_name_with_no_rate_last():
    debts = [
        _debt("Zeta loan", "0.0500", "900.00"),
        _debt("No rate", "", "5000.00"),
        _debt("Card", "0.1850", "100.00"),
        _debt("Bike", "0.0500", "900.00"),
        _debt("Car", "0.0500", "4000.00"),
    ]
    names = [d["name"] for d in sorted(debts, key=_by_rate)]
    assert names == ["Card", "Car", "Bike", "Zeta loan", "No rate"]


def test_the_debts_read_names_its_order():
    listed = DebtList(debts=[], total_balance="0.00", total_minimum_payments="0.00")
    assert listed.model_dump()["order"] == "rate_desc"
