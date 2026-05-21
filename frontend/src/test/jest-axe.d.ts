/**
 * Minimal type shim for jest-axe (v9 ships no bundled type declarations).
 * Covers the surface the SYNAPSE test suite uses.
 */
declare module "jest-axe" {
  export interface AxeResults {
    violations: ReadonlyArray<{
      id: string;
      impact?: string | null;
      description: string;
      help: string;
      nodes: ReadonlyArray<unknown>;
    }>;
  }

  export function axe(
    html: Element | string | Document,
    options?: Record<string, unknown>,
  ): Promise<AxeResults>;

  export function configureAxe(options?: Record<string, unknown>): typeof axe;

  export const toHaveNoViolations: {
    toHaveNoViolations(results: AxeResults): {
      pass: boolean;
      message(): string;
    };
  };
}
