# Requirements Document

## Introduction

This feature takes the GitLab CI/CD port of the SYNAPSE monorepo from "CI-linter-valid YAML" to "verified, running, and operational," and completes the human-only setup that cannot be expressed in config. The GitLab CI configuration currently exists only in three unmerged, stacked Merge Requests (!75 → !76 → !77); none of it has ever executed. The work merges that stack with owner approval, drives every pipeline to a green (or genuinely-red-and-documented) state using evidence from real runs, performs the human-only GitLab platform setup (schedules, Docker-capable runner, protected environments and secrets), wires the real deploy flow behind manual gates, decides and documents the admission-controller posture for GitLab-signed images, and produces a GitHub↔GitLab parity-and-status report.

The GitHub Actions workflows (`.github/workflows/*`) and `infrastructure/gcp/verify_images.sh` are the parity reference and the untouched fallback. All GitLab work is confined to `.gitlab-ci.yml`, `.gitlab/ci/*`, and `infrastructure/security/verify_images_gitlab.sh`. The overriding optimization target is real working outcomes at zero incremental cost, not green YAML.

## Glossary

- **Operator**: The human engineer (or the agent acting on the engineer's behalf) performing the operationalization work, including merges, fix-forward commits, and platform setup.
- **Owner**: The repository owner whose approval is required before merging MRs and before destructive or policy-changing decisions.
- **GitLab_Project**: The GitLab.com project `praneshrajank-synapse/Synapse` (project_id 83534308) where the work is performed.
- **MR_Stack**: The three stacked Merge Requests containing the GitLab CI/CD port, in merge order !75 → !76 → !77.
- **GitLab_Pipeline**: A pipeline run produced by the GitLab CI configuration (root `.gitlab-ci.yml` plus child pipelines under `.gitlab/ci/*`) for a merge request or branch.
- **CI_Linter**: The GitLab CI configuration validation facility (the project's `/ci/lint` validation) used to confirm a configuration is syntactically and semantically valid before commit.
- **GitLab_CI_Files**: The set of files this feature is permitted to create or modify: `.gitlab-ci.yml`, any file under `.gitlab/ci/`, and `infrastructure/security/verify_images_gitlab.sh`.
- **GitHub_Fallback_Files**: The protected reference/fallback set that MUST NOT be modified: any file under `.github/workflows/` and `infrastructure/gcp/verify_images.sh`.
- **Quality_Gate**: A pipeline check that blocks merge/deploy on failure (blocking), as distinct from an advisory check.
- **Advisory_Check**: A pipeline check that surfaces findings but does not block (e.g., dependency-audit, v4-compliance, license audit marked informational).
- **Gate_Semantics**: The exact set of thresholds, blocking-vs-advisory classifications, and install-ordering behaviors carried over from the GitHub workflows.
- **Mutation_Threshold**: The mutation-survival ceilings enforced by `scripts/check_mutation_threshold.py`: rewards < 15%, guardrails < 10%, audit < 10%.
- **Coverage_Floor**: The per-package branch-coverage minimums enforced by `scripts/coverage_per_package.py` against `infrastructure/quality/coverage-floors.yaml`.
- **Spec_Coverage_Threshold**: The aggregate invariant assertion-match threshold enforced by `scripts/check_spec_coverage.py --threshold 99`.
- **Invariant_I1**: The zero-paid-API / $0-cost project invariant: no paid services may be introduced, and runner minutes are minimized via `rules:changes` and `interruptible`.
- **Keyless_Signing**: Cosign keyless image signing using a GitLab OIDC token (`SIGSTORE_ID_TOKEN`, audience `sigstore`) with no private key material.
- **Supply_Chain_Verifier**: `infrastructure/security/verify_images_gitlab.sh`, which verifies signed images against the GitLab Fulcio certificate identity.
- **Deployable_Image**: One of the 12 container images produced by the build-and-sign matrix: api-gateway, orchestrator, digital-twin, demand-prophet, routing-navigator, inventory-sentinel, freshness-guardian, pricing-oracle, disruption-shield, supplier-trust, sustainability-agent, frontend.
- **Docker_Runner**: A GitLab runner with a Docker executor and privileged mode, required by Docker-in-Docker jobs (build-and-sign, integration-e2e).
- **Pipeline_Schedule**: A GitLab scheduled pipeline configured against `main`.
- **Protected_Environment**: A GitLab deployment environment (oracle-prod, oracle-canary) gated by approval rules and protected/masked secret variables.
- **Masked_Protected_Variable**: A GitLab CI/CD variable stored via GitLab secret management, marked masked and protected, used for real deploy credentials.
- **Parity_Report**: The written GitHub-workflow → GitLab-equivalent → verified-running-status matrix plus residual-risk list.
- **ADR**: An Architecture Decision Record committed to the repository documenting a durable decision.

## Requirements

### Requirement 1: Confine all changes to GitLab CI files

**User Story:** As the Owner, I want every change scoped to the GitLab CI surface, so that the proven GitHub Actions fallback remains intact and deployable at all times.

#### Acceptance Criteria

1. WHEN a file modification is proposed, IF the target file path is one of GitLab_CI_Files, THEN THE Operator SHALL allow the change to proceed.
2. WHEN a file modification is proposed, IF the target file path is not one of GitLab_CI_Files, THEN THE Operator SHALL reject the change without altering the target file.
3. IF a proposed change would create, modify, or delete any GitHub_Fallback_Files, THEN THE Operator SHALL reject the change and produce a violation report that identifies the rejected file path and the rule violated.
4. THE Operator SHALL keep every file under `.github/workflows/` and the file `infrastructure/gcp/verify_images.sh` byte-identical (matching checksum) from the start to the completion of this feature.

### Requirement 2: Never commit secrets

**User Story:** As the Owner, I want zero secret material in the repository, so that credentials cannot leak through version control.

#### Acceptance Criteria

1. THE Operator SHALL store all real deploy credentials exclusively as Masked_Protected_Variables through GitLab secret management, with no credential value present in any committed file.
2. WHEN a CI/CD job authenticates to the GitLab Container Registry, THE GitLab_CI_Files SHALL authenticate using `$CI_JOB_TOKEN` and SHALL NOT reference any static or hardcoded registry credential.
3. THE GitLab_CI_Files SHALL perform image signing via Keyless_Signing using the GitLab OIDC token, without referencing any private key file, key variable, or key path.
4. IF a commit would introduce a hardcoded credential, token, or private key into any tracked repository file, THEN THE Operator SHALL reject the commit before it is recorded, leaving the repository unchanged.
5. WHEN the Operator rejects a commit under criterion 4, THE Operator SHALL report an error indicating the offending file and the location of the detected secret within that file.

### Requirement 3: Preserve gate semantics exactly

**User Story:** As the Owner, I want the GitLab pipelines to enforce the same quality regime as the GitHub workflows, so that the migration changes the platform but not the standards.

#### Acceptance Criteria

1. WHEN the GitLab_Pipeline evaluates Mutation_Threshold results, THE GitLab_Pipeline SHALL compare the measured mutation score against the limits of rewards below 15 percent, guardrails below 10 percent, and audit below 10 percent.
2. IF the measured rewards mutation score is at or above 15 percent, OR the measured guardrails mutation score is at or above 10 percent, OR the measured audit mutation score is at or above 10 percent, THEN THE GitLab_Pipeline SHALL fail the mutation stage and report which threshold was exceeded.
3. WHEN the GitLab_Pipeline evaluates coverage, THE GitLab_Pipeline SHALL compare measured coverage against the Coverage_Floor values defined in `infrastructure/quality/coverage-floors.yaml` without lowering any floor.
4. IF measured coverage for any module is below its Coverage_Floor value defined in `infrastructure/quality/coverage-floors.yaml`, THEN THE GitLab_Pipeline SHALL fail the coverage stage and report the module below floor.
5. WHEN the GitLab_Pipeline evaluates spec coverage via `scripts/check_spec_coverage.py`, THE GitLab_Pipeline SHALL compare the measured spec coverage against the Spec_Coverage_Threshold of 99.
6. IF the measured spec coverage reported by `scripts/check_spec_coverage.py` is below 99, THEN THE GitLab_Pipeline SHALL fail the spec coverage stage and report the measured value.
7. WHEN a check is classified as blocking as carried from the GitHub workflows, THE GitLab_Pipeline SHALL block the merge if that check fails.
8. WHERE a check is classified as advisory as carried from the GitHub workflows, THE GitLab_Pipeline SHALL allow the merge to proceed when that check fails while recording the failure result.
9. WHERE working bash logic encodes a prior incident fix, THE Operator SHALL preserve that logic verbatim, including the pathspec and starlette force-last pins, the cosign sign-by-digest-not-tag behavior, and the mutmut exit-code masking.
10. IF a proposed change would alter any Gate_Semantics value or classification, THEN THE Operator SHALL withhold the change, retain the existing Gate_Semantics value and classification unchanged, and obtain Owner approval before applying the change.

### Requirement 4: Honor the zero-cost invariant (I-1)

**User Story:** As the Owner, I want the pipelines to run at zero incremental cost, so that the project's $0 invariant is never violated.

#### Acceptance Criteria

1. THE Operator SHALL ensure that the GitLab_CI_Files and platform configuration reference only services billed at $0.00 incremental cost (free-tier or self-hosted at no marginal charge), introducing no service that incurs a positive monetary charge per pipeline run.
2. IF a proposed change to the GitLab_CI_Files or platform configuration would introduce a service that incurs a positive monetary charge, THEN THE Operator SHALL reject the change and provide an indication identifying the cost-incurring service.
3. THE GitLab_CI_Files SHALL gate every job whose runtime exceeds 60 seconds or which invokes an external build, test, or deployment step with a `rules:changes` clause, so that such jobs run only when at least one of their declared relevant paths changes.
4. THE GitLab_CI_Files SHALL set `interruptible: true` on every job that performs no irreversible external side effect (build, test, lint, or analysis jobs), so that superseded pipeline runs are cancelled and runner minutes are not consumed by stale runs.
5. WHERE a runner must be provisioned, THE Operator SHALL propose at least one runner option that incurs $0.00 incremental monetary cost (free-tier or self-hosted) and SHALL document the option's applicable usage limits.

### Requirement 5: Validate every configuration before commit

**User Story:** As the Operator, I want every configuration change linted before it lands, so that no broken config is ever committed.

#### Acceptance Criteria

1. WHEN a change to GitLab_CI_Files is prepared, THE Operator SHALL submit the changed configuration to the CI_Linter and obtain a validation result before initiating any commit.
2. IF the CI_Linter reports the configuration as invalid, THEN THE Operator SHALL withhold the commit, surface an error indication identifying the failing configuration and the reported validation errors, and retain the prepared change without modification until a subsequent validation returns a passing result.
3. IF the CI_Linter does not return a validation result within 30 seconds, or returns an error indicating it is unavailable, THEN THE Operator SHALL withhold the commit and surface an error indication that validation could not be completed.
4. WHEN the CI_Linter returns a passing validation result, THE Operator SHALL commit the change as a single atomic commit containing only the files belonging to that one validated change, such that the commit applies completely or not at all.

### Requirement 6: Merge the MR stack with owner approval

**User Story:** As the Owner, I want the three stacked MRs merged in order with my approval, so that the GitLab CI configuration lands on main in a controlled sequence.

#### Acceptance Criteria

1. THE Operator SHALL merge the MR_Stack in the strict sequence !75 first, then !76, then !77, and SHALL NOT merge any MR before all MRs earlier in the sequence have been confirmed as merged to `main`.
2. WHEN an MR in the MR_Stack is confirmed merged to `main`, THE Operator SHALL retarget the next MR in the stack to `main` and SHALL complete the retarget before initiating the merge of that next MR.
3. IF Owner approval has not been granted for a given MR, THEN THE Operator SHALL withhold the merge of that MR and SHALL leave that MR and all subsequent MRs in the stack unmerged.
4. IF a merge of any MR in the MR_Stack does not complete successfully, THEN THE Operator SHALL halt the sequence, SHALL NOT attempt to merge any subsequent MR, and SHALL surface an indication identifying the MR that failed to merge.
5. WHEN all three MRs (!75, !76, !77) are confirmed merged, THE Operator SHALL verify that every file in the GitLab_CI_Files set exists on `main`.
6. IF any file in the GitLab_CI_Files set is absent from `main` after all three MRs are merged, THEN THE Operator SHALL report a verification failure identifying each missing file.

### Requirement 7: Drive each pipeline to a verified state with real-run evidence

**User Story:** As the Operator, I want every pipeline driven to green using evidence from real runs, so that "operational" reflects actual execution rather than valid syntax.

#### Acceptance Criteria

1. THE Operator SHALL trigger both the merge-request and branch GitLab_Pipelines such that each defined job in those pipelines reaches a terminal execution status (success or failure) at least once, with no job remaining in a created, skipped, or manual-pending state.
2. WHEN a job reaches a failed terminal status, THE Operator SHALL read that job's execution log and apply a fix-forward change as a single commit that modifies only the files required to address the identified failure and that passes the CI_Linter with zero reported violations before being pushed.
3. WHEN a GitLab_Pipeline on `main` reaches a terminal status, THE Operator SHALL record the run as green only if every job in that pipeline reports a success status, and otherwise record it as not green, citing the identifier of each non-success job.
4. IF a job still reports a failed status after the Operator has read its execution log and applied at least one fix-forward attempt, THEN THE Operator SHALL document the failure as an identified code or infrastructure defect, including the failing job identifier and the observed cause from the log, rather than recording it as an unresolved configuration defect.
5. THE Operator SHALL support every risk resolution with a reference to a pipeline run that produced execution logs (a real run), and SHALL NOT close a risk based on syntax validation or dry-run results alone.

### Requirement 8: Resolve first-run install drift

**User Story:** As the Operator, I want the long, order-sensitive install sequences confirmed against a real run, so that first-run install drift is corrected with evidence.

#### Acceptance Criteria

1. WHEN the install steps of a GitLab_Pipeline run for the first time, THE Operator SHALL confirm from the job log that every other dependency install step appears before the force-last pins (pathspec and starlette), and that the pathspec and starlette install steps appear after all other package install steps.
2. WHEN the first-run install sequence completes, THE Operator SHALL record the job log reference (pipeline identifier and job identifier) as evidence that the install sequence completed with a success status and in the confirmed order.
3. IF the job log shows the force-last pins (pathspec or starlette) installed before any other dependency, THEN THE Operator SHALL apply a fix-forward that restores the force-last ordering and re-run the GitLab_Pipeline install steps to confirm the corrected order from the new job log.
4. IF the install sequence produces a version-resolution conflict, THEN THE Operator SHALL apply a fix-forward that re-establishes the force-last pin behavior (pathspec and starlette installed last) carried from the GitHub workflows and re-run the GitLab_Pipeline install steps to confirm from the job log that the conflict no longer occurs.

### Requirement 9: Confirm the frontend lockfile path

**User Story:** As the Operator, I want the frontend lockfile path confirmed, so that the frozen-lockfile install in frontend-checks does not fail.

#### Acceptance Criteria

1. THE Operator SHALL confirm that a pnpm lockfile exists at the path `frontend/pnpm-lock.yaml` that the frontend-checks job consumes when running `pnpm install --frozen-lockfile`.
2. WHEN the frontend-checks job runs `pnpm install --frozen-lockfile` against the lockfile at `frontend/pnpm-lock.yaml`, THE frontend-checks job SHALL complete the install step with a success (zero) exit status.
3. IF the lockfile is absent at `frontend/pnpm-lock.yaml`, THEN THE Operator SHALL correct either the path configured in the frontend-checks job or the lockfile location so that the lockfile resolves to the path the job consumes, and SHALL re-run the install to obtain a success (zero) exit status.
4. IF the lockfile at `frontend/pnpm-lock.yaml` is out of sync with the frontend `package.json` such that `pnpm install --frozen-lockfile` exits with a non-zero status, THEN THE Operator SHALL regenerate the lockfile using pnpm 9.12.0 so that the frozen-lockfile install completes with a success (zero) exit status.

### Requirement 10: Confirm Docker-capable runner availability

**User Story:** As the Operator, I want a privileged Docker runner confirmed for the jobs that need it, so that build-and-sign and integration-e2e can execute.

#### Acceptance Criteria

1. THE Operator SHALL confirm that at least one Docker_Runner is registered to the GitLab_Project, reports an active/online status, is configured with the Docker executor and privileged mode enabled, and carries tags that match the build-and-sign and integration-e2e jobs.
2. IF no Docker_Runner meeting all conditions in criterion 1 is available, THEN THE Operator SHALL propose either an instance-runner or project-runner option whose configuration incurs zero recurring paid-service cost (USD 0.00).
3. WHEN a proposed runner option is approved, THE Operator SHALL enable the runner and re-verify it against all conditions in criterion 1.
4. IF the runner cannot be enabled or fails re-verification after being enabled, THEN THE Operator SHALL retain the prior project runner configuration unchanged and surface an indication identifying which condition in criterion 1 was not met.

### Requirement 11: Verify and tune the GitLab Cosign identity

**User Story:** As the Operator, I want the Cosign certificate-identity regex verified against an actually-signed image, so that supply-chain verification matches the real GitLab Fulcio subject.

#### Acceptance Criteria

1. WHEN a Deployable_Image is signed via Keyless_Signing, THE Supply_Chain_Verifier SHALL verify that image against the GitLab Fulcio certificate identity and return a success result only when the image's certificate subject matches the configured `--certificate-identity-regexp`.
2. IF the default certificate-identity regex derived from `CI_PROJECT_URL` does not match the real Fulcio subject, THEN THE Operator SHALL update the `--certificate-identity-regexp` in `infrastructure/security/verify_images_gitlab.sh` so that it matches the verified Fulcio subject of the signed image.
3. IF the signed image's certificate subject does not match the configured `--certificate-identity-regexp`, THEN THE Supply_Chain_Verifier SHALL fail verification with a non-zero exit status and an error indicating the certificate-identity mismatch, and SHALL NOT mark the image as verified.
4. WHEN the Operator runs verification against a Deployable_Image that was signed during an actual CI pipeline run, THE Supply_Chain_Verifier SHALL complete verification and return a success result that confirms the tuned certificate identity matches the real Fulcio subject.

### Requirement 12: Confirm mutmut patch-file support

**User Story:** As the Operator, I want the mutmut patch-file mode confirmed on the installed version, so that the MR-scoped mutation-fast job runs as designed.

#### Acceptance Criteria

1. WHEN the Operator verifies the mutation-fast job dependencies, THE Operator SHALL determine, by inspecting the installed mutmut version's supported options, whether the `--use-patch-file` flag is present, and SHALL record the result as a pass (flag present) or fail (flag absent).
2. IF the installed mutmut version does not expose the `--use-patch-file` flag, THEN THE Operator SHALL pin a specific mutmut version that exposes the flag and SHALL re-verify that the pinned version exposes `--use-patch-file` before the mutation-fast job runs.
3. WHILE a mutmut version is pinned to obtain `--use-patch-file` support, THE Operator SHALL preserve the Mutation_Threshold enforcement (rewards < 15%, guardrails < 10%, audit < 10%) executed by scripts/check_mutation_threshold.py, such that the threshold values and the enforcing check remain unchanged.
4. IF no available mutmut version exposes the `--use-patch-file` flag, THEN THE Operator SHALL halt the mutation-fast job setup and SHALL produce an indication that a patch-file-capable mutmut version could not be installed.

### Requirement 13: Constrain builds to amd64

**User Story:** As the Operator, I want builds limited to amd64 until a native arm64 runner exists, so that the QEMU emulation budget is not exceeded.

#### Acceptance Criteria

1. THE build-and-sign job SHALL build all 12 Deployable_Images for the `linux/amd64` platform.
2. THE build-and-sign job SHALL NOT build any Deployable_Image for any platform other than `linux/amd64`.
3. WHERE a native arm64 runner is configured as available, THE build-and-sign job SHALL build all 12 Deployable_Images for the `linux/arm64` platform in addition to `linux/amd64`.
4. IF a platform other than `linux/amd64` is configured for the build-and-sign job while no native runner for that platform is available, THEN THE build-and-sign job SHALL fail before producing images and return an error indicating the platform is unsupported without a native runner.

### Requirement 14: Create pipeline schedules on main

**User Story:** As the Owner, I want the recurring pipelines scheduled, so that mutation, security, and integration runs fire automatically.

#### Acceptance Criteria

1. THE Operator SHALL create an active Pipeline_Schedule targeting the `main` branch for the mutation pipeline with cron expression `0 2 * * 0` evaluated in UTC.
2. THE Operator SHALL create an active Pipeline_Schedule targeting the `main` branch for the security and dependency-audit pipeline with cron expression `0 6 * * 1` evaluated in UTC.
3. THE Operator SHALL create an active Pipeline_Schedule targeting the `main` branch for the integration pipeline with cron expression `0 4 * * *` evaluated in UTC.
4. THE Operator SHALL record, for each Pipeline_Schedule, a written procedure that states the creation method (GitLab API or UI), the target branch (`main`), the cron expression, the UTC timezone, and the active status, sufficient for an independent operator to reproduce the schedule.
5. WHEN a Pipeline_Schedule reaches its next scheduled cron time, THE Operator SHALL verify within 60 minutes of that scheduled time that the schedule triggered a pipeline run on `main` whose status is one of pending, running, or completed.
6. IF a Pipeline_Schedule does not trigger a pipeline run within 60 minutes of its next scheduled cron time, THEN THE Operator SHALL record the failure and the affected schedule, and the schedule SHALL remain configured as active so that the next scheduled run is still attempted.

### Requirement 15: Configure protected environments and approvals

**User Story:** As the Owner, I want oracle-prod protected with approvals and secrets, so that production deploys require deliberate, credentialed authorization.

#### Acceptance Criteria

1. THE Operator SHALL configure the oracle-prod environment as a Protected_Environment requiring at least one approval from an authorized approver before any deploy proceeds.
2. THE Operator SHALL set all deploy secrets for the Protected_Environment as Masked_Protected_Variables via GitLab secret management, such that their values are not displayed in job logs or the UI.
3. WHEN the deploy-oracle-prod job is reached in the pipeline, THE deploy-oracle-prod job SHALL remain in a paused state behind a manual gate and SHALL NOT execute until an authorized approver triggers it.
4. IF a deploy to the Protected_Environment is triggered by a user who is not an authorized approver, THEN THE GitLab_Project SHALL block the deploy, leave the target environment unchanged, and return an indication that authorization was denied.
5. WHEN the Protected_Environment configuration is completed, THE Operator SHALL record a written configuration procedure that documents the protected environment settings, the approval rule, and the masked secret entries.

### Requirement 16: Wire the real deploy flow behind manual gates

**User Story:** As the Owner, I want the deploy jobs connected to the real runner and SSH flow, so that deploys move from placeholders to actual delivery without exposing credentials.

#### Acceptance Criteria

1. THE Operator SHALL connect the deploy-oracle-canary and deploy-oracle-prod jobs to the real runner and SSH flow defined under `infrastructure/oracle/` and `infrastructure/gcp/`, such that no placeholder or stub commands remain in either job definition.
2. THE deploy-oracle-canary and deploy-oracle-prod jobs SHALL execute only when manually triggered, and SHALL NOT start automatically in response to commits, merge events, tags, or scheduled pipelines.
3. THE deploy-oracle-canary and deploy-oracle-prod jobs SHALL obtain every credential exclusively from Masked_Protected_Variables, with no credential sourced from any other location.
4. WHEN a deploy job completes, whether succeeding or failing, THE GitLab_Project SHALL record the deployment in the target environment's deployment history together with its final status.
5. IF a deploy job references a hardcoded credential, THEN THE Operator SHALL block the wiring until the credential is sourced from a Masked_Protected_Variable.
6. IF a deploy job's SSH flow fails to connect or returns a non-zero exit status, THEN THE deploy job SHALL terminate with a failed status, record the failure in the environment's deployment history, and leave the target environment's previously deployed release unchanged.
7. THE deploy-oracle-canary and deploy-oracle-prod jobs SHALL mask all credential values in job output and logs so that no credential value appears in plaintext.

### Requirement 17: Decide and document the admission-controller posture

**User Story:** As the Owner, I want a documented decision on whether Kyverno admission accepts GitLab-signed images, so that the deployable signing source is explicit once GitLab is authoritative.

#### Acceptance Criteria

1. WHEN GitLab is confirmed as the authoritative pipeline, THE Operator SHALL present to the Owner, within the same decision session, exactly two options: (a) wiring Kyverno admission to also accept the GitLab Cosign issuer in addition to the GitHub Cosign issuer, and (b) keeping GitHub-signed images as the sole admission source.
2. WHEN the Owner selects one of the two presented options, THE Operator SHALL record the decision in an ADR committed to the repository, where the ADR captures the selected option, the rejected option, the decision rationale, and the decision date.
3. WHERE the Owner chooses to accept the GitLab Cosign issuer, THE Operator SHALL document in the ADR the specific Kyverno admission policy change required to add the GitLab Cosign issuer as an accepted admission source.
4. IF the Owner has not recorded a decision in a committed ADR, THEN THE Operator SHALL retain GitHub-signed images as the admission source and SHALL NOT modify the Kyverno admission policy.

### Requirement 18: Produce the parity and status report

**User Story:** As the Owner, I want a written parity-and-status report, so that I can see each GitHub workflow's GitLab equivalent, its verified-running status, and residual risks.

#### Acceptance Criteria

1. THE Parity_Report SHALL map each of the six mandatory GitHub workflows (ci, cd, integration, policy, security, mutation) to its GitLab equivalent, identifying each GitLab equivalent by its pipeline or job name.
2. THE Parity_Report SHALL state a verified-running status for each GitLab equivalent, where the status is exactly one of "passing", "failing", or "not-run".
3. WHEN the verified-running status of a GitLab equivalent is "passing" or "failing", THE Parity_Report SHALL record supporting evidence consisting of a reference to the most recent pipeline run and its completion timestamp.
4. IF any of the six mandatory GitHub workflows has no GitLab equivalent, THEN THE Parity_Report SHALL record that workflow as unmapped with a stated reason.
5. THE Parity_Report SHALL list each residual risk remaining after operationalization with a description, a severity of "high", "medium", or "low", and a mitigation or owner.
6. WHEN the Parity_Report is finalized, THE Operator SHALL commit the Parity_Report and any new ADRs to the repository.
7. IF the commit of the Parity_Report or any new ADRs fails, THEN THE Operator SHALL retain the report contents and surface an error indicating the commit did not complete.

### Requirement 19: Surface CI results in merge-request widgets

**User Story:** As a reviewer, I want security, coverage, and CVE findings rendered on merge requests, so that quality signals are visible at review time.

#### Acceptance Criteria

1. WHEN a GitLab_Pipeline completes on a merge request and produces Dependency-Scanning, Secret-Detection, SAST, or Container-Scanning report artifacts, THE GitLab_Project SHALL render the findings from each available report in the merge-request security widget within 60 seconds of pipeline completion.
2. WHEN a GitLab_Pipeline completes and produces a valid Cobertura coverage report, THE GitLab_Project SHALL display the overall coverage value as a percentage (0.00% to 100.00%) on the merge request within 60 seconds of pipeline completion.
3. IF a Dependency-Scanning, Secret-Detection, SAST, or Container-Scanning job fails or produces no parseable report artifact, THEN THE GitLab_Project SHALL omit that scanner's section from the security widget and indicate that results are unavailable for that scanner, while retaining results from the scanners that succeeded.
4. IF the Cobertura coverage report is absent or malformed, THEN THE GitLab_Project SHALL display no coverage value on the merge request and indicate that coverage data is unavailable.
