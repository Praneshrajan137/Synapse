# CONTEST-PROTOCOL - how the public contest is committed, seeded, revealed and checked

**Written 2026-11-18, truth program session 3**, for the release's second door (`docs/truth/PLAN.md`
section 4.3; decision D-14): SYNAPSE and the incumbent run identical simulated stores for 120
simulated days, one simulated day per real hour, over five days, on randomness nobody controls,
and anyone can recompute every step. Its analysis is sealed in `PREREG-1.md` section 8.

## 1. The beacon

drand `quicknet`: chain hash `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`,
public key in `synapse_beacon.PUBLIC_KEY_HEX`, genesis 1692803367, one round every 3 seconds, scheme
`bls-unchained-g1-rfc9380`. Round `r` is emitted at `genesis + (r - 1) * 3`; `round_at(T)` is the
first round emitted at or after `T`. A round is checked by verifying its BLS signature over
`sha256(r as 8 bytes, big-endian)` against the public key; its randomness is `sha256(signature)`.

**Proven on 2026-11-18** (`tests/beacon/`): a real round (34052212, fetched from the public relays,
three of which returned byte-identical JSON) verifies with the pure-Python verifier
(`synapse_beacon`, on `py_ecc`, whose hash-to-curve matches RFC 9380's published vectors) and
independently with `@noble/curves` 1.9.7 under Node (`scripts/beacon/noble_cross_check.mjs`); a
flipped signature bit, the wrong round and another public key are each rejected by both.

## 2. Commit (at least 72 hours before launch)

Published in one commit to `main`, tagged `contest-1-commit`, so that GitHub's push records the time:

1. **The code**: the commit hash `C` of the tree that runs the contest (the kernel, the world, both
   policies, the runner), and the runner's command line.
2. **The claims and the analysis**: the SHA-256 of `PREREG-1.md` and `prereg-1.json`.
3. **The launch**: the launch time `T_L` (a whole hour, UTC) and the launch round `R_L = round_at(T_L)`.
4. **The output format**: the canonical JSON schema of one day's results.

## 3. Seed

`seed = int(SHA-256("synapse/contest-1/" || sig(R_L) || C)[:8], big) >> 1`, with `C` as its 20 raw
bytes. The code's hash is inside the seed, so code changed after `R_L` would produce a different
run: there is no "same run with a fix". Every random draw of the run comes from this seed through
the kernel's named substreams.

*Target form, if session 11 reaches it:* day `k` (0 to 119) draws from
`SHA-256("synapse/contest-1/day/" || sig(round_at(T_L + 3600 k)) || C || k)`, so even the future
is unknown to the authors as the contest runs; the rest of this protocol is unchanged.

## 4. Reveal (hourly)

At `T_L + 3600 (k + 1)` the site publishes simulated day `k`'s results for both stores (canonical JSON,
`sort_keys` and compact separators) and the chained digest
`d_k = SHA-256(d_{k-1} || day_k_json)`, with `d_{-1} = SHA-256(C)`. Interim numbers are labelled
descriptive. Nothing in the run changes during the contest: a defect found is reported, and a
corrected run may follow afterwards, labelled as a separate run.

## 5. Check (anyone, any time)

Fetch `R_L` from any relay (`api.drand.sh`, `api2.drand.sh`, `api3.drand.sh`,
`drand.cloudflare.com`), verify its signature, derive the seed, run the committed code for days
`0..k` in the browser (session 8) or natively, and compare `d_k`. A single differing digest is
evidence against the contest, and the protocol says so on the page.

## 6. Failures

- **A relay is down**: use another; every relay serves the same signed data.
- **The beacon halts**: the launch waits for `R_L`'s emission, and the delay is announced.
- **A browser cannot verify**: the native verifier and the published round JSON remain; the page
  says which check failed.

## 7. What it protects, and what it does not

**Protects** against the authors choosing favourable randomness (`R_L` is unknowable when it is
committed), and against changing the code after seeing it (`C` is committed first and mixed into
the seed). **Does not protect** against the authors withholding a bad result (but `R_L` is announced,
so silence is visible); against a flawed implementation (but it is public before launch); or against a
compromise of the beacon itself (a threshold of the League of Entropy's nodes is assumed honest).
**Fallback, recorded in advance:** if verification were impossible at launch, the seed would come
from a hash commitment `SHA-256(secret)` published with the commit and the secret revealed after day
119; this is weaker (the authors know the seed) and would be labelled as such.
