# BDD behaviour spec — verified by tests/invariants.test.mjs (INV-CLR-002,
# INV-CLR-003, INV-CLR-014) and exercised live in the Override Console.
Feature: Escalations communicate urgency without relying on colour alone
  The Override Console is a safety surface. An escalation must read clearly,
  and its outcome controls must be legible and unambiguous.

  Scenario: An escalation card is tinted by its confidence zone
    Given an escalation with a confidence value
    When the card renders
    Then its rail is tinted by the confidence zone colour
    And the confidence gauge states the zone in words

  Scenario: HITL outcome buttons are legible
    Given the approve, modify and reject buttons
    Then each button label clears its APCA contrast tier
    And each carries a text label, not colour alone

  Scenario: State colours never collide with each other
    Given the 5 semantic state colours
    Then every pair is distinct in both themes and under CVD simulation
