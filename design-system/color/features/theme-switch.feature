# BDD behaviour spec — verified by tests/invariants.test.mjs (INV-CLR-001,
# INV-CLR-013) and tests/metamorphic.test.mjs (MR-CLR-001).
Feature: Theme switching preserves legibility
  Operators run in low-ambient control rooms (dark default) but the console
  must also serve daytime and accessibility use.

  Scenario: Every semantic token resolves in both themes
    Given the semantic token set
    Then each token has a concrete value in light and in dark

  Scenario: Contrast survives theme inversion
    Given a text-on-surface pair that is legible in dark
    When the theme switches to light
    Then the pair still clears WCAG AA and its APCA tier

  Scenario: The theme applies before first paint
    Given a saved theme preference
    When the console loads
    Then the theme is applied with no flash of the wrong theme

  Scenario: System preferences are honoured
    Given a user who prefers reduced motion or increased contrast
    Then the stylesheet defines a fallback for that preference
