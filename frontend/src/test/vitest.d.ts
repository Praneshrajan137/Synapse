/**
 * Type augmentation so jest-axe's `toHaveNoViolations` matcher is
 * recognized on Vitest's `expect`.
 */
import "vitest";

declare module "vitest" {
  interface Assertion {
    toHaveNoViolations(): void;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void;
  }
}
