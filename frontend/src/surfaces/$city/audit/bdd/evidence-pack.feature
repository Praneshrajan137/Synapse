Feature: Compliance auditor exports a deterministic evidence pack
  As a Compliance / FSSAI auditor
  I want a byte-deterministic PDF for any decision, gated by chain proof + PII reauth
  So that I can rely on the export as authoritative regulatory evidence

  Background:
    Given I am authenticated as compliance_auditor_01
    And the active city is "bengaluru"

  @smoke @audit-vault @residency
  Scenario: Residency chip is always visible
    When I navigate to /bengaluru/audit
    Then a residency chip "data: ap-south-1 · retained 90d" is visible

  @audit-vault @pii @reauth
  Scenario: Revealing PII requires reauth
    When I press "Reveal PII"
    Then a password dialog opens
    When I confirm with my password
    Then the PII columns render unredacted
    And the URL contains "pii=true"
    And the elevated window expiry is announced via the live region

  @audit-vault @determinism
  Scenario: Two PDF exports of the same decision are byte-equal
    Given I open a decision whose chain verifies
    When I download the evidence PDF twice
    Then the two SHA-256 digests are identical
    And the X-Atlas-Audit-SHA256 response header matches the file
