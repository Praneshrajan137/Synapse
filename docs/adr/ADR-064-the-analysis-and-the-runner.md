# ADR-064: The confirmatory analysis and its runner: one attempt, logged before it is opened

## Status

Accepted (truth program session 6, stages D1 and D2). It implements PREREG-1 sections 5 to 7 for
the release's confirmatory run: the seeds, the arms, the replicates per cell, the analysis, and the
rule that an execution reading the beacon's signature is logged in public before its output exists.
Freeze C fixes it with the composition of ADR-063. Session 7 executes it.

## Context

PREREG-1 seals what the confirmatory run computes; the code that computes it does not exist until
now. Section 5 seals the following:

- The confirmatory round, R_C = 34714612 of drand quicknet, emitted at 2026-12-11T00:00:00Z.
- The seed of replicate `j`: the first 8 bytes of `SHA-256("synapse/prereg-1/confirm/" || sig ||
  j)`, shifted right by one bit.
- That every attempt is logged publicly before its output is opened.

Section 6 seals `n_c` from `s_c` on the 32 validation seeds. Section 7 seals the claims and their
tests: BCa intervals with 10,000 resamples and ties counted as one half; C1 as an
intersection-union test; Holm over C2's three cells and C3; the D-4(a) mark; the ablations.

The analysis was written first (stage D1, #111), before any SYNAPSE number existed on the release
world, so it could not be bent toward one.

## Decision

1. **The analysis** (`synapse_kernel/proof/analysis.py`, #111):
   - One bootstrap stream, `Generator(PCG64(s))` with `s` from the signature, cells in order N, L,
     S1, S2, S3, each cell's resample indices shared by every statistic of that cell.
   - Sequential sums, so ties are exact. A share of 0 or 1 gives the extreme bootstrap value, and
     past the pole a level of 1 (upper) or 0 (lower).
   - Holm rejects every hypothesis that clears at the current step.
   - It is checked against scipy's BCa to 1e-12, every planted fault is caught, and numpy's stream
     is pinned by a golden digest. That digest was also reproduced by numpy 2.4.6 on Linux.
2. **Power** (`scripts/confirm/power.py`): `s_c` with `n - 1` on the paired differences
   `J_SYNAPSE - J_incumbent` on the 32 validation seeds. They are run with the composition as
   committed in stage C, each replicate in a fresh child with both replays. `n_c` follows PREREG-1's
   formula. Every delta is published, with what the run could detect at `n_c`.
3. **The attempt record** (`scripts/confirm/attempt.py`). It holds a fresh nonce, the time, the
   commit and the digest of freeze C's sums. It is committed and pushed before any execution reads
   R_C's signature.
4. **The runner** (`scripts/confirm/run.py`) refuses unless the attempt's record:
   - is on `origin/main` byte for byte;
   - is not named by any results file;
   - and freeze C's checker passes, and R_C has been emitted.

   It fetches R_C from the public relays and verifies it against quicknet's key (`synapse_beacon`),
   then derives the seeds. Per world and cell it runs `n_c` replicates of:
   - the cell's incumbent;
   - SYNAPSE;
   - SYNAPSE's lane incumbent;
   - SYNAPSE without each named component (the lane rule; each trusted entry).

   Every SYNAPSE arm runs in a fresh child per replicate, with both replays. It then calls the
   frozen analysis. The work can be split into parts (cells, slices of replicates) on separate
   machines and merged. The merge refuses a part that ran other code or arms, a missing or repeated
   replicate, or a part of another attempt.
5. **The dry run** stands the D3 development seeds (k 448-647, up to 200 a cell) in for the
   confirmatory seeds and a fixed label in for the signature. It computes every statistic, with no
   attempt and no round.

## Consequences

- **One attempt per pushed record.** A crash or a repeat needs a new pushed record. Every execution
  that read the signature is therefore in the public history before its output is opened.
  PREREG-1's "first complete run is primary" can be checked against that history.
- **The confirmatory run's compute.** At `n_c` replicates a cell, four SYNAPSE arms each with a
  replay, and two worlds, it is spread over runners. The dry run measures how long it takes.
- **The analysis is frozen with numpy 2.4.4.** Another version is accepted only if the stream's
  golden digest is equal.

## Alternatives rejected

- **Writing the analysis after the first SYNAPSE numbers:** it would invite a fork toward a result.
- **One local process for the confirmatory run:** it is slower, and needs no less trust than runners
  whose every part is replayed and merged with checks.
- **Fetching the round before the attempt is pushed:** the output could then be seen before anything
  public says the attempt happened.
