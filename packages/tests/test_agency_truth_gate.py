"""The ADR-052 agency gate must report the loop as real in this repo, and its ratchet
must actually bite. Guards both the loop AND the gate from rotting."""

from __future__ import annotations

from scripts.audit.agency_truth import evaluate


def test_agentic_loop_is_real() -> None:
    probe = evaluate()
    assert probe.ok, probe.detail
    # All five structural loop invariants hold.
    assert all(c.ok for c in probe.checks), [c.name for c in probe.checks if not c.ok]
    # The vertical-slice agents are genuinely converted (real actuation).
    assert "inventory_sentinel" in probe.converted
    assert "supplier_trust" in probe.converted


def test_ratchet_actually_bites() -> None:
    # There are still stub execute()s to convert; a ceiling of 0 must FAIL (so the
    # ratchet genuinely tightens as agents convert — it is not decorative).
    assert evaluate(max_stubs=0).ok is False
