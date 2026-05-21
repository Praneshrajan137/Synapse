/**
 * SYNAPSE Atlas Console — MSW Node server (Vitest).
 * Browser worker for Storybook lives separately at .storybook/mockServiceWorker.js.
 */
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
