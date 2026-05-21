/**
 * SYNAPSE Atlas Console — IndexedDB-backed offline queue.
 *
 * Used by Mission Control to persist HITL responses (Approve / Reject /
 * Modify) until the orchestrator ACKs over the WebSocket. If the page
 * reloads or the socket drops mid-decision, the queue survives and the
 * next mount replays.
 *
 * Storage: a single keyval pair under `KEY` holding a JSON-serialised
 * array of entries. We keep a single key (not a per-entry key) because
 * (a) volume is tiny — ops staff make tens of decisions per shift, not
 * thousands; (b) atomic replace simplifies dedup; (c) idb-keyval's
 * single-key API is the smallest supply-chain surface.
 *
 * Entries are tagged with a stable client-side `clientId` so the
 * orchestrator can ACK exactly which response was processed.
 */
import { get, set, del } from "idb-keyval";

const KEY = "atlas:mc:offline-queue";

export interface QueuedResponse<T = unknown> {
  /** Stable, client-issued id used for ACK matching. */
  readonly clientId: string;
  /** ISO timestamp of original action. */
  readonly enqueuedAt: string;
  /** The decision the operator acted on. */
  readonly decisionId: string;
  /** Action payload — schema enforced upstream by Zod. */
  readonly payload: T;
}

function newClientId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `q-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export async function readQueue<T>(): Promise<QueuedResponse<T>[]> {
  const raw = await get<QueuedResponse<T>[]>(KEY);
  return Array.isArray(raw) ? raw : [];
}

export async function enqueue<T>(
  decisionId: string,
  payload: T,
): Promise<QueuedResponse<T>> {
  const entry: QueuedResponse<T> = {
    clientId: newClientId(),
    enqueuedAt: new Date().toISOString(),
    decisionId,
    payload,
  };
  const existing = await readQueue<T>();
  await set(KEY, [...existing, entry]);
  return entry;
}

export async function ack(clientId: string): Promise<void> {
  const existing = await readQueue();
  const filtered = existing.filter((e) => e.clientId !== clientId);
  if (filtered.length === 0) {
    await del(KEY);
  } else {
    await set(KEY, filtered);
  }
}

export async function clearQueue(): Promise<void> {
  await del(KEY);
}

export const __TEST_ONLY__ = { newClientId };
