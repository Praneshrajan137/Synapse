"""Reader for the committed twin decision-relevance policy (ADR-055; AD-13).

Feature: decision-quality-proof, task 8.2 / 9.6. Design section E2c.2.

``digital_twin/simulation/policy.yaml`` is the single committed file every calibrated twin
parameter is read from, so that **no literal lands in** ``engine.py``. This module is the
reader.

**The one rule that matters here: nothing is defaulted.** A missing key raises
:class:`PolicyUnavailableError` naming the key and the file. It does not fall back to a
"reasonable" value, and the reason is not fastidiousness -- a silent default substitutes an
unreviewed number for a committed one, and every threshold in this phase exists precisely so
that the number a run was judged against is the number somebody committed *before* the run.
A default would reintroduce, at the reader, exactly the defect the policy file removes.

This mirrors ``load_anchor_settings``, which raises ``SettingsUnavailableError`` rather than
defaulting, and it is why the deferred block in the policy file names its owing task per key
rather than shipping a placeholder: a placeholder would be judged against.
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path
from typing import Any, Final

import yaml

__all__ = [
    "POLICY_PATH",
    "MarginRule",
    "PolicyUnavailableError",
    "comparator_restock_threshold",
    "load_policy",
    "materiality_margin",
    "materiality_margin_rule",
    "negative_control_settings",
    "regret_weights",
    "require",
]

POLICY_PATH: Final[Path] = Path(__file__).resolve().parent / "policy.yaml"


class PolicyUnavailableError(Exception):
    """A committed policy value could not be read. Never substituted with a default."""


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    """Read the committed policy document, or raise naming the file."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise PolicyUnavailableError(
            f"the twin policy at {path.as_posix()} could not be read: {error}"
        ) from error
    if not isinstance(raw, dict):
        raise PolicyUnavailableError(
            f"the twin policy at {path.as_posix()} does not contain a mapping"
        )
    return raw


def require(document: dict[str, Any], dotted: str, *, path: Path = POLICY_PATH) -> Any:
    """Resolve ``dotted`` or raise naming the key and the file. **Never defaults.**"""
    node: Any = document
    walked: list[str] = []
    for segment in dotted.split("."):
        walked.append(segment)
        if not isinstance(node, dict) or segment not in node:
            raise PolicyUnavailableError(
                f"{path.as_posix()} declares no value at {'.'.join(walked)!r} (requested "
                f"{dotted!r}). This is NOT defaulted: a default would substitute an "
                "unreviewed number for a committed one, and the whole point of this file is "
                "that a run is judged against a value somebody committed before the run"
            )
        node = node[segment]
    return node


def comparator_restock_threshold(path: Path = POLICY_PATH) -> float:
    """The restock threshold the uplift comparator runs the twin with (R5.36).

    Committed as ``0.0``, which DISABLES the twin's endogenous ``(s, S)`` restock rather
    than merely lowering it: ``set_policy`` clamps with ``max(0.0, ...)`` so ``0.0`` is
    reachable, and at ``0.0`` the engine's ``if level < safety_stock`` guard is false for
    every clamped level. Without this the harness measured a compared ``(s, S)`` policy
    stacked on top of the twin's own, biasing regret toward zero.
    """
    return float(require(load_policy(path), "comparator.restock_threshold", path=path))


def regret_weights(path: Path = POLICY_PATH) -> dict[str, float]:
    """The scalar regret objective's weights (ADR-055 D2.3, R5.33).

    Two of these are READ from ``newsvendor.py`` rather than chosen -- an 8:1
    shortage-to-holding ratio this repository already commits -- and the file records which
    are read and which are declaration-time choices.
    """
    weights = require(load_policy(path), "regret_objective.weights", path=path)
    if not isinstance(weights, dict) or not weights:
        raise PolicyUnavailableError(
            f"{path.as_posix()} declares no regret_objective.weights mapping"
        )
    return {str(name): float(value) for name, value in weights.items()}


def negative_control_settings(path: Path = POLICY_PATH) -> tuple[int, float]:
    """``(independent_seed_sets, max_proven_gain_rate)`` for R6.15.

    Both are pre-registered design parameters declared in ADR-055 D6, not measurements.
    """
    document = load_policy(path)
    sets = int(require(document, "negative_control.independent_seed_sets", path=path))
    rate = float(require(document, "negative_control.max_proven_gain_rate", path=path))
    return sets, rate



