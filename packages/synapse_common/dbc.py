"""SYNAPSE Design-by-Contract facade — thin re-export over `deal`.

Centralizes the DbC import surface. Every module that wants
preconditions/postconditions/invariants imports from here, not from
`deal` directly. This keeps spec-coverage tooling (`scripts/check_spec_coverage.py`)
on a single grep target and makes it possible to switch the underlying library
without touching call sites.

ADR-015 (seven-layer testing) defines DbC as Layer 5. ADR-025 layers JSON-Schema
boundary validation on top.

Typical usage::

    from synapse_common.dbc import pre, post, inv

    @pre(lambda x: x >= 0)
    @post(lambda result: result >= 0)
    def sqrt_nonneg(x: float) -> float:
        return x ** 0.5
"""

from __future__ import annotations

import deal

# Re-exports preserved verbatim so call sites read like the upstream lib.
pre = deal.pre
post = deal.post
inv = deal.inv
raises = deal.raises
ensure = deal.ensure
has = deal.has
chain = deal.chain
PreContractError = deal.PreContractError
PostContractError = deal.PostContractError
InvContractError = deal.InvContractError

__all__ = [
    "deal",
    "pre",
    "post",
    "inv",
    "raises",
    "ensure",
    "has",
    "chain",
    "PreContractError",
    "PostContractError",
    "InvContractError",
]
