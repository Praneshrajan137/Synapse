"""The external-dataset licence register, as a typed model (R8.1, R8.2).

Feature: decision-quality-proof, task 7.1 / 7.2. Design section E4a.1.

``infrastructure/data/dataset-licences.yaml`` records, per external dataset, the six fields
R8.1 names. This module is the reader. It exists as a separate model from the gate that
reports on it (``scripts/audit/dataset_licence_truth``) for the same reason
``gate_fault_injection`` and ``sweep_budget_truth`` are separate: the thing that knows the
shape of a declaration and the thing that decides a verdict over it are different concerns,
and fusing them makes the verdict unavailable to any other caller.

**The one load-bearing decision in this module.** ``DatasetLicence.confirmed`` is *not*
read from the artifact's ``confirmation.confirmed`` flag. It is **derived** from whether
every one of the six R8.1 fields is non-null, and :meth:`DatasetLicence.flag_disagrees` is
what reports a declaration whose flag claims more than its fields support. A boolean that
can disagree with its own subject is a claim, not evidence, and this project has already
been burned by exactly that shape: ``published_checkpoint_truth.evaluate`` let an
``UNAVAILABLE`` outcome fall through to ``ok`` because a three-valued vocabulary could not
say "nothing was checked". Deriving the answer, and reporting the disagreement separately,
is the fix.

**Why every field is ``str | None`` and none has a default.** A default would make a
missing term readable as a permissive one. R8.1's "an absent field is named rather than
defaulted" is implemented as: the schema requires the key to be *present*, the model
requires it to be *declared*, and ``None`` means "not established" rather than "unrestricted".
``absent_fields`` then names them, which is what the gate reports.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

__all__ = [
    "ARTIFACT_PATH",
    "R8_1_FIELDS",
    "Confirmation",
    "DatasetLicence",
    "LicenceArtifactError",
    "LicenceRegister",
    "Redistribution",
    "artifact_digest",
    "load_licence_document",
]

#: Repository root, resolved from this file rather than a working directory, so a caller's
#: cwd cannot change which artifact is read.
_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

#: The committed register. Design section E4a.1 names this path; the model module owns the
#: default location because a consumer that has to be told where the terms live can be told
#: the wrong place.
ARTIFACT_PATH: Final[Path] = (
    _ROOT / "infrastructure" / "data" / "dataset-licences.yaml"
)


class LicenceArtifactError(Exception):
    """The licence artifact could not be read or does not satisfy the register model.

    Distinct from "the terms are unconfirmed": this is the artifact being *unreadable*,
    which is a different repair from the artifact being *incomplete*. Runtime consumers
    refuse on either, but they must not report one as the other.
    """

#: The six fields R8.1 names, in the order the requirement states them. This tuple is the
#: single source of the completeness rule: :meth:`DatasetLicence.absent_fields` iterates it
#: rather than restating the names, so adding a seventh required term is a one-line change
#: that cannot be half-applied.
R8_1_FIELDS: Final[tuple[str, ...]] = (
    "dataset_id",
    "licence_id",
    "licence_text_uri",
    "read_date",
    "permitted_use",
    "dataset_revision",
)

#: ``unknown`` and ``None`` are deliberately distinct. ``unknown`` asserts the terms were
#: read and found silent or ambiguous; ``None`` asserts they were not read. Neither is
#: ``permitted``, and collapsing them would lose the difference between an answered question
#: and an unasked one.
Redistribution = Literal[
    "permitted", "prohibited", "permitted-with-attribution", "unknown"
]


class Confirmation(BaseModel):
    """Who established the terms, and - while nobody has - what an operator must do.

    ``procedure`` is required even on a confirmed entry, so the record states *how* the
    confirmation was obtained rather than only that it was. ``blocked_on`` carries the
    reason a confirmation cannot be obtained mechanically, which is what stops a null field
    reading as a mystery rather than a task.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    confirmed: bool
    procedure: str
    confirmed_by: str | None = None
    blocked_on: str | None = None


