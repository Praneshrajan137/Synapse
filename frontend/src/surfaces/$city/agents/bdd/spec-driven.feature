Feature: Adding a new agent requires no UI code change
  As a platform engineer
  I want the Agent Floor to render new agents from spec.yaml only
  So that adding an agent is a 1-PR change (plan §5.5 acceptance)

  @smoke @agent-floor
  Scenario: Agent panels are derived from virtual:atlas/agent-specs
    Given the repo's agents/ directory contains 8 spec.yaml files
    When I navigate to /bengaluru/agents
    Then I see exactly 8 agent panels
    And each panel's title matches the spec.agent_name
    And each panel displays its state machine

  @agent-floor @hmr
  Scenario: Editing a spec.yaml live-updates its panel via HMR
    Given the dev server is running
    When I edit agents/demand_prophet/spec.yaml and bump the version
    Then the demand_prophet panel re-renders with the new version
    And no other panels re-render unnecessarily

  @agent-floor @aaa
  Scenario: A failing critical invariant is rendered with AAA contrast
    Given an invariant of severity "critical" reports status "fail"
    Then the panel border uses the safety-critical token
    And the failing item's badge clears WCAG AAA (7:1) on the active theme
