# ADR-060: A light decision kernel grows beside the legacy twin and harness, bound to them by bit-parity tests

## Status

Accepted (truth program sessions 3 and 5; the kernel landed in PR #97 on 2026-11-18, its port of
the decision core in session 5). It supersedes nothing. ADR-059 is taken by an unmerged frontend
branch, so this record is numbered 060.

## Context

The release (`docs/truth/PLAN.md` sections 4 and 5.1) runs the twin and the policies in each
visitor's browser through Pyodide, and runs the sealed confirmatory experiment natively; both must
compute the same numbers. The legacy code could not be that engine:

- **Weight.** Importing the legacy twin loads 12 third-party packages and the legacy tuned rule 19,
  through `uplift/__init__.py`, which assembles the consensus arm (truth log S3-M-09).
- **Environment.** The legacy twin's constants come from `TwinConfig`, a pydantic `BaseSettings`
  that reads `TW_*` environment variables, so a variable silently changes every legacy run while no
  sealed digest moves (finding F-33).
- **Sealed sources.** `uplift/*.py`, `digital_twin/simulation/*` and `digital_twin/config.py` are
  bound by the digests of the proof's records (`POWER_SOURCE_SET`, `BPRIME_PHYSICS_SET`); one
  edited comment voids a record (finding 122). The legacy code cannot be refactored in place.
- **The decision core.** The eight-agent consensus arm needs the whole agent stack; a browser cannot
  run it.

## Decision

1. **`synapse_kernel/` is a separate package that needs only numpy and simpy**, reads no
   environment variable, and imports nothing else from the repository. `tests/kernel/test_closure.py`
   measures this at run time in a fresh interpreter and fails on a planted `yaml` import, `uplift`
   import or `os.environ` read.
2. **Legacy mode is a mechanical port with bit parity.** `engine.py`, `world.py` and `lead_time.py`
   were ported by asserted text replacement, keeping every draw, event and line of arithmetic in its
   order; `drive.py`, `objective.py` and `policies/{tuned,base_stock}.py` reproduce E5's loop, the
   committed objective and arms E and O. `tests/kernel/test_legacy_parity.py` requires the kernel's
   cost to equal `uplift.e5_suite.production_arm_cost` as `float.hex` on E5's first twelve
   replicate seeds, on Windows and Linux.
3. **The legacy code is never edited for the kernel.** The kernel grows beside it (strangler fig and
   parallel change), so the proof's records stand.
4. **The decision core is ported as the Sentinel alone** (`policies/sentinel.py`, session 5): the
   request the consensus arm builds for the Inventory Sentinel, how the Sentinel reads it, its
   newsvendor decision and the consensus arm's translation. On E5's twelve seeds it costs exactly what
   the eight-agent arm costs, and equals the legacy pathway (request builder, A2A handler, translator)
   on every one of 288 decisions and 2,880 quantities (`tests/kernel/test_sentinel_*.py`). It accepts
   only the legacy world's observation: nothing of SYNAPSE runs on the release world before freeze W
   (`docs/truth/sealed/PREREG-1.md` section 5).
5. **CI**: `.github/workflows/kernel.yml` runs a light job (numpy, simpy, pytest, hypothesis only;
   plus ruff and `mypy --strict` on the kernel) and a parity job with the full legacy closure. The
   verdict (ADR-061) prices the Sentinel alone on every run.

## Consequences

- The browser can show SYNAPSE's measured decisions without the agent stack: the eight-agent arm and
  one newsvendor rule are the same decisions on the measured cell (truth finding F-01, measured
  exactly in session 5).
- Two code lines exist until the experiment rule of decision D-5 retires one; tests bind them, and
  any divergence is named (the verdict's `KERNEL_DIVERGED`, parity tests' first divergence).
- A change to the agents' decision must move the port in the same change, or the verdict says so.
- The kernel carries legacy idioms in legacy mode on purpose; the release's world is new code beside
  it (ADR-062), not a rewrite of the port.

## Alternatives Rejected

- **A lazy `uplift/__init__.py`**: an edit to a sealed source set, voiding the Power_Report's digest.
- **An engine without SimPy for legacy mode**: parity at risk for no gain; the release world, which
  needs no parity with the legacy, is the place for a new engine.
- **Importing legacy files by path**: pulls pydantic and YAML into the closure.
- **Porting the Sentinel by importing the agent code**: breaks the light closure the browser needs.
- **A JavaScript kernel**: a second implementation to keep equal, where Pyodide runs the same Python.
