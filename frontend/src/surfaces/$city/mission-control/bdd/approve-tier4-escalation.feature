# SYNAPSE Atlas Console — Mission Control · BDD scenarios
#
# Plan §7.3: one BDD feature per persona × surface for golden paths.
# Step definitions live alongside the Playwright e2e specs in
# tests/e2e/mission-control.spec.ts and re-export to Cucumber via the
# adapter wired in playwright.config.ts.

Feature: Ops Controller approves a tier-4 escalation
  As an Ops Controller in Bengaluru
  I want to approve a tier-4 escalation in under five seconds
  So that the supply chain doesn't fall back to a default action

  Background:
    Given I am authenticated as ops_controller_01
    And the active city is "bengaluru"
    And the WebSocket /ws/escalation is connected

  @smoke @mission-control @keyboard
  Scenario: Approve via keyboard
    Given a tier-4 escalation arrives with confidence 0.31 and 90 seconds remaining
    When I press "j"
    And I press "Enter"
    Then the escalation is approved within 1 second
    And the audit-trailed action is "approved"
    And the live region announces "Escalation approved"
    And the offline queue contains zero unACKed entries

  @mission-control @aria
  Scenario: Urgency bar fires below 30 seconds
    Given a tier-4 escalation arrives with 25 seconds remaining
    Then the urgency banner is visible
    And it has role "alert"
    And the banner contrast clears WCAG AAA

  @mission-control @hotkeys
  Scenario: Help dialog discovers every shortcut
    When I press "?"
    Then the hotkeys help dialog opens
    And it lists shortcuts for next, prev, approve, reject, modify, defocus, help
    When I press "Escape"
    Then the dialog closes

  @mission-control @resilience
  Scenario: Reconnect replays the offline queue
    Given a tier-3 escalation arrives
    And I press "r"
    And the WebSocket disconnects before the ACK arrives
    When the WebSocket reconnects
    Then the rejection is re-sent with the same client_id
    And the offline queue is cleared on ACK
