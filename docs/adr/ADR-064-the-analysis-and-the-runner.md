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
4. **The runner** (`scripts/confirm/run.py`). First, before anything reads the round, it refuses
   any of the following:
   - arguments that would fail later: an attempt runs as parts and one merge of both worlds;
   - a numpy other than 2.4.4;
   - a beacon verifier that cannot verify a known past round (py_ecc missing, say);
   - a loaded module that comes from an unfrozen file under the repository, such as an added
     `scripts/__init__.py` or a root-level file shadowing the standard library.

   It also clears `sys.argv`, so no child's launch inputs carry the part's cells. Then it refuses
   unless the attempt's record:
   - is on `origin/main` byte for byte;
   - is not named by any results file, in the checkout or on `origin/main`;
   - names R_C, and the digest of the freeze C sums this checkout holds.

   Beyond the record, all of these must hold:
   - those sums are `origin/main`'s, and the checkout's commit is on `origin/main`;
   - freeze C's checker passes, run isolated (`-I`);
   - R_C has been emitted (the relays are not asked before).

   It fetches R_C from the public relays and verifies it against quicknet's key (`synapse_beacon`),
   then derives the seeds. Per world and cell it runs `n_c` replicates of:
   - the cell's incumbent;
   - SYNAPSE;
   - SYNAPSE's lane incumbent;
   - SYNAPSE without each named component (the lane rule; each trusted entry).

   Every SYNAPSE arm runs in a fresh child per replicate, with both replays. It then calls the
   frozen analysis. The work can be split into parts (cells, slices of replicates) on separate
   machines and merged. Each part records where it ran: the interpreter, numpy, the platform, and
   GitHub's run id, run attempt and job. The merge refuses:
   - a part of another attempt (its label, round or signature differs);
   - a part of another world, or holding a cell outside the five;
   - a part whose challenger code differs from the merging checkout's, whose arms differ from the
     world's, or that ran another numpy;
   - an arm whose children were launched with different specs or arguments, or outside an empty
     folder, and a part whose children saw different environments;
   - a missing or repeated replicate, or one run with another seed than the round gives it.

   It analyses both worlds before it writes anything. The results record:
   - each part's sha256 and environment;
   - every replicate's totals;
   - as description beside section 7, the per-item breakdown and each shock cell's difference in
     differences against N.
5. **The dry run** stands the D3 development seeds (k 448-647, up to 200 a cell) in for the
   confirmatory seeds and a fixed label in for the signature. It computes every statistic, with no
   attempt and no round.
6. **No run overwrites a frozen file** (`scripts/confirm/outputs.py`). After freeze C, a dry run or
   a power run is a rehearsal and writes to `docs/truth/confirm/rehearsals/`.
7. **The rehearsal** (`--rehearse`) exercises the confirmatory path's outside steps on a known past
   round: the verifier, every relay, and the git reads of `origin/main`. It never reads R_C.

## Consequences

- **An attempt is one pushed record and one workflow run on GitHub's runners.** Its parts and its
  merge are jobs of that run, so every execution that reads the signature is in the run's public
  history, and the parts and results name the run. This is the reading of PREREG-1 section 5's
  "each is logged publicly (a pushed commit)": the record is the pushed commit, and the workflow
  run is the execution it announces.
- **A part whose job fails before writing its output** may be re-run within that workflow run
  (GitHub's "re-run failed jobs"). Its run attempt number is recorded in the part. The run is
  deterministic (bit-exact replicates, a bootstrap seeded from the signature), so a re-run gives
  the same bytes and cannot select a result.
- **A run is complete when every part is written.** A merge that fails leaves no results file and is
  repeated on the same parts. The first complete run is primary. Anything else needs a new pushed
  record:
  - a new workflow run;
  - a re-run after the results exist.
- **What the code enforces, and what the procedure does.** The runner refuses an attempt whose
  results exist, in the checkout or on `origin/main`. That a crashed whole run is not re-executed
  under its record rests on two things:
  - the public run history;
  - the determinism above.
- **The parts are kept.** They are the run's raw data, and GitHub's artifacts expire. Session 7
  commits them compressed or attaches them to a release, and each part's sha256 is in the results.
- **The confirmatory run's compute.** At `n_c` replicates a cell, four SYNAPSE arms each with a
  replay, and two worlds, it is spread over runners. The dry run measures how long it takes.
- **numpy is exactly 2.4.4** (PREREG-1 section 5 fixes "the numpy version"). The gate's reading
  allowed any version whose bootstrap stream digest is equal. The attack on freeze C showed the
  analysis also does float work that the digest does not cover, so the runner and the merge refuse
  any other version. The stream digest is still checked.
- **The analysis is the same bits on every platform.** The gate fixed Phi from
  `statistics.NormalDist`, but its bits follow the platform's libm and the Python version. Merges of
  the same parts on Windows and on Linux differed in a few BCa endpoints' last bits, with no verdict
  moved. Phi and its inverse are now computed in decimal arithmetic, correctly rounded
  (`analysis.phi`, `analysis.phi_inverse`; truth session 6, S6-D-14). Merges of the same 100 parts
  on Windows and on a Linux runner now give a byte-identical analysis. Φ's golden digest is
  reproduced under Pyodide too, so the map can be recomputed in a browser to the bit.

## Alternatives rejected

- **Writing the analysis after the first SYNAPSE numbers:** it would invite a fork toward a result.
- **One local process for the confirmatory run:** it is slower, and needs no less trust than runners
  whose every part is replayed and merged with checks.
- **Fetching the round before the attempt is pushed:** the output could then be seen before anything
  public says the attempt happened.
