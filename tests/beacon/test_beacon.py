"""The beacon verifier, against the standard's own vectors and a real round (truth session 3, E).

1. Hash-to-curve is checked against RFC 9380's published vectors for the exact suite quicknet uses
   (Appendix J.9.1, ``BLS12381G1_XMD:SHA-256_SSWU_RO_``; read from rfc-editor.org 2026-11-18), so
   a ``py_ecc`` built on a draft of the standard would fail here, not silently verify wrongly.
2. A real quicknet round, fetched 2026-11-18 from the public relays (three returned byte-identical
   JSON), verifies, and its randomness is the hash of its signature.
3. A flipped signature bit, the wrong round, another public key and malformed input all fail: a
   verifier that said yes to everything would pass item 2.
4. The round-time arithmetic, including the round the sealed pre-registration names.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

import synapse_beacon as beacon

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROUND = json.loads((FIXTURES / "quicknet-round-34052212.json").read_text(encoding="utf-8"))
INFO = json.loads((FIXTURES / "quicknet-info.json").read_text(encoding="utf-8"))

RFC_DST = b"QUUX-V01-CS02-with-BLS12381G1_XMD:SHA-256_SSWU_RO_"
RFC_VECTORS = {
    b"": (
        "052926add2207b76ca4fa57a8734416c8dc95e24501772c814278700eed6d1e4e8cf62d9c09db0fac349612b759e79a1",
        "08ba738453bfed09cb546dbb0783dbb3a5f1f566ed67bb6be0e8c67e2e81a4cc68ee29813bb7994998f3eae0c9c6a265",
    ),
    b"abc": (
        "03567bc5ef9c690c2ab2ecdf6a96ef1c139cc0b2f284dca0a9a7943388a49a3aee664ba5379a7655d3c68900be2f6903",
        "0b9c15f3fe6e5cf4211f346271d7b01c8f3b28be689c8429c85b67af215533311f0b8dfaaa154fa6b88176c229f2885d",
    ),
}


def _utc(*parts: int) -> int:
    return int(dt.datetime(*parts, tzinfo=dt.UTC).timestamp())


@pytest.mark.parametrize("msg", sorted(RFC_VECTORS))
def test_hash_to_g1_matches_rfc_9380_appendix_j_9_1(msg: bytes) -> None:
    from py_ecc.bls.hash_to_curve import hash_to_G1
    from py_ecc.optimized_bls12_381 import normalize

    x, y = normalize(hash_to_G1(msg, RFC_DST, hashlib.sha256))
    want_x, want_y = RFC_VECTORS[msg]
    assert f"{int(x):096x}" == want_x
    assert f"{int(y):096x}" == want_y


def test_the_fixture_is_quicknet_and_the_constants_agree() -> None:
    assert INFO["hash"] == beacon.CHAIN_HASH
    assert INFO["public_key"] == beacon.PUBLIC_KEY_HEX
    assert INFO["genesis_time"] == beacon.GENESIS_TIME
    assert INFO["period"] == beacon.PERIOD_S
    assert INFO["schemeID"] == beacon.SCHEME


def test_a_real_round_verifies_and_its_randomness_is_the_hash_of_its_signature() -> None:
    assert beacon.verify(ROUND["round"], ROUND["signature"])
    assert beacon.randomness(bytes.fromhex(ROUND["signature"])).hex() == ROUND["randomness"]


def test_a_flipped_signature_bit_fails() -> None:
    signature = bytearray.fromhex(ROUND["signature"])
    signature[-1] ^= 0x01
    assert not beacon.verify(ROUND["round"], signature.hex())


def test_the_signature_of_one_round_does_not_verify_another() -> None:
    assert not beacon.verify(ROUND["round"] + 1, ROUND["signature"])
    assert not beacon.verify(ROUND["round"] - 1, ROUND["signature"])


def test_another_public_key_fails() -> None:
    from py_ecc.bls.point_compression import compress_G2
    from py_ecc.optimized_bls12_381 import G2, multiply

    z1, z2 = compress_G2(multiply(G2, 123456789))
    other = f"{z1:096x}{z2:096x}"
    assert other != beacon.PUBLIC_KEY_HEX
    assert not beacon.verify(ROUND["round"], ROUND["signature"], other)


@pytest.mark.parametrize("signature", ["", "zz", "00" * 48, ROUND["signature"][:-2]])
def test_malformed_signatures_fail_rather_than_raise(signature: str) -> None:
    assert not beacon.verify(ROUND["round"], signature)


def test_round_time_arithmetic() -> None:
    assert beacon.emitted_at(1) == beacon.GENESIS_TIME
    assert beacon.round_at(beacon.GENESIS_TIME) == 1
    assert beacon.round_at(_utc(2026, 11, 18)) == ROUND["round"] == 34052212
    assert beacon.emitted_at(ROUND["round"]) == _utc(2026, 11, 18)
    # The confirmatory round sealed in docs/truth/sealed/PREREG-1.md.
    assert beacon.round_at(_utc(2026, 12, 11)) == 34714612
    assert beacon.emitted_at(34714612) == _utc(2026, 12, 11)
    # "At or after": half a second past an emission is the NEXT round, not the one just emitted.
    assert beacon.round_at(_utc(2026, 12, 11) + 0.5) == 34714613
    for r in (1, 2, 1000, 34052212, 34714612):
        assert beacon.round_at(beacon.emitted_at(r)) == r
