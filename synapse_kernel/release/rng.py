"""Counter-based random numbers: Threefry-2x32 with 20 rounds, keyed by seed, read by counter.

Threefry is the counter-based generator of Salmon, Moraes, Dror and Shaw, "Parallel random numbers:
as easy as 1, 2, 3" (SC'11, 2011), the family JAX uses by default. A draw is the cipher of a counter
under a key, so it is a pure function of its coordinates: here the key is the replicate's seed and
the counter is (purpose, entity, slot, index). No draw can depend on which other draws were made,
in what order, or on anything a policy did (PREREG-1 section 1). Only 32-bit additions, rotations
and exclusive-ors are used, so the output is the same on every platform, in CPython and in Pyodide;
``tests/kernel/release/test_rng.py`` checks it against Random123's published answer vectors and
against the pure-Python form below.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt

__all__ = [
    "ENTITY_BITS",
    "INDEX_BITS",
    "PURPOSE_BITS",
    "SLOT_BITS",
    "Purpose",
    "threefry2x32",
    "threefry2x32_reference",
    "uniforms",
]

U32 = npt.NDArray[np.uint32]

#: Threefry-2x32's rotation constants (Random123, ``R_32x2_0_0`` to ``R_32x2_7_0``).
ROTATIONS: Final[tuple[int, ...]] = (13, 15, 26, 6, 17, 29, 16, 24)
#: Skein's key-schedule parity constant for 32-bit words (``SKEIN_KS_PARITY32``).
KS_PARITY: Final[int] = 0x1BD11BDA
ROUNDS: Final[int] = 20
_MASK: Final[int] = 0xFFFFFFFF

PURPOSE_BITS: Final[int] = 12
ENTITY_BITS: Final[int] = 20
SLOT_BITS: Final[int] = 24
INDEX_BITS: Final[int] = 8
_TWO_POW_MINUS_53: Final[float] = 2.0**-53


class Purpose:
    """The frozen purpose numbers: changing one re-draws that whole stream (a world change)."""

    DEMAND: Final[int] = 1
    DEMAND_PAIRS: Final[int] = 2
    DAY_ITEM: Final[int] = 3
    DAY_STORE: Final[int] = 4
    SURGE_DEMAND: Final[int] = 5
    SURGE_PAIRS: Final[int] = 6
    SHOCK_DURATION: Final[int] = 10
    SHOCK_ONSET: Final[int] = 11
    SHOCK_SIZE: Final[int] = 12
    SHOCK_SUPPLIER: Final[int] = 13
    SHOCK_ITEMS: Final[int] = 14


def _rotl(x: U32, r: int) -> U32:
    return (x << np.uint32(r)) | (x >> np.uint32(32 - r))


def threefry2x32(c0: U32, c1: U32, k0: int, k1: int) -> tuple[U32, U32]:
    """Threefry-2x32-20 of the counters ``(c0, c1)`` under the key ``(k0, k1)``, elementwise.

    ``c0`` and ``c1`` are uint32 arrays of one shape; unsigned 32-bit arithmetic wraps, as the
    cipher
    requires.
    """
    ks = (np.uint32(k0), np.uint32(k1), np.uint32(KS_PARITY ^ k0 ^ k1))
    # Wrapping is the cipher's arithmetic; numpy warns about it only for 0-d operands.
    with np.errstate(over="ignore"):
        x0 = np.atleast_1d(np.asarray(c0, dtype=np.uint32)) + ks[0]
        x1 = np.atleast_1d(np.asarray(c1, dtype=np.uint32)) + ks[1]
        for r in range(ROUNDS):
            x0 = x0 + x1
            x1 = _rotl(x1, ROTATIONS[r % 8])
            x1 = x1 ^ x0
            if r % 4 == 3:
                s = (r + 1) // 4
                x0 = x0 + ks[s % 3]
                x1 = x1 + ks[(s + 1) % 3] + np.uint32(s)
    return x0, x1


def threefry2x32_reference(c0: int, c1: int, k0: int, k1: int) -> tuple[int, int]:
    """The same cipher in plain Python integers: the independent form the tests compare against."""

    def rotl(x: int, r: int) -> int:
        return ((x << r) | (x >> (32 - r))) & _MASK

    ks = (k0 & _MASK, k1 & _MASK, (KS_PARITY ^ k0 ^ k1) & _MASK)
    x0 = (c0 + ks[0]) & _MASK
    x1 = (c1 + ks[1]) & _MASK
    for r in range(ROUNDS):
        x0 = (x0 + x1) & _MASK
        x1 = rotl(x1, ROTATIONS[r % 8]) ^ x0
        if r % 4 == 3:
            s = (r + 1) // 4
            x0 = (x0 + ks[s % 3]) & _MASK
            x1 = (x1 + ks[(s + 1) % 3] + s) & _MASK
    return x0, x1


def _check(name: str, values: npt.NDArray[np.int64], bits: int) -> None:
    if values.size and (int(values.min()) < 0 or int(values.max()) >= 1 << bits):
        raise ValueError(f"{name} must lie in [0, 2**{bits}); got [{values.min()}, {values.max()}]")


def uniforms(
    seed: int,
    purpose: int,
    entity: npt.ArrayLike,
    slot: npt.ArrayLike,
    index: int = 0,
) -> npt.NDArray[np.float64]:
    """Uniform draws in ``[0, 1)``, one per broadcast (entity, slot) pair, at 53-bit resolution.

    The draw at ``(seed, purpose, entity, slot, index)`` is ``Threefry(counter, key)`` with key =
    the seed's two 32-bit halves and counter = ``(purpose << 20 | entity, slot << 8 | index)``; its
    top 53 bits over ``2**53``. Exact in float64.

    Raises:
        ValueError: A coordinate outside its field (the seed must be in ``[0, 2**64)``).
    """
    if not 0 <= seed < 1 << 64:
        raise ValueError(f"seed must lie in [0, 2**64); got {seed}")
    if not 0 <= purpose < 1 << PURPOSE_BITS:
        raise ValueError(f"purpose {purpose} out of range")
    if not 0 <= index < 1 << INDEX_BITS:
        raise ValueError(f"index {index} out of range")
    ent, sl = np.broadcast_arrays(
        np.asarray(entity, dtype=np.int64), np.asarray(slot, dtype=np.int64)
    )
    _check("entity", ent, ENTITY_BITS)
    _check("slot", sl, SLOT_BITS)
    c0 = ((np.int64(purpose) << ENTITY_BITS) | ent).astype(np.uint32)
    c1 = ((sl << INDEX_BITS) | np.int64(index)).astype(np.uint32)
    x0, x1 = threefry2x32(c0, c1, seed & _MASK, (seed >> 32) & _MASK)
    top = (x0.astype(np.uint64) << np.uint64(21)) | (x1.astype(np.uint64) >> np.uint64(11))
    out: npt.NDArray[np.float64] = top.astype(np.float64) * _TWO_POW_MINUS_53
    return out
