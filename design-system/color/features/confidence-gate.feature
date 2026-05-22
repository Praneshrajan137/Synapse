# BDD behaviour spec — verified by tests/invariants.test.mjs (INV-CLR-007),
# tests/metamorphic.test.mjs (MR-CLR-003) and tests/fuzz.test.mjs.
Feature: Confidence reads at a glance and respects the I-5 gates
  Confidence is continuous data. Its colour must move smoothly with the value
  and break exactly where the human-in-the-loop gates sit.

  Scenario: The scale traverses red to teal
    Given a confidence value rising from 0 to 1
    When it is mapped to a colour
    Then the hue advances monotonically red -> amber -> green -> teal
    And the mapping is continuous with no jumps

  Scenario: Zone boundaries equal the I-5 gates
    Given the confidence zones low, escalation and autonomous
    Then the boundaries fall exactly at 0.70 and 0.80

  Scenario: A value below the gate is flagged for escalation
    Given a decision with confidence 0.62
    Then its zone is "low"
    And the gauge shows a non-colour zone label

  Scenario: Out-of-range input is clamped, never crashed
    Given a confidence value outside [0,1]
    When it is mapped to a colour
    Then the value is clamped to the [0,1] endpoints
