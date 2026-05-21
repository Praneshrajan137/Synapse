/**
 * SYNAPSE Atlas Console — MSW browser worker (Storybook).
 *
 * Storybook auto-starts via msw-storybook-addon's `mswLoader` (see
 * .storybook/preview.tsx). This file exists so a manual `worker.start()`
 * is also possible for ad-hoc browser harnesses.
 */
import { setupWorker } from "msw/browser";

import { handlers } from "./handlers";

export const worker = setupWorker(...handlers);
