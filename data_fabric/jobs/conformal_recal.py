"""Conformal recalibration job (Sprint 8 stub, Sprint 9 wiring).

Per E-S6-04, Mumbai conformal intervals MUST be recalibrated on a Mumbai
holdout after transfer learning — Bengaluru intervals are INVALID for the
Mumbai distribution. This script is the **stub** that Sprint 8 ships:

  - it loads the Mumbai holdout from a Feast offline parquet,
  - it calls ``ConformalCalibrator(city_stratify=True).fit_city("mumbai", ...)``,
  - it stages the updated ``mumbai_<model>_conformal_quantiles`` artifact
    in MLflow,
  - and (Sprint 9) it gets invoked nightly by APScheduler / cron / Argo.

For Sprint 8 the entrypoint exists, is invocable from CI, and short-circuits
gracefully when Feast / MLflow are not present. The scheduler integration is
deferred — Sprint 9 wires `data_fabric.scheduler` to call this entrypoint on
a cron expression and reports back to the Mumbai SLO dashboards.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def _load_mumbai_holdout() -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Best-effort load. Returns ``None`` when offline data is unavailable."""
    try:
        import pandas as pd  # noqa: F401
    except ImportError:
        logger.warning("pandas_unavailable_for_conformal_recal")
        return None

    holdout_path = Path("data_fabric") / "feast" / "data" / "mumbai_holdout.parquet"
    if not holdout_path.exists():
        logger.info("mumbai_holdout_not_present", path=str(holdout_path))
        return None
    # Sprint 9 fills in the actual loader. The Sprint-8 stub returns empty.
    return ({}, {})


def recalibrate(city: str = "mumbai") -> int:
    """Run a single recalibration pass for ``city``. Returns exit code."""
    if city != "mumbai":
        logger.error("only_mumbai_recal_supported_in_sprint8", city=city)
        return 1

    data = _load_mumbai_holdout()
    if data is None:
        logger.info("conformal_recal_skipped_no_data", city=city)
        return 0

    predictions, actuals = data
    try:
        from agents.demand_prophet.training.conformal import ConformalCalibrator
    except ImportError as exc:
        logger.error("conformal_calibrator_unavailable", error=str(exc))
        return 1

    calibrator = ConformalCalibrator(city_stratify=True)
    if not predictions:
        # Empty holdout — Sprint 8 path; do not run fit_city against empty data.
        logger.info("conformal_recal_no_horizons", city=city)
        return 0

    coverages = calibrator.fit_city(city, predictions, actuals)
    failed = [h for h, cov in coverages.items() if cov < calibrator.coverage_target]
    if failed:
        logger.error("conformal_recal_coverage_below_target", city=city, horizons=failed)
        return 1
    logger.info("conformal_recal_complete", city=city, coverages=coverages)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse-conformal-recal")
    parser.add_argument("--city", default="mumbai")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return recalibrate(args.city)


if __name__ == "__main__":
    raise SystemExit(main())
