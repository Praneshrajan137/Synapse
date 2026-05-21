# BDD behaviour spec — verified by tests/invariants.test.mjs (INV-CLR-006)
# and tests/mutation.test.mjs.
Feature: Decision tier reads as ordered depth
  Decision tier is ordinal data (I-8). Its colour must encode the order, so a
  glance tells reflex (Tier 1) from deep deliberation (Tier 4).

  Scenario: Tier colours form a monotonic lightness ramp
    Given the 4 decision-tier colours
    Then lightness strictly decreases from Tier 1 to Tier 4

  Scenario: Tiers share one calm hue family
    Given the decision-tier ramp
    Then every tier sits on the cognition hue
    And no tier reads as an alarm

  Scenario: A reordered ramp is rejected
    Given a tier ramp where Tier 3 is lighter than Tier 2
    When the ordinality check runs
    Then it fails
