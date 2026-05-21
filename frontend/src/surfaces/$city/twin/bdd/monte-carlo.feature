Feature: Supply Analyst runs a Monte-Carlo what-if
  As a Supply Analyst
  I want to launch a 1000-scenario simulation, see fan-out + KL divergence + counterfactual
  So that I can quantify a what-if before recommending it to ops

  Background:
    Given I am authenticated as supply_analyst_01
    And the active city is "bengaluru"

  @smoke @twin-studio @search-params
  Scenario: Form input is URL-shareable
    When I navigate to /bengaluru/twin
    And I set demand_multiplier to 1.5
    Then the URL contains "demand_multiplier=1.5"

  @twin-studio @sla
  Scenario: 1000 scenarios complete within INV-TW-004 (≤ 10s)
    Given I set n_scenarios to 1000
    When I press "Run simulation"
    Then a result arrives within 10 seconds
    And the fan-out chart renders p10 / p50 / p90

  @twin-studio @drift
  Scenario: KL divergence > 0.1 fires the assertive banner
    Given a result whose latest KL divergence is 0.18
    Then a critical-contrast banner reads "Twin diverging — KL > 0.1"
    And it has aria-live="assertive"