# ---------------------------------------------------------------------------
# The materiality margin: rule committed before the run, value measured after
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class MarginRule:
    """The materiality margin's pre-registered derivation rule (ADR-055 D2.5).

    R5.2 forbids pinning the ``(s, S)`` materiality margin before it has been measured, while
    every other threshold in this phase is pinned *before* the run judged against it. Combined
    naively, those two rules license choosing the margin with the number already in hand --
    which decides task 11's verdict by the choice of margin.

    So the halves are separated. This rule is committed **before** checkpoint A; only the
    magnitude is instantiated from checkpoint A's run. That is the shape of a minimum
    detectable effect: pre-registered rule, measured value.
    """

    form: str
    service_points: float
    points_to_fraction: float
    weight_term: str
    weight: float
    must_be_below_measured_headroom: bool

    @property
    def derived(self) -> float:
        """The margin the rule produces. One service point costs ``weight * 0.01``."""
        return self.service_points * self.points_to_fraction * self.weight

    def describe(self) -> str:
        """ASCII one-liner naming every input, so a report never states a bare number."""
        return (
            f"{self.service_points:g} service point(s) x {self.points_to_fraction:g} x "
            f"weight({self.weight_term})={self.weight:g} = {self.derived:.6g}"
        )


def materiality_margin_rule(path: Path = POLICY_PATH) -> MarginRule:
    """Read the pre-registered derivation rule, or raise naming what is missing.

    The rule is **required**, unlike the value: a run that cannot state how its margin would
    be derived has not pre-registered anything, and R5.2's deferral is a licence to measure the
    magnitude later, not a licence to decide the criterion later.
    """
    document = load_policy(path)
    base = "regret_objective.materiality_margin"
    rule = require(document, f"{base}.derivation", path=path)
    if not isinstance(rule, dict):
        raise PolicyUnavailableError(
            f"{path.as_posix()} declares {base}.derivation but it is not a mapping"
        )

    form = str(require(document, f"{base}.derivation.form", path=path))
    if form != "service_point_equivalent":
        raise PolicyUnavailableError(
            f"unrecognised materiality-margin form {form!r}; this reader implements only "
            "'service_point_equivalent' (ADR-055 D2.5) and will not guess at another"
        )

    points = float(require(document, f"{base}.derivation.service_points", path=path))
    fraction = float(require(document, f"{base}.derivation.points_to_fraction", path=path))
    term = str(require(document, f"{base}.derivation.weight_term", path=path))
    weight = float(require(document, f"regret_objective.weights.{term}", path=path))

    if points <= 0.0 or fraction <= 0.0 or weight <= 0.0:
        raise PolicyUnavailableError(
            f"the materiality-margin rule must have strictly positive inputs, got "
            f"service_points={points!r}, points_to_fraction={fraction!r}, "
            f"weight({term})={weight!r}. A zero or negative margin makes every measured regret "
            "material and task 11 could never proceed"
        )

    return MarginRule(
        form=form,
        service_points=points,
        points_to_fraction=fraction,
        weight_term=term,
        weight=weight,
        must_be_below_measured_headroom=bool(
            require(document, f"{base}.must_be_below_measured_headroom", path=path)
        ),
    )


def materiality_margin(
    path: Path = POLICY_PATH, *, measured_headroom: float | None = None
) -> float | None:
    """The committed margin, or ``None`` while R5.2's deferral is still in force.

    ``None`` is an honest state, not a failure: ``classify_regret`` maps it to ``unavailable``,
    which is what the first measuring run must report. A placeholder would be judged against.

    **A present value is re-derived from the rule, never trusted.** If the committed number is
    not the one the rule produces, this raises rather than recording it -- otherwise the
    pre-registration is decoration and the margin could still be chosen to suit the number it
    judges.

    Args:
        path: Policy file to read.
        measured_headroom: The comparator's measured headroom, when known. Supplying it enables
            the derivable guard: a margin at or above the total headroom is unfalsifiable by
            construction, because no policy could exceed it, so ``material`` would be
            unreachable and task 11 could only ever proceed.

    Raises:
        PolicyUnavailableError: If the rule is absent, if a committed value disagrees with the
            rule, or if a committed value is not below a supplied measured headroom.
    """
    rule = materiality_margin_rule(path)
    document = load_policy(path)
    committed = require(document, "regret_objective.materiality_margin.value", path=path)

    if committed is None:
        return None

    value = float(committed)
    if not math.isclose(value, rule.derived, rel_tol=1e-9, abs_tol=1e-12):
        raise PolicyUnavailableError(
            f"the committed materiality margin {value!r} is not the value its own rule "
            f"produces ({rule.describe()}). The rule was pre-registered before the run that "
            "instantiates the value precisely so the margin could not be chosen to suit the "
            "number it judges; a value that disagrees with it is refused, not recorded. "
            "Either correct the value or amend the rule in ADR-055 D2.5 BEFORE the next run"
        )

    guard_applies = rule.must_be_below_measured_headroom and measured_headroom is not None
    if guard_applies and not value < float(measured_headroom or 0.0):
        raise PolicyUnavailableError(
            f"the committed materiality margin {value:.6g} is not below the measured "
            f"comparator headroom {float(measured_headroom or 0.0):.6g}. Such a margin is "
            "unfalsifiable by construction: no policy could exceed it, so `material` is "
            "unreachable and task 11 could only ever proceed (ADR-055 D2.5)"
        )

    return value