class DatasetLicence(BaseModel):
    """One external dataset's licence terms, with completeness derived rather than trusted.

    **Every R8.1 field defaults to ``None``, and that is load-bearing.** A key that is
    *absent* and a key that is *null* are the same fact - "nobody established this term" -
    and they must produce the same verdict. Requiring the keys here would split one fact into
    two verdicts (a missing key raising a validation error -> fail, a null key reporting
    absent -> skip) decided by whichever mechanism noticed first. Completeness has exactly
    one owner: :attr:`absent_fields`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str | None = None
    licence_id: str | None = None
    licence_text_uri: str | None = None
    read_date: str | None = None
    permitted_use: str | None = None
    dataset_revision: str | None = None
    redistribution: Redistribution | None = None
    confirmation: Confirmation
    notes: tuple[str, ...] = ()

    @field_validator("read_date")
    @classmethod
    def _read_date_is_a_date(cls, value: str | None) -> str | None:
        """A present ``read_date`` must parse as ISO ``YYYY-MM-DD``. ``None`` is admitted.

        **Why this exists in addition to the schema's format checker.** The gate validates
        against the JSON Schema, but :func:`load_licence_document` deliberately does not - a
        runtime ingestion path should not import ``jsonschema`` to satisfy a check that
        already has an owner. That leaves the runtime path able to read a malformed date
        unless the model refuses it here. Two layers, two audiences, and the malformed value
        is refused on both: absent is admitted (nobody read the terms), present-and-wrong is
        not (somebody wrote that value).
        """
        if value is None:
            return None
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(
                f"read_date must be an ISO YYYY-MM-DD date or null, got {value!r}: a date "
                "nobody can parse is not a record of when the terms were read"
            ) from error
        return value

    @property
    def absent_fields(self) -> tuple[str, ...]:
        """Every R8.1 field that is ``None``, in requirement order.

        This is the whole of the completeness rule. The gate reports these by name, which is
        R8.1's "an absent field is named rather than defaulted" made mechanical.
        """
        return tuple(name for name in R8_1_FIELDS if getattr(self, name) is None)

    @property
    def confirmed(self) -> bool:
        """True only when every R8.1 field is established. **Derived, never read.**

        Deliberately ignores ``confirmation.confirmed``. See :meth:`flag_disagrees`.
        """
        return not self.absent_fields

    @property
    def redistribution_established(self) -> bool:
        """Whether the redistribution disposition was answered at all.

        Separate from :attr:`confirmed` because redistribution is task 7.1's own addition
        rather than one of R8.1's six, so it must not silently widen the R8.1 verdict.
        """
        return self.redistribution is not None

    def flag_disagrees(self) -> bool:
        """True when the declaration's own flag claims more than its fields support.

        A ``confirmed: true`` entry carrying a null R8.1 field is a **fail**, not a skip:
        the artifact is not merely incomplete, it is making a false statement about itself.
        The reverse direction - ``confirmed: false`` with every field populated - is *not* a
        disagreement worth failing on: it is the ordinary state of an operator who filled the
        fields in and has not yet flipped the flag, and treating it as a defect would punish
        the honest half of the procedure.
        """
        return self.confirmation.confirmed and bool(self.absent_fields)

    def unconfirmed_fields(self) -> tuple[str, ...]:
        """:attr:`absent_fields` under the name a refusal message wants.

        Kept as a method rather than a second property because runtime consumers call it to
        build a **work list** for an operator ("these terms are still unread"), while
        :attr:`absent_fields` is the gate's reporting vocabulary. Same values, two audiences;
        one implementation, so they cannot diverge.
        """
        return self.absent_fields


class LicenceRegister(BaseModel):
    """The whole register. ``datasets`` is non-empty by schema, and that matters.

    "No datasets declared" and "this dataset is licensed" must not share a representation,
    so an empty register is refused rather than read as vacuously satisfied - the same
    vacuity that lets a property pass over a stub returning ``[]``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int
    datasets: tuple[DatasetLicence, ...]

    def entry(self, dataset_id: str) -> DatasetLicence | None:
        """The entry for ``dataset_id``, or ``None``. Never raises on a missing entry.

        Returning ``None`` rather than raising is deliberate: "this dataset is not declared"
        is a fact a caller must be able to *report*, and a caller that has to catch an
        exception to learn it will eventually catch it too broadly.
        """
        for candidate in self.datasets:
            if candidate.dataset_id == dataset_id:
                return candidate
        return None

    #: Retained alias. ``entry`` is the name runtime consumers use.
    by_id = entry


def artifact_digest(path: Path = ARTIFACT_PATH) -> str:
    """``sha256:<hex>`` over the licence artifact's exact bytes.

    This is what makes an ingestion record's licence binding mean something. Recording only
    "the licence was confirmed" is a claim about a file that may since have been edited;
    recording the digest makes the precise terms that were in force recoverable from the
    record alone. Hashed as raw bytes, not decoded text, so a line-ending or encoding change
    is visible rather than normalised away.

    The ``sha256:`` prefix is deliberate: a bare hex string does not say which algorithm
    produced it, and a stored digest outlives the code that computed it. A reader comparing
    two digests years apart needs to know they are comparing like with like.
    """
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise LicenceArtifactError(
            f"the licence artifact at {path.as_posix()} could not be read for digesting: "
            f"{error}"
        ) from error


def load_licence_document(path: Path = ARTIFACT_PATH) -> LicenceRegister:
    """Read and validate the register, or raise :class:`LicenceArtifactError`.

    **Why this raises where the gate does not.** ``scripts/audit/dataset_licence_truth``
    reads the same artifact but must *distinguish* its failure modes to report them
    (``register-absent`` vs ``register-unparseable`` vs ``schema-invalid``), so it does its
    own reading and returns a report rather than raising. A runtime consumer has no such
    need: it either has terms it can proceed under, or it refuses. Two audiences, two
    shapes, one artifact - and neither is permitted to treat an unreadable register as a
    permissive one.

    Note this deliberately does **not** run the JSON-Schema validation the gate runs. The
    Pydantic model is `extra='forbid'` and every R8.1 field is required-but-nullable, so the
    structural guarantees a consumer depends on are enforced here; the schema is the gate's
    subject, and importing `jsonschema` into a runtime ingestion path would add a dependency
    to satisfy a check that already has an owner.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise LicenceArtifactError(
            f"the licence artifact at {path.as_posix()} could not be parsed: {error}"
        ) from error

    if raw is None:
        raise LicenceArtifactError(
            f"the licence artifact at {path.as_posix()} is empty; an empty register is not "
            "a permissive one"
        )

    try:
        return LicenceRegister.model_validate(raw)
    except ValidationError as error:
        raise LicenceArtifactError(
            f"the licence artifact at {path.as_posix()} does not satisfy the register "
            f"model: {str(error).replace(chr(10), '; ')}"
        ) from error
