/**
 * SYNAPSE Atlas Console — MSW WebSocket handler for /ws/escalation.
 *
 * MSW 2 ships first-class WS interception via `ws.link()`. We model the
 * server-side of the HITL escalation socket: on connect, push two
 * fixture escalations (tier 4 + tier 3); on receive, ack with a small
 * confirmation envelope.
 *
 * Note: the existing legacy `useWebSocket` JSX hook connects relative,
 * so the URL pattern matches `*/\/ws/escalation` to cover both `ws://`
 * and `wss://` variants.
 */
import { ws } from "msw";

import { fixtureConsensusDecision } from "./fixtures";

const escalationLink = ws.link("*/ws/escalation");

const tier4Payload = {
  type: "escalation",
  decision_id: fixtureConsensusDecision.decision_id,
  tier: "tier_4",
  confidence: 0.31,
  proposals: fixtureConsensusDecision.proposals,
  recommended_action: fixtureConsensusDecision.selected_action,
  violations: ["pricing_essential_cap_exceeded"],
};

const tier3Payload = {
  type: "escalation",
  decision_id: "bbbb2222-bbbb-4bbb-bbbb-bbbb22222222",
  tier: "tier_3",
  confidence: 0.42,
  proposals: fixtureConsensusDecision.proposals,
  recommended_action: { sku_id: "SKU-002", reorder: 90 },
  violations: [],
};

export const wsHandlers = [
  escalationLink.addEventListener("connection", ({ client }) => {
    // Push two escalations spaced apart so the surface can show both
    // ordering rules and the live-region announcement cadence.
    client.send(JSON.stringify(tier4Payload));
    setTimeout(() => client.send(JSON.stringify(tier3Payload)), 250);

    client.addEventListener("message", (event) => {
      // Echo a confirmation envelope so the SPA's offline-queue logic can be
      // exercised in tests.
      try {
        const parsed = JSON.parse(String(event.data));
        client.send(
          JSON.stringify({
            type: "ack",
            decision_id: parsed?.decision_id ?? null,
            response: parsed?.response ?? null,
          }),
        );
      } catch {
        client.send(JSON.stringify({ type: "ack", error: "invalid_json" }));
      }
    });
  }),
];
