"""
Tax roles come from tax packs.

A pack declares the withholding kinds it credits (Sri Lanka: APIT, AIT, foreign
tax), and its regimes bring their own roles (foreign service income, qualifying
payments). An account's `tax_role` must be one its owner's country's packs
declare; a user who has not said where they are taxed may use any pack's.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from salli.domain.tax.models import StarterAccount, WithholdingKind
from salli.domain.tax.packs import registry
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26
from salli.domain.tax.packs.registry import InvalidTaxPack, validate_pack

SRI_LANKAN_ROLES = (
    "apit_credit",
    "ait_credit",
    "foreign_tax_credit",
    "qualifying_payment",
    "fsi_income",
)


def test_sri_lanka_declares_the_roles_it_always_had():
    """The five roles accounts already carry keep working, in the order the
    API has always listed them."""
    assert LK_2025_26.tax_roles == SRI_LANKAN_ROLES
    assert [(k.code, k.label) for k in LK_2025_26.withholding_kinds] == [
        ("apit_credit", "APIT"),
        ("ait_credit", "AIT"),
        ("foreign_tax_credit", "Foreign tax credit"),
    ]
    assert all(k.description for k in LK_2025_26.withholding_kinds)


def test_the_roles_a_country_allows():
    assert registry.tax_roles("LK") == SRI_LANKAN_ROLES
    assert registry.tax_roles("lk") == SRI_LANKAN_ROLES
    # No pack, no roles.
    assert registry.tax_roles("US") == ()
    assert registry.tax_roles(None) == ()
    # An account's role must be its country's; with no residency, any pack's.
    assert registry.allowed_tax_roles("LK") == SRI_LANKAN_ROLES
    assert registry.allowed_tax_roles("US") == ()
    assert registry.allowed_tax_roles(None) == registry.all_tax_roles() == SRI_LANKAN_ROLES


def test_a_regime_role_comes_and_goes_with_its_regime():
    no_fsi = replace(LK_2025_26, foreign_service_income=None)
    assert "fsi_income" not in no_fsi.tax_roles
    no_relief = replace(LK_2025_26, qualifying_payment_cap=Decimal(0))
    assert "qualifying_payment" not in no_relief.tax_roles


def test_a_pack_has_no_qualifying_payment_relief_unless_it_says_so():
    """The cap used to default to Sri Lanka's LKR 75,000, which any other
    country's pack would have inherited."""
    bare = replace(
        LK_2025_26,
        qualifying_payment_cap=Decimal(0),
        qualifying_payment_fraction=Decimal(0),
        starter_accounts=(),
    )
    assert not bare.has_qualifying_payment_relief
    assert LK_2025_26.has_qualifying_payment_relief


def test_starter_accounts_come_from_the_country_s_pack():
    assert [a.code for a in registry.starter_accounts("LK")] == [
        "5900",
        "4110",
        "4410",
        "4500",
        "4510",
    ]
    assert registry.starter_accounts(None) == ()
    assert registry.starter_accounts("GB") == ()


# ── A pack is refused when its roles could not work ──────────────────────────


def test_a_kind_the_engine_cannot_credit_is_refused():
    """It would be dropped from the bill without a word."""
    paye = WithholdingKind("paye_credit", "PAYE", "Withheld by an employer.")
    with pytest.raises(InvalidTaxPack, match="does not credit"):
        validate_pack(replace(LK_2025_26, withholding_kinds=(paye,)))


def test_a_kind_declared_twice_or_malformed_is_refused():
    apit = LK_2025_26.withholding_kinds[0]
    with pytest.raises(InvalidTaxPack, match="twice"):
        validate_pack(replace(LK_2025_26, withholding_kinds=(apit, apit)))
    with pytest.raises(InvalidTaxPack, match="not a tax role code"):
        validate_pack(replace(LK_2025_26, withholding_kinds=(replace(apit, code="APIT Credit"),)))
    with pytest.raises(InvalidTaxPack, match="label and a description"):
        validate_pack(replace(LK_2025_26, withholding_kinds=(replace(apit, label=" "),)))


def test_a_starter_account_must_carry_a_role_its_pack_declares():
    stray = StarterAccount("4999", "Somewhere Else Receivable", "asset", "paye_credit")
    with pytest.raises(InvalidTaxPack, match="does not declare"):
        validate_pack(replace(LK_2025_26, starter_accounts=(stray,)))
    first = LK_2025_26.starter_accounts[0]
    with pytest.raises(InvalidTaxPack, match="used twice"):
        validate_pack(replace(LK_2025_26, starter_accounts=(first, first)))
    with pytest.raises(InvalidTaxPack, match="malformed"):
        validate_pack(replace(LK_2025_26, starter_accounts=(replace(first, type="cash"),)))


def test_relief_out_of_range_is_refused():
    with pytest.raises(InvalidTaxPack, match="relief"):
        validate_pack(replace(LK_2025_26, qualifying_payment_fraction=Decimal("1.5")))
