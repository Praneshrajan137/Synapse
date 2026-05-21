# SYNAPSE Atlas Console — Decision Trace · BDD scenarios

Feature: Supply Analyst replays a decision window
  As a Supply Analyst
  I want to filter, replay, and verify the audit chain of any decision
  So that I can explain a decision end-to-end with cryptographic proof

  Background:
    Given I am authenticated as supply_analyst_01
    And the active city is "bengaluru"
    And the API has 50 fixture decisions across all four tiers

  @smoke @decision-trace @search-params
  Scenario: Filtering on tier preserves the URL
    When I navigate to /bengaluru/decisions
    And I filter to tier_4
    Then the URL contains "?tier=tier_4"
    And the table shows only tier_4 rows

  @decision-trace @drawer
  Scenario: Opening a row reveals the 5-phase trace
    When I click the first row
    Then the drawer is visible
    And it shows the 5-phase timeline
    And the chain-proof banner reads "Audit chain verified"
    And the JSON export button is enabled

  @decision-trace @audit-chain
  Scenario: A tampered chain blocks export
    Given a decision whose audit_trace[1].hash has been tampered with
    When I open that decision's drawer
    Then the chain-proof banner reads "Audit chain broken"
    And the JSON export button is disabled
    And an alert is announced via the live region

  @decision-trace @scrubber @determinism
  Scenario: The scrubber never drops a decision
    Given the table has 25 decisions in the loaded window
    When I move the scrubber to t-30 minutes
    And I move it back to t-0
    Then the rendered row count is unchanged
    And no decision_id is missing from the rendered set
