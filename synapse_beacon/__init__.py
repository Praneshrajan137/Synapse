"""Verify drand ``quicknet`` rounds: the public randomness the release's contest and seeds use.

``quicknet`` is the League of Entropy's beacon in unchained mode (scheme
``bls-unchained-g1-rfc9380``): every 3 seconds its nodes jointly produce a threshold BLS signature
on BLS12-381, with the signature on G1 and the group public key on G2. Round ``r``'s signature
signs ``sha256(r as 8 bytes, big-endian)``, hashed to G1 by RFC 9380's
``BLS12381G1_XMD:SHA-256_SSWU_RO_`` suite under drand's domain-separation tag; its randomness is
``sha256(signature)``. Nobody can compute a round before the network emits it, and anyone can
check it with the public key below (chain information checked from the public relay 2026-11-18).

This verifier is pure Python (``py_ecc``, MIT), so it also runs in a browser under Pyodide; it is a
test-time and command-line tool, deliberately kept out of ``synapse_kernel`` so the kernel stays
numpy and simpy only. A second, independent implementation (``@noble/curves``) is used to
cross-check it (``docs/truth/sealed/CONTEST-PROTOCOL.md``).
"""

from __future__ import annotations

import hashlib
import math
from typing import Final

CHAIN_HASH: Final[str] = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
PUBLIC_KEY_HEX: Final[str] = (
    "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c"
    "8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb"
    "5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a"
)
GENESIS_TIME: Final[int] = 1692803367
PERIOD_S: Final[int] = 3
SCHEME: Final[str] = "bls-unchained-g1-rfc9380"
#: drand's domain-separation tag for G1 signatures (RFC 9380 suite, "NUL" = no augmentation).
DST: Final[bytes] = b"BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_"


def emitted_at(round_number: int) -> int:
    """The Unix time at which ``round_number`` is emitted: ``genesis + (round - 1) * period``."""
    if round_number < 1:
        raise ValueError(f"rounds start at 1, got {round_number}")
    return GENESIS_TIME + (round_number - 1) * PERIOD_S


def round_at(unix_seconds: float) -> int:
    """The first round emitted at or after ``unix_seconds`` (round 1 before genesis).

    "At or after" makes the round unknowable at ``unix_seconds``: a round chosen by this rule for
    a time in the future cannot have been seen when the time was fixed.
    """
    if unix_seconds <= GENESIS_TIME:
        return 1
    return math.ceil((unix_seconds - GENESIS_TIME) / PERIOD_S) + 1


def message(round_number: int) -> bytes:
    """What round ``round_number`` signs: ``sha256`` of the round as 8 bytes, big-endian."""
    return hashlib.sha256(round_number.to_bytes(8, "big")).digest()


def randomness(signature: bytes) -> bytes:
    """A round's randomness: ``sha256`` of its signature."""
    return hashlib.sha256(signature).digest()


def verify(round_number: int, signature_hex: str, public_key_hex: str = PUBLIC_KEY_HEX) -> bool:
    """Whether ``signature_hex`` is the beacon's signature of ``round_number``.

    Checks that both points decompress, lie in the prime-order subgroups, and satisfy
    ``e(signature, g2) == e(H(message), public_key)``. Any malformed input is ``False``.
    """
    from py_ecc.bls.hash_to_curve import hash_to_G1
    from py_ecc.bls.point_compression import decompress_G1, decompress_G2
    from py_ecc.bls.typing import G1Compressed, G2Compressed
    from py_ecc.fields import optimized_bls12_381_FQ12 as FQ12
    from py_ecc.optimized_bls12_381.optimized_curve import G2, curve_order, is_inf, multiply, neg
    from py_ecc.optimized_bls12_381.optimized_pairing import final_exponentiate, pairing

    try:
        signature = bytes.fromhex(signature_hex)
        key = bytes.fromhex(public_key_hex)
        if len(signature) != 48 or len(key) != 96:
            return False
        sig_point = decompress_G1(G1Compressed(int.from_bytes(signature, "big")))
        halves = (int.from_bytes(key[:48], "big"), int.from_bytes(key[48:], "big"))
        key_point = decompress_G2(G2Compressed(halves))
    except (ValueError, TypeError):
        return False
    if is_inf(sig_point) or is_inf(key_point):
        return False
    if not is_inf(multiply(sig_point, curve_order)) or not is_inf(multiply(key_point, curve_order)):
        return False
    # py_ecc annotates the hash argument as a hash object but calls it as a constructor, as its own
    # BLS code does with hashlib.sha256.
    hashed = hash_to_G1(message(round_number), DST, hashlib.sha256)  # type: ignore[arg-type]
    product = pairing(neg(G2), sig_point, final_exponentiate=False) * pairing(
        key_point, hashed, final_exponentiate=False
    )
    return bool(final_exponentiate(product) == FQ12.one())
