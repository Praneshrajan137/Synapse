/**
 * SYNAPSE Atlas Console — MSW handler barrel.
 *
 * Composed of REST + SSE + WebSocket. Storybook (browser worker) and
 * Vitest (node server) both subscribe through this single export so a
 * fixture change touches one file and propagates everywhere.
 */
import { restHandlers } from "./rest";
import { sseHandlers } from "./sse";
import { wsHandlers } from "./ws";

export const handlers = [...restHandlers, ...sseHandlers, ...wsHandlers];
