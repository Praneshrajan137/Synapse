/**
 * Bounded ring buffer — the shared, property-testable model lifted out of
 * `state/firehose.store.ts` (design "E. lib — ring-buffer + firehose stress",
 * Req 6).
 *
 * The firehose store held its own private `newBounded`/`appendBounded` per
 * channel (governed by FE-INV-017). This module lifts that exact model into
 * `lib/` so it can be reused and property-tested without changing the runtime
 * caps: the eviction semantics here are byte-for-byte the same as the store's
 * previous inline implementation (append at the tail, evict from the head once
 * `cap` is reached, never mutate the source array).
 *
 * `applyOnce` adds the at-most-once sequence guarantee (Req 6.3, 6.5): a
 * message whose `seq` was already applied is dropped rather than re-appended,
 * so a firehose replay/duplicate can never double-count an item.
 */

/**
 * A bounded, append-only buffer. `items.length` is always `≤ cap` regardless
 * of how many appends occur (Req 6.2). Both fields are readonly so callers
 * treat a buffer as an immutable value and replace it on append.
 */
export interface RingBuffer<T> {
  readonly cap: number;
  /** Retained items, oldest first; length always ≤ cap (Req 6.2). */
  readonly items: readonly T[];
}

/**
 * A fresh empty buffer with the given cap.
 *
 * A non-positive cap is meaningless for a bounded buffer; it is clamped to 1 so
 * the invariant `0 < items.length ≤ cap` after an append still holds and a
 * caller can never construct a zero-capacity buffer that silently drops
 * everything.
 */
export function newBounded<T>(cap: number): RingBuffer<T> {
  const safeCap = Number.isFinite(cap) && cap >= 1 ? Math.floor(cap) : 1;
  return { cap: safeCap, items: [] };
}

/**
 * Appends `item`, evicting the oldest entry when the buffer is at capacity so
 * `items.length` never exceeds `cap` regardless of call count (Req 6.2).
 *
 * Returns a new buffer; the source `buf.items` array is never mutated (the
 * immutability FE-INV-017 relied on).
 */
export function appendBounded<T>(buf: RingBuffer<T>, item: T): RingBuffer<T> {
  const items = buf.items.length >= buf.cap ? [...buf.items.slice(1), item] : [...buf.items, item];
  return { cap: buf.cap, items };
}

/**
 * At-most-once application keyed by `seq` (Req 6.3, 6.5).
 *
 * When `msg.seq` is already present in `appliedSeqs` the message is a duplicate
 * (e.g. a firehose replay after reconnect) and is dropped: the buffer is
 * returned unchanged and `applied` is `false`. Otherwise the message is
 * appended via {@link appendBounded} and `applied` is `true`. The caller owns
 * `appliedSeqs` and adds `msg.seq` to it when `applied` is `true`, so no
 * message applies more than once.
 */
export function applyOnce<T extends { seq: number }>(
  buf: RingBuffer<T>,
  appliedSeqs: ReadonlySet<number>,
  msg: T,
): { readonly buf: RingBuffer<T>; readonly applied: boolean } {
  if (appliedSeqs.has(msg.seq)) {
    return { buf, applied: false };
  }
  return { buf: appendBounded(buf, msg), applied: true };
}
