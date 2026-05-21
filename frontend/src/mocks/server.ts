import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/** Node MSW server — used by the Vitest suite (see src/test/setup.ts). */
export const server = setupServer(...handlers);
