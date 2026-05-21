/**
 * SYNAPSE Atlas Console — realtime barrel.
 *
 * Re-export under named entry. Surfaces import from `@shared/realtime`
 * rather than reaching into individual files.
 */
export { useWebSocket } from "./use-websocket";
export type { UseWebSocketOptions, UseWebSocketResult } from "./use-websocket";
export { useSse } from "./use-sse";
export type { UseSseOptions, UseSseResult } from "./use-sse";
