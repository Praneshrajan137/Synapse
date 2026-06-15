"""APScheduler-based job runner for SYNAPSE batch workloads (Sprint 9 §M5)."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


def _conformal_recal_bengaluru() -> int:
    from data_fabric.jobs.conformal_recal import recalibrate

    return recalibrate("bengaluru")


def _conformal_recal_mumbai() -> int:
    from data_fabric.jobs.conformal_recal import recalibrate

    return recalibrate("mumbai")


def _drift_psi() -> int:
    from data_fabric.jobs.drift_psi import run_drift_psi

    return run_drift_psi()


def _audit_archive() -> int:
    try:
        from orchestrator.audit.archiver import archive_old_rows
    except ImportError:
        logger.warning("audit_archiver_unavailable")
        return 0
    return archive_old_rows()


def _feast_compact() -> int:
    try:
        from data_fabric.jobs.feast_compact import compact_feature_views
    except ImportError:
        logger.warning("feast_compact_unavailable")
        return 0
    return compact_feature_views()


def _outcome_score() -> int:
    # Sprint 17 (ADR-046): close the outcome loop — score settled decisions
    # against realized signals and append to decision_outcomes. Runs every
    # 15 min so the Standing Watch calibration view stays fresh.
    try:
        from data_fabric.jobs.outcome_score import run_outcome_scoring
    except ImportError:
        logger.warning("outcome_score_unavailable")
        return 0
    return run_outcome_scoring()


JOBS: dict[str, tuple[str, Callable[[], int]]] = {
    "conformal_recal_bengaluru": ("0 2 * * *", _conformal_recal_bengaluru),
    "conformal_recal_mumbai": ("30 2 * * *", _conformal_recal_mumbai),
    "drift_psi": ("0 3 * * *", _drift_psi),
    "audit_archive": ("0 4 * * *", _audit_archive),
    "feast_compact": ("0 5 * * *", _feast_compact),
    "outcome_score": ("*/15 * * * *", _outcome_score),
}


def build_scheduler() -> Any:  # noqa: ANN401
    """Construct a configured ``BlockingScheduler`` with every Sprint-9 job."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError as exc:
        raise RuntimeError(
            "apscheduler is required for synapse-scheduler; install with `pip install apscheduler`"
        ) from exc

    scheduler = BlockingScheduler(timezone="UTC")
    for name, (cron, func) in JOBS.items():
        scheduler.add_job(
            func,
            trigger=CronTrigger.from_crontab(cron),
            id=name,
            name=name,
            replace_existing=True,
        )
        logger.info("scheduler_job_registered", job=name, cron=cron)
    return scheduler


def trigger(job_name: str) -> int:
    """Invoke a single job ad-hoc (for ops + CI smoke tests)."""
    if job_name not in JOBS:
        logger.error("scheduler_unknown_job", job=job_name, known=sorted(JOBS.keys()))
        return 2
    _, func = JOBS[job_name]
    logger.info("scheduler_job_triggered_manually", job=job_name)
    return int(func())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse-scheduler")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Start the blocking scheduler (long-lived)")
    p_trigger = sub.add_parser("trigger", help="Invoke a single job and exit")
    p_trigger.add_argument("job")
    sub.add_parser("list", help="List registered jobs")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.command == "list":
        for name, (cron, _) in JOBS.items():
            print(f"{name:30s} {cron}")
        return 0
    if args.command == "trigger":
        return trigger(args.job)
    if args.command == "run":
        scheduler = build_scheduler()
        try:
            scheduler.start()
        except KeyboardInterrupt:
            scheduler.shutdown(wait=False)
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
