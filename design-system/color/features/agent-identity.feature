# BDD behaviour spec — verified by tests/invariants.test.mjs (INV-CLR-004,
# INV-CLR-005, INV-CLR-012) and tests/metamorphic.test.mjs (MR-CLR-002).
Feature: Agent identity is unmistakable
  An operator must always know which of the 8 agents an element belongs to,
  including operators with a colour-vision deficiency.

  Scenario: Each agent owns one earned hue
    Given the 8 SYNAPSE agents
    When each is assigned its identity colour
    Then every pair differs by at least the agent deltaEOK threshold
    And no two agents share a hue family

  Scenario: Agents stay distinct under colour-vision deficiency
    Given the 8 agent identity colours
    When deuteranopia, protanopia, or tritanopia is simulated
    Then every agent pair remains perceptually separated

  Scenario: Colour is never the only signal
    Given an agent shown anywhere in the console
    Then it also carries a unique glyph and a text label

  Scenario: The agent-to-hue map is frozen
    Given the agent identity registry
    When the system is built
    Then exactly the 8 SYNAPSE agents have identity colours
