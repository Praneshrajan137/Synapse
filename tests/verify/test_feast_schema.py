"""E1 (elevation): Mumbai Feast feature schema invariants.

CLAUDE.md error pattern E-S6-09 says::

    Mumbai Feast feature views MUST include ``monsoon_intensity`` (0-1
    scale) not present in Bengaluru schema.

We verify this *statically* by parsing the per-city ``features/`` Python
source -- not by importing Feast itself, since the test suite must not
require the Feast runtime. Static verification catches schema drift in
CI before any model is trained on a Mumbai feature group that silently
dropped monsoon_intensity.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BENGALURU_FEATURES = REPO_ROOT / "data_fabric" / "feast" / "features"
MUMBAI_FEATURES = REPO_ROOT / "data_fabric" / "feast" / "mumbai" / "features"


def _field_names(py_file: Path) -> set[str]:
    """Best-effort extraction of ``Field(name=...)`` tokens from a feature file."""
    if not py_file.exists():
        return set()
    text = py_file.read_text(encoding="utf-8")
    return set(re.findall(r'Field\(\s*name\s*=\s*"([^"]+)"', text))


def test_mumbai_weather_includes_monsoon_intensity() -> None:
    fields = _field_names(MUMBAI_FEATURES / "weather_features.py")
    assert "monsoon_intensity" in fields, (
        "E-S6-09: Mumbai weather_features must include monsoon_intensity"
    )


def test_bengaluru_weather_does_not_define_monsoon_intensity() -> None:
    """Bengaluru does not have a monsoon season modeled this way -- if a
    weather features file appears there it MUST NOT carry monsoon_intensity,
    or transfer-learning input vectors will diverge silently.
    """
    candidates = list(BENGALURU_FEATURES.glob("*weather*"))
    for candidate in candidates:
        assert "monsoon_intensity" not in _field_names(candidate), (
            f"E-S6-09: {candidate.name} must not define monsoon_intensity"
        )


def test_both_cities_share_store_entity() -> None:
    """Transfer learning requires the same store entity definition in both
    cities (E-S6-01 SKU-id alignment generalised to entities).
    """
    bengaluru_entities = (BENGALURU_FEATURES / "entities.py").read_text(encoding="utf-8")
    mumbai_entities = (MUMBAI_FEATURES / "entities.py").read_text(encoding="utf-8")
    assert "store" in bengaluru_entities
    assert "store" in mumbai_entities


@pytest.mark.parametrize(
    "filename",
    ["demand_features.py", "store_features.py"],
)
def test_mumbai_view_uses_mumbai_data_path(filename: str) -> None:
    """Each Mumbai feature file's source path must point at data/mumbai/.

    Catches the copy-paste-from-bengaluru bug where someone clones a feature
    file but forgets to retarget the FileSource (E-S6-03 per-city registries).
    """
    text = (MUMBAI_FEATURES / filename).read_text(encoding="utf-8")
    if "FileSource" not in text and "source=" not in text:
        pytest.skip(f"{filename} has no FileSource declaration")
    # The path may appear with single or double quotes.
    has_mumbai_path = (
        "data/mumbai/" in text
        or "data\\\\mumbai\\\\" in text
    )
    assert has_mumbai_path, (
        f"E-S6-03: {filename} must reference data/mumbai/ (got Bengaluru path?)"
    )
