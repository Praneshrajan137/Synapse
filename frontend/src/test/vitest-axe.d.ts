// Type augmentation for the vitest-axe `toHaveNoViolations` matcher registered
// in ./setup.ts. vitest-axe ships the matcher type but not the `declare module
// "vitest"` wiring for Vitest's Assertion, so we add it here.
import "vitest";

interface AxeMatchers {
  toHaveNoViolations(): void;
}

declare module "vitest" {
  // biome-ignore lint/suspicious/noExplicitAny: matches Vitest's own Assertion signature.
  interface Assertion<T = any> extends AxeMatchers {}
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}
