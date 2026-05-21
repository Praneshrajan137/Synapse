Feature: SRE confirms the live city pulse
  As an SRE
  I want a single screen showing live KPIs, the city map, and the event tail
  So that I can detect operational drift in under 5 seconds

  Background:
    Given I am authenticated as sre_01
    And the active city is "bengaluru"

  @smoke @living-city
  Scenario: KPI band renders the five tiles even with no data
    When I navigate to /bengaluru/
    Then I see five KPI tiles: orders/min, avg delivery, fill rate, waste rate, CO₂
    And missing values render as "—" (never "0")

  @living-city @sse
  Scenario: Disruption alerts surface on the map and the tail simultaneously
    Given a "synapse.disruption.alert" event arrives
    Then a disruption pin appears on the Living Map
    And the event tail shows the event with an "alert" badge

  @living-city @aria
  Scenario: The map is reachable from a "skip to main content" link
    When I press Tab from the URL bar
    Then a visible focus ring appears on the skip-link
    And following it lands focus inside the map region
