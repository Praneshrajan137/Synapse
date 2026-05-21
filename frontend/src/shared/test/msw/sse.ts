/**
 * SYNAPSE Atlas Console — MSW SSE handler for /api/v1/stream/{topic}.
 *
 * MSW doesn't have a native SSE primitive (yet); we craft a streaming
 * `text/event-stream` body using a `ReadableStream` controller. Each
 * fixture event from `fixtureSseEvents[topic]` is emitted ~400ms apart
 * with a synthetic `partition:offset` event id so reconnection via
 * `Last-Event-ID` is exercisable.
 *
 * The handler deliberately mimics the production SSE bridge contract
 * from `api/routers/sse.py`:
 *   - id is `partition:offset`,
 *   - heartbeat every 15s as a comment-only event,
 *   - body is the raw Kafka payload (JSON string).
 */
import { http, HttpResponse } from "msw";

import { fixtureSseEvents } from "./fixtures";

const TOPIC_RE = /\/api\/v1\/stream\/([\w.]+)$/;

function encodeEvent(id: string, dataObj: unknown): string {
  const data = typeof dataObj === "string" ? dataObj : JSON.stringify(dataObj);
  return `id: ${id}\nevent: message\ndata: ${data}\n\n`;
}

function heartbeat(): string {
  return `:hb ${Date.now()}\n\n`;
}

export const sseHandlers = [
  http.get("*/api/v1/stream/:topic", ({ request, params }) => {
    const topic = String(params["topic"] ?? "");
    const events = fixtureSseEvents[topic] ?? [];
    const encoder = new TextEncoder();

    const stream = new ReadableStream<Uint8Array>({
      async start(controller) {
        let aborted = false;
        request.signal.addEventListener("abort", () => {
          aborted = true;
          try {
            controller.close();
          } catch {
            /* already closed */
          }
        });

        for (let i = 0; i < events.length; i += 1) {
          if (aborted) return;
          await new Promise((resolve) => setTimeout(resolve, 400));
          const id = `0:${i + 1}`;
          controller.enqueue(encoder.encode(encodeEvent(id, events[i])));
        }

        // After the fixture loop finishes, emit a heartbeat every 15s
        // until the consumer disconnects. Bounded to 4 to avoid leaks
        // in jsdom tests with no client teardown.
        for (let h = 0; h < 4; h += 1) {
          if (aborted) return;
          await new Promise((resolve) => setTimeout(resolve, 15_000));
          controller.enqueue(encoder.encode(heartbeat()));
        }
        try {
          controller.close();
        } catch {
          /* noop */
        }
      },
    });

    return new HttpResponse(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  }),

  // 404 shape mirrors the production bridge for robust hook-error tests.
  http.get("*/api/v1/stream/", () =>
    HttpResponse.json({ detail: "topic required" }, { status: 400 }),
  ),
  // Wildcard fallback — anything not in the user-visible topic set 404s.
  http.get("*/api/v1/stream/*", ({ request }) => {
    const m = TOPIC_RE.exec(new URL(request.url).pathname);
    const topic = m?.[1] ?? "unknown";
    if (Object.prototype.hasOwnProperty.call(fixtureSseEvents, topic)) {
      // shouldn't happen — caught by the named-param handler above.
      return undefined;
    }
    return HttpResponse.json(
      { detail: `topic not user-visible: ${topic}` },
      { status: 404 },
    );
  }),
];
