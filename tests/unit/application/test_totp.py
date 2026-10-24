"""Authenticator codes (application/totp.py) against RFC 6238's test vectors."""

from __future__ import annotations

import base64
from urllib.parse import parse_qs, urlparse

import pytest

from salli.application import totp

#: RFC 6238, appendix B: the SHA-1 seed is the ASCII "12345678901234567890".
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(
    ("unix", "code"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_the_rfc_6238_sha1_vectors(unix, code):
    assert totp.code_at(RFC_SECRET, totp.step_of(unix), digits=8) == code
    # Six digits are the same number's last six.
    assert totp.code_at(RFC_SECRET, totp.step_of(unix)) == code[-6:]


def test_a_code_counts_one_step_either_side_of_now_and_no_further():
    now = 1111111111
    step = totp.step_of(now)
    for offset in (-1, 0, 1):
        code = totp.code_at(RFC_SECRET, step + offset)
        assert totp.matching_step(RFC_SECRET, code, now) == step + offset
    for offset in (-2, 2):
        assert totp.matching_step(RFC_SECRET, totp.code_at(RFC_SECRET, step + offset), now) is None
    assert totp.matching_step(RFC_SECRET, "12345", now) is None
    assert totp.matching_step(RFC_SECRET, "abcdef", now) is None


def test_a_new_secret_is_160_bits_of_base32():
    secret = totp.new_secret()
    assert len(base64.b32decode(secret + "=" * (-len(secret) % 8))) == 20
    assert secret != totp.new_secret()


def test_the_uri_is_what_an_authenticator_app_reads():
    uri = urlparse(totp.provisioning_uri("JBSWY3DPEHPK3PXP", "ada@example.org"))
    assert (uri.scheme, uri.netloc, uri.path) == ("otpauth", "totp", "/Salli%3Aada%40example.org")
    assert parse_qs(uri.query) == {
        "secret": ["JBSWY3DPEHPK3PXP"],
        "issuer": ["Salli"],
        "algorithm": ["SHA1"],
        "digits": ["6"],
        "period": ["30"],
    }


def test_recovery_codes_are_ten_different_and_match_however_typed():
    codes = totp.new_recovery_codes()
    assert len(set(codes)) == 10 and all(len(c) == 11 and c[5] == "-" for c in codes)
    code = codes[0]
    assert totp.recovery_hash(code) == totp.recovery_hash(f" {code.upper().replace('-', '')} ")
    assert totp.recovery_hash(code) != totp.recovery_hash(codes[1])
