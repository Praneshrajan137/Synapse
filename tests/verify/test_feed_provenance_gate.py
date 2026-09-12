"""Teeth for the feed-provenance gate (audit R4.8, task 10.11).

A gate that cannot fail is documentation. These tests drive
``scripts/audit/feed_provenance.py``'s classifier at its pure seam (``classify`` over a
parsed class) and prove the three things R4.8 actually asks for:

1. An unconditionally empty ``poll_arrivals`` is classified ``STUB`` **regardless of what the
   class is called or what it declares** - the pre-task-10.11 ``ExternalFeedSource`` is the
   worked example.
2. A body that both reads a feed and draws from a generator is a violation, because that is
   the seeded fallback R4.5 forbids.
3. ``externally_driven`` stays false without recorded decision provenance, so CI cannot
   report the loop as externally driven on the strength of a shipped class.

Plus one check against the real tree: the shipped sources classify cleanly.
"""

from __future__ import annotations

import ast
import textwrap

from scripts.audit.feed_provenance import (
    EXTERNAL,
    SEEDED,
    STUB,
    UNCLASSIFIED,
    SourceReport,
    classify,
    collect,
    external_implementation_present,
    externally_driven,
)


def _classdef(src: str) -> ast.ClassDef:
    node = ast.parse(textwrap.dedent(src)).body[0]
    assert isinstance(node, ast.ClassDef)
    return node


def _kinds(report: SourceReport) -> set[str]:
    return {v.kind for v in report.violations}


STUB_FEED = """
    class ExternalFeedSource:
        def provenance(self):
            return SourceProvenance.EXTERNAL

        def poll_arrivals(self, now_sim_min, horizon_min):
            logger.info("external_feed_not_wired")
            return []
"""

SEEDED_SOURCE = """
    class SimWorldSource:
        def provenance(self):
            return SourceProvenance.SEEDED

        def poll_arrivals(self, now_sim_min, horizon_min):
            events = [self._rng.random()]
            return events
"""

REAL_FEED = """
    class RealFeed:
        def provenance(self):
            return SourceProvenance.EXTERNAL

        def poll_arrivals(self, now_sim_min, horizon_min):
            records = self._consumer.drain(max_records=10)
            return self._to_events(records)
"""

FALLBACK_FEED = """
    class FallbackFeed:
        def provenance(self):
            return SourceProvenance.EXTERNAL

        def poll_arrivals(self, now_sim_min, horizon_min):
            try:
                return self._consumer.drain(max_records=10)
            except Exception:
                return [random.random()]
"""

UNDECLARED_FEED = """
    class Undeclared:
        def poll_arrivals(self, now_sim_min, horizon_min):
            records = self._consumer.drain()
            return records
"""


def test_unconditionally_empty_poll_is_a_stub_however_it_is_named() -> None:
    report = classify("fake.py", _classdef(STUB_FEED))
    assert report.derived == STUB
    assert report.declared == "EXTERNAL"
    assert "declaration_contradicts_body" in _kinds(report)


def test_a_seeded_generator_classifies_as_seeded_with_no_violation() -> None:
    report = classify("fake.py", _classdef(SEEDED_SOURCE))
    assert report.derived == SEEDED
    assert report.violations == []


def test_a_real_feed_classifies_as_external_with_no_violation() -> None:
    report = classify("fake.py", _classdef(REAL_FEED))
    assert report.derived == EXTERNAL
    assert report.violations == []


def test_a_seeded_fallback_inside_a_feed_is_a_violation() -> None:
    """R4.5: an unreachable feed must not advance demand from a generator."""
    report = classify("fake.py", _classdef(FALLBACK_FEED))
    assert report.derived == UNCLASSIFIED
    assert "seeded_fallback_in_feed" in _kinds(report)


def test_an_undeclared_source_is_a_violation() -> None:
    report = classify("fake.py", _classdef(UNDECLARED_FEED))
    assert "undeclared_provenance" in _kinds(report)


def test_a_stub_can_never_make_the_loop_externally_driven() -> None:
    stub = classify("fake.py", _classdef(STUB_FEED))
    assert external_implementation_present([stub]) is False
    assert externally_driven([stub], 99) is False


def test_capability_alone_is_not_evidence_the_loop_ran_on_real_data() -> None:
    real = classify("fake.py", _classdef(REAL_FEED))
    assert external_implementation_present([real]) is True
    # No recorded provenance -> not externally driven. Absence of proof is not a pass (I-7).
    assert externally_driven([real], 0) is False
    assert externally_driven([real], 1) is True


def test_the_shipped_sources_classify_cleanly() -> None:
    reports, errors = collect()
    assert errors == []
    derived = {r.class_name: r.derived for r in reports}
    assert derived.get("SimWorldSource") == SEEDED
    assert derived.get("ExternalFeedSource") == EXTERNAL
    assert [v for r in reports for v in r.violations] == []
