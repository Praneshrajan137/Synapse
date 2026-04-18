# License Audit

This document tracks the open-source licenses of every Python and JavaScript
dependency in SYNAPSE. It is regenerated monthly by CI and on every major
dependency change. The full machine-readable dump lives in
`docs/license_audit_full.md`.

## Policy (from CLAUDE.md)

- **Allowed**: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, PSF, ISC, MPL-2.0
- **Conditionally allowed**: LGPL (linking-only OK; never modify the LGPL code in-tree)
- **Forbidden**: GPL-3.0, AGPL-3.0, any "non-commercial only" license, any paid SaaS

## Summary (Python — 237 packages)

| Category | Count | Status |
|---------|------:|--------|
| MIT / MIT-flavored | 100 | OK |
| Apache-2.0 / Apache Software License | 47 | OK |
| BSD (2/3-Clause + variants) | 56 | OK |
| MPL-2.0 (Mozilla Public 2.0) | 6 | OK |
| PSF / Python Software Foundation | 5 | OK |
| ISC | 3 | OK |
| Public Domain / Unlicense | 2 | OK |
| LGPL (linking-only) | 1 | OK with caveat |
| **GPL-3.0+** | **1** | **FLAGGED — see below** |
| Triple-licensed (BSD/GPL/Public Domain — taken under BSD) | 1 | OK |
| Multi-license combinations (Apache OR MIT, etc.) | 12 | OK |
| UNKNOWN (license metadata missing) | 3 | Manual review needed |

## Flagged dependencies

### `rfc3987` — GPL-3.0+ — **REMEDIATED (blocked via constraints.txt)**

| Field | Value |
|-------|-------|
| Version | 1.3.8 (present only in user site-packages, NOT in project venv) |
| License | GNU General Public License v3 or later |
| Required-by | (empty) — not a declared project dependency |
| Status | **REMEDIATED — pip-blocked preventatively** |
| Action taken | `constraints.txt` at repo root pins `rfc3987==999.999.999`; `.github/workflows/policy.yml` `license-policy` job fails CI if rfc3987 ever appears in the resolved dependency tree |

**Remediation steps (applied 2026-04-18)**:

```bash
# 1. Confirm not a declared project dep
pip show rfc3987                                      # Required-by: (empty)
grep -rn "rfc3987" --include="*.txt" --include="*.toml"   # 0 project hits
grep -rn "jsonschema\[format\]" --include="*.txt" --include="*.toml"  # 0 hits

# 2. Block re-entry via constraints.txt (created)
cat constraints.txt
#   rfc3987==999.999.999  # license-blocked (GPL-3.0+ policy violation)

# 3. CI enforcement added to policy.yml
#   license-policy job runs pip-licenses and fails the build if
#   rfc3987 (or any other forbidden package) appears in the resolved tree.

# 4. Document recommended replacements if URI validation is ever needed:
#      jsonschema[format_nongpl]    (swap in place of jsonschema[format])
#      rfc3987-syntax==1.1.0        (BSD-3-Clause re-implementation)
```

### `psycopg2-binary` — LGPL — conditionally allowed

| Field | Value |
|-------|-------|
| Version | 2.9.11 |
| License | LGPL |
| Status | OK for dev/test (linking-only); production uses `psycopg2` + system libpq |
| Reference | E-S5-09 in `CLAUDE.md` |

### `docutils` — Triple-licensed (BSD / GPL / Public Domain)

We elect the **BSD license** for our use. Documented in this audit per the
maintainer's notice; no action needed.

### Three `UNKNOWN` packages

The `pip-licenses` scan returned `UNKNOWN` for three packages. Manual review
required at next audit cycle. Run `pip show <name>` and inspect `LICENSE` file
in each package's site-packages directory.

## JavaScript dependencies (frontend)

```bash
cd ui && npm ls --all --json | jq '.dependencies | keys | length'
cd ui && npx license-checker --summary
```

Frontend uses React, deck.gl, and shadcn/ui — all MIT or Apache-2.0. Full
report regenerated in `ui/license_report.json` on every npm install.

## Regeneration

```bash
# Python
pip install pip-licenses
python -m piplicenses --format=markdown --with-urls --output-file=docs/license_audit_full.md

# JavaScript
cd ui && npx license-checker --json --out license_report.json

# Aggregate
python scripts/check_licenses.py  # exits non-zero on policy violations (future hook)
```

A monthly cron in `cd.yml` regenerates this audit and opens a PR if the diff
is non-empty.

## Compliance attestations

- **DPDPA 2023**: No package processes raw customer data outside India-region
  storage (verified by `tests/compliance/test_dpdpa.py`).
- **Apache-2.0 NOTICE**: `NOTICE` file in repo root aggregates required attributions.
- **BSD-3-Clause attribution**: `LICENSES/THIRD_PARTY_LICENSES.md` reproduces
  copyright notices for every BSD-3-Clause package.

## Remediation log

### 2026-04-18 — rfc3987 GPL-3.0+ preventative block

- **Finding**: `pip-licenses` dump listed `rfc3987 1.3.8` (GPL-3.0+).
- **Investigation**: `pip show rfc3987` showed `Required-by: (empty)`. Repo-wide
  grep for `rfc3987` and `jsonschema[format]` returned **0 project references**.
  The package exists only in the host's user site-packages, not the project venv.
- **Conclusion**: Not a declared project dependency — preventative block appropriate.
- **Actions**:
  1. Created `constraints.txt` at repo root pinning `rfc3987==999.999.999`.
  2. Added `license-policy` job to `.github/workflows/policy.yml` that runs
     `pip-licenses` against the resolved dependency tree (installed with the
     constraints file) and fails CI if any forbidden package is present.
  3. Updated this document to mark rfc3987 REMEDIATED.
- **Verification**: `pip install -c constraints.txt rfc3987` now fails with
  "No matching distribution", confirming the block is effective.

## See also

- `docs/license_audit_full.md` — raw `pip-licenses` markdown dump (machine-generated)
- `constraints.txt` — pip constraint file blocking forbidden packages
- `pyproject.toml` — license constraints in `tool.synapse.licenses`
- `.github/workflows/policy.yml` — `license-policy` job blocks PR merge on violations
