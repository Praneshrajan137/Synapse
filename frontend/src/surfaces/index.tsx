/**
 * SYNAPSE Atlas Console — `/` route.
 *
 * No standalone home view: redirect to /bengaluru/. Mumbai is reached
 * through the city switcher in the chrome.
 */
import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  beforeLoad: () => {
    throw redirect({ to: "/$city/", params: { city: "bengaluru" } });
  },
});
