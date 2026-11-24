# ADR-061: The verdict: one command judges the decision core's safety, quality, determinism and kernel parity in about a minute

## Status

Accepted (truth program session 3, PR #96, 2026-11-18; extended in session 5 with the kernel
parity outcome). It supersedes nothing.

## Context

Before session 3, the decision core's safety was unit-tested in 18 to 46 seconds, but its decision
quality was judged only by E5, a CI job run when a person applied a label: 53 minutes plus that
person's latency (truth findings F-31, F-32). A change could pass every fast test and still make the
consensus arm's decisions worse, nondeterministic, or quietly dependent on the environment (F-33).

## Decision

`python -m scripts.verdict` (`make verdict`, CI `.github/workflows/verdict.yml`) runs at once:

- the decision core's fast test selection in two pytest process shards;
- a miniature of E5: E5's own cost function on its first twelve replicate seeds for the consensus arm
  and the tuned control, two seeds priced again in another process;
- since session 5, the kernel's port of the decision core (`synapse_kernel.policies.sentinel`, ADR-060)
  on the same seeds.

Costs are judged **exactly** (`float.hex`) against committed pins
(`infrastructure/quality/verdict-pins.json`): the proof is deterministic, so any difference is a
real change. The exit code names the outcome, most severe first: REFUSED_ENV 6 (a `TW_` variable is
set), INCOMPLETE 7, SAFETY 1, NONDETERMINISTIC 4, CONTROL_MOVED 5, WORSE 2, CHANGED 3,
KERNEL_DIVERGED 8, PASS 0. A change to the agents still reads WORSE or CHANGED; the kernel's port is
compared with the pins, so once a change is accepted by re-pinning, the port must move with it or the
verdict reads KERNEL_DIVERGED. `--repin` writes pins only from a safe, complete, deterministic run in
which the kernel's port reproduces the measured consensus.

Two process shards and two pricing processes, each importing the agent stack once (about 12 s per
process), were measured fastest: a pool handing out single replicates was slower with more workers
(truth log S3-M-22).

## Consequences

- About 45 s on the laptop on mains power, about 25 s on CI; the fault proof
  (`scripts/verdict/fault_proof.py`, record `infrastructure/quality/verdict-fault-proof.json`) shows
  every planted fault judged as expected and a clean tree passing three times.
- A change that moves any decision fails the verdict until its pins are re-written in the same pull
  request, where the diff shows the per-seed movement.
- The legacy twin's environment dependence (F-33) cannot silently move a verdict: the command refuses
  to run while a `TW_` variable is set.

## Alternatives Rejected

- **pytest-xdist**: a new dependency for what two process shards give.
- **Pins alone without a direction**: cannot say better or worse; the judge reports the sign.
- **A statistical bound alone**: misses cost-neutral behaviour changes and nondeterminism.
- **A pool of single-replicate workers**: measured slower (S3-M-22).
- **Comparing the kernel's port with the measured consensus instead of the pins**: a change to the
  agents would then read as a kernel divergence and hide WORSE or CHANGED.
- **A safety-shard test for the port**: would mislabel a divergence as SAFETY.
