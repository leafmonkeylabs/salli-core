"""The API says which withholding kinds and tax roles each pack declares, and
refuses a role the caller's own packs do not."""

from __future__ import annotations

import json

from salli.application.services.ledger_service import UnknownTaxRoleError
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26
from salli.interfaces.api.main import create_app
from tests.unit.api.conftest import AUTH, make_account


async def test_each_pack_lists_its_withholding_kinds_and_roles(client, mock_services):
    mock_services.tax.list_packs.return_value = [LK_2025_26]

    [pack] = (await client.get("/v1/tax/packs", headers=AUTH)).json()

    assert [(k["code"], k["label"]) for k in pack["withholding_kinds"]] == [
        ("apit_credit", "APIT"),
        ("ait_credit", "AIT"),
        ("foreign_tax_credit", "Foreign tax credit"),
    ]
    assert all(k["description"] for k in pack["withholding_kinds"])
    assert pack["tax_roles"] == [
        "apit_credit",
        "ait_credit",
        "foreign_tax_credit",
        "qualifying_payment",
        "fsi_income",
    ]


async def test_meta_lists_the_kinds_too(client):
    lk = (await client.get("/v1/meta")).json()["tax_packs"][0]
    assert [k["code"] for k in lk["withholding_kinds"]] == [
        "apit_credit",
        "ait_credit",
        "foreign_tax_credit",
    ]


async def test_a_role_no_pack_declares_is_refused_before_the_service(client, mock_services):
    r = await client.post(
        "/v1/accounts/",
        json={"code": "1", "name": "x", "type": "asset", "tax_role": "paye_credit"},
        headers=AUTH,
    )
    assert r.status_code == 422
    mock_services.ledger.add_account.assert_not_awaited()


async def test_a_role_the_callers_own_packs_do_not_declare_is_a_422(client, mock_services):
    mock_services.ledger.add_account.side_effect = UnknownTaxRoleError(
        "Salli has no tax pack for United Kingdom yet"
    )
    r = await client.post(
        "/v1/accounts/",
        json={"code": "4110", "name": "APIT", "type": "asset", "tax_role": "apit_credit"},
        headers=AUTH,
    )
    assert r.status_code == 422
    assert "United Kingdom" in r.json()["detail"]


async def test_an_account_reads_back_its_role(client, mock_services):
    mock_services.ledger.get_account.return_value = make_account(tax_role="fsi_income")
    r = await client.get("/v1/accounts/acc-1", headers=AUTH)
    assert r.json()["tax_role"] == "fsi_income"


def test_the_contract_lists_the_roles_the_packs_declare():
    """Generated clients keep the same enum: it is built from the packs now,
    and they declare what the old fixed list held, in its order."""
    schemas = create_app().openapi()["components"]["schemas"]
    for name in ("AddAccountRequest", "UpdateAccountRequest", "Account"):
        role = schemas[name]["properties"]["tax_role"]
        assert json.dumps(role["anyOf"][0]) == json.dumps(
            {
                "type": "string",
                "enum": [
                    "apit_credit",
                    "ait_credit",
                    "foreign_tax_credit",
                    "qualifying_payment",
                    "fsi_income",
                ],
            }
        )
