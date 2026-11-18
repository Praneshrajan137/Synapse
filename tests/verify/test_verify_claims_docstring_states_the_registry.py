"""``verify_claims.py``'s docstring states the registry it opens, and this file holds it there.

Feature: decision-quality-proof, task 33.2 (session 13).

The module docstring of ``scripts/audit/verify_claims.py`` said its check identifiers were
``C1..C25`` while the registry held 68 checks from C2 to C76. A range written in prose that no
gate derives drifts with every registration, and here it drifted in the file whose job is to
stop exactly that (``.kiro/steering/standard-of-work.md``). The docstring now states how many
checks are registered, the lowest and highest identifiers, and every identifier between them
that is not registered. This file derives all four from ``verify_claims._CHECKS``, the list
``register`` appends to, and fails naming each one that differs.

What would make this file wrong: a second way to register a check (``register`` is the only
code that appends to ``_CHECKS``), or a sentence this reader parses differently from how a
person reads it. A docstring without the sentence is refused, never passed, and
:func:`test_one_more_registration_fails_the_comparison` shows the comparison failing on the
real docstring.

Importing ``verify_claims`` registers its checks and runs none of them, so nothing here
executes a probe. Nothing here is a property, so no Hypothesis budget is set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import pytest

from scripts.audit import verify_claims as vc

if TYPE_CHECKING:
    from collections.abc import Sequence

#: The sentence the docstring states the registry in, matched after whitespace is folded to
#: single spaces, so a line break inside it reads as a space. Either the skipped identifiers
#: are named, or the sentence says none is skipped.
_REGISTRY_SENTENCE: Final[re.Pattern[str]] = re.compile(
    r"(?P<count>\d+) checks are registered, with identifiers from C(?P<low>\d+) to "
    r"C(?P<high>\d+); (?:(?P<skipped>(?:C\d+(?:, | and ))*C\d+) (?:is|are) not registered"
    r"|every identifier between them is registered)\."
)

#: A registered identifier: ``C`` and its number.
_CHECK_ID: Final[re.Pattern[str]] = re.compile(r"C(?P<number>\d+)")


class RegistryStatementMissingError(ValueError):
    """The docstring holds no registry sentence this reader can parse."""


@dataclass(frozen=True)
class RegistryStatement:
    """What the docstring says the registry holds."""

    count: int
    low: int
    high: int
    skipped: frozenset[int]


def stated_registry(docstring: str | None) -> RegistryStatement:
    """The registry sentence of ``docstring``, refused when it has none."""
    flat = " ".join((docstring or "").split())
    match = _REGISTRY_SENTENCE.search(flat)
    if match is None:
        raise RegistryStatementMissingError(
            "the docstring states no '<N> checks are registered, with identifiers from C<a> to "
            "C<b>; ...' sentence, so there is nothing to hold to the registry"
        )
    named = match.group("skipped") or ""
    return RegistryStatement(
        count=int(match.group("count")),
        low=int(match.group("low")),
        high=int(match.group("high")),
        skipped=frozenset(int(found.group("number")) for found in _CHECK_ID.finditer(named)),
    )


def registered_numbers(check_ids: Sequence[str]) -> tuple[int, ...]:
    """The number of each registered identifier, refused when one is not ``C<digits>``."""
    numbers: list[int] = []
    for cid in check_ids:
        match = _CHECK_ID.fullmatch(cid)
        if match is None:
            raise ValueError(f"registered identifier {cid!r} is not shaped C<digits>")
        numbers.append(int(match.group("number")))
    return tuple(numbers)


def disagreements(statement: RegistryStatement, numbers: Sequence[int]) -> list[str]:
    """Each way ``statement`` differs from the registered ``numbers``; empty when they agree."""
    registered = frozenset(numbers)
    found: list[str] = []
    if len(registered) != len(numbers):
        found.append(
            f"duplicates: the registry holds {len(numbers)} entries under {len(registered)} "
            "distinct identifiers, so a count of checks is ambiguous"
        )
    if statement.count != len(numbers):
        found.append(
            f"count: the docstring states {statement.count}, the registry holds {len(numbers)}"
        )
    if not registered:
        found.append("empty: the registry holds no check")
        return found
    low, high = min(registered), max(registered)
    if statement.low != low:
        found.append(
            f"lowest identifier: the docstring states C{statement.low}, the registry C{low}"
        )
    if statement.high != high:
        found.append(
            f"highest identifier: the docstring states C{statement.high}, the registry C{high}"
        )
    skipped = frozenset(range(low, high + 1)) - registered
    if statement.skipped != skipped:
        found.append(
            f"skipped identifiers: the docstring names {sorted(statement.skipped)}, the "
            f"registry skips {sorted(skipped)}"
        )
    return found


def _live_numbers() -> tuple[int, ...]:
    """The registered identifiers' numbers, in registration order."""
    return registered_numbers([cid for cid, _title, _fn in vc._CHECKS])


def test_the_docstring_states_the_registry_it_opens() -> None:
    found = disagreements(stated_registry(vc.__doc__), _live_numbers())
    assert found == [], (
        "scripts/audit/verify_claims.py's docstring no longer states its registry: "
        + "; ".join(found)
        + ". Move the sentence in the same commit as the registration."
    )


def test_one_more_registration_fails_the_comparison() -> None:
    """The falsifier, on the real docstring: a check registered past it, the sentence unmoved."""
    numbers = _live_numbers()
    found = disagreements(stated_registry(vc.__doc__), (*numbers, max(numbers) + 1))
    assert any(line.startswith("count:") for line in found), found
    assert any(line.startswith("highest identifier:") for line in found), found


def test_filling_a_skipped_identifier_fails_the_comparison() -> None:
    statement = RegistryStatement(count=3, low=2, high=5, skipped=frozenset({4}))
    assert disagreements(statement, (2, 3, 5)) == []
    found = disagreements(statement, (2, 3, 4, 5))
    assert any(line.startswith("count:") for line in found), found
    assert any(line.startswith("skipped identifiers:") for line in found), found


def test_a_duplicated_identifier_makes_the_count_ambiguous() -> None:
    statement = RegistryStatement(count=3, low=2, high=3, skipped=frozenset())
    found = disagreements(statement, (2, 2, 3))
    assert any(line.startswith("duplicates:") for line in found), found


def test_the_reader_parses_both_forms_of_the_sentence() -> None:
    named = stated_registry(
        "3 checks are registered, with identifiers from C2 to C6; C4 and\n   C5 are not registered."
    )
    assert named == RegistryStatement(count=3, low=2, high=6, skipped=frozenset({4, 5}))
    complete = stated_registry(
        "2 checks are registered, with identifiers from C7 to C8; every identifier between "
        "them is registered."
    )
    assert complete == RegistryStatement(count=2, low=7, high=8, skipped=frozenset())


def test_a_docstring_without_the_sentence_is_refused() -> None:
    with pytest.raises(RegistryStatementMissingError):
        stated_registry("Verify SYNAPSE claims against code reality.")
    with pytest.raises(RegistryStatementMissingError):
        stated_registry(None)


def test_an_identifier_not_shaped_like_a_check_is_refused() -> None:
    with pytest.raises(ValueError, match="not shaped C<digits>"):
        registered_numbers(["C2", "X3"])
