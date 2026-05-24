"""SYNAPSE data-fabric scheduler (Sprint 9 §M5).

Wires APScheduler `BlockingScheduler` to the Sprint-8 conformal-recal
stub + Sprint-9 drift_psi + Sprint-9 audit_archive + Sprint-9
feast_compact jobs. Cron schedules:

  - ``conformal_recal``  : 02:00 UTC daily per city
  - ``drift_psi``        : 03:00 UTC daily
  - ``audit_archive``    : 04:00 UTC daily
  - ``feast_compact``    : 05:00 UTC daily

All jobs are idempotent and structured-logged. APScheduler is FOSS
(MIT). Sprint 10 deploys this as a Helm sub-chart (see ADR-034).
"""

from data_fabric.scheduler.scheduler import (
    build_scheduler,
    main,
    trigger,
)

__all__ = ["build_scheduler", "main", "trigger"]
