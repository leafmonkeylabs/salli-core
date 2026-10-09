import pytest

from tests.unit.api.conftest import AUTH, make_account


@pytest.mark.asyncio
async def test_list_accounts_empty(client, mock_services):
    mock_services.ledger.list_accounts.return_value = []
    r = await client.get("/accounts/", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_accounts(client, mock_services):
    mock_services.ledger.list_accounts.return_value = [make_account()]
    r = await client.get("/accounts/", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["code"] == "1000"
    assert data[0]["type"] == "asset"


@pytest.mark.asyncio
async def test_add_account(client, mock_services):
    mock_services.ledger.add_account.return_value = "new-acc-id"
    r = await client.post(
        "/accounts/",
        json={"code": "2000", "name": "Liabilities", "type": "liability"},
        headers=AUTH,
    )
    assert r.status_code == 201
    assert r.json() == {"id": "new-acc-id"}
    mock_services.ledger.add_account.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_auth_returns_4xx(client):
    r = await client.get("/accounts/")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_add_account_passes_tax_role(client, mock_services):
    """The tax engine classifies by `tax_role` alone, so it has to survive create."""
    mock_services.ledger.add_account.return_value = "new-acc-id"
    r = await client.post(
        "/accounts/",
        json={
            "code": "1010",
            "name": "APIT Receivable",
            "type": "asset",
            "tax_role": "apit_credit",
        },
        headers=AUTH,
    )
    assert r.status_code == 201
    assert mock_services.ledger.add_account.await_args.kwargs["tax_role"] == "apit_credit"


@pytest.mark.asyncio
async def test_add_account_rejects_unknown_tax_role(client, mock_services):
    r = await client.post(
        "/accounts/",
        json={"code": "1010", "name": "Nope", "type": "asset", "tax_role": "not_a_role"},
        headers=AUTH,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_without_tax_role_keeps_the_existing_one(client, mock_services):
    """A rename must not silently clear the role.

    The repository assigns `row.tax_role = tax_role` unconditionally and the
    mobile client never sends the field, so an omitted value has to fall back to
    what the account already carries. Otherwise renaming an APIT account drops
    the credit and quietly inflates the user's tax bill.
    """
    mock_services.ledger.get_account.return_value = make_account(tax_role="apit_credit")
    r = await client.patch(
        "/accounts/acc-1",
        json={"code": "1010", "name": "APIT Receivable (renamed)", "type": "asset"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert mock_services.ledger.update_account.await_args.kwargs["tax_role"] == "apit_credit"


@pytest.mark.asyncio
async def test_update_can_set_tax_role_explicitly(client, mock_services):
    mock_services.ledger.get_account.return_value = make_account(tax_role="apit_credit")
    r = await client.patch(
        "/accounts/acc-1",
        json={
            "code": "1011",
            "name": "AIT Receivable",
            "type": "asset",
            "tax_role": "ait_credit",
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    assert mock_services.ledger.update_account.await_args.kwargs["tax_role"] == "ait_credit"


@pytest.mark.asyncio
async def test_accounts_expose_tax_role(client, mock_services):
    """The client cannot preserve a role it is never told about."""
    mock_services.ledger.list_accounts.return_value = [make_account(tax_role="ait_credit")]
    r = await client.get("/accounts/", headers=AUTH)
    assert r.json()[0]["tax_role"] == "ait_credit"

    mock_services.ledger.get_account.return_value = make_account(tax_role="ait_credit")
    r = await client.get("/accounts/acc-1", headers=AUTH)
    assert r.json()["tax_role"] == "ait_credit"
