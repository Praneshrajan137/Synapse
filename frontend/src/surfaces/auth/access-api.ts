import { createHttpClient } from "@transport/http-client";
import { z } from "zod";

// ADR-057 — the two public auth calls the console makes before it holds any token. They
// live beside the boot hook, not in the shared typed client, because the shared client
// attaches the session's bearer token and these two calls never carry one.

const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL ?? "";

/** Overall deadline for each call, so a hung gateway can never hold the boot splash open. */
export const ACCESS_CALL_TIMEOUT_MS = 8_000;

// Mirrors api/routers/auth.py AccessModeResponse: `authority` is null exactly when the
// gateway requires sign-in.
export const AccessModeResponseSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("open"), authority: z.enum(["view", "act"]) }).strict(),
  z.object({ mode: z.literal("authenticated"), authority: z.null() }).strict(),
]);
export type AccessModeResponse = z.infer<typeof AccessModeResponseSchema>;

// Mirrors api/routers/auth.py PreviewResponse. A preview grant is never above ops: the
// gateway refuses to sign one (api/access.py), and this schema refuses to accept one.
export const PreviewGrantSchema = z
  .object({
    access_token: z.string().min(1),
    token_type: z.literal("Bearer"),
    expires_in: z.number().int().positive(),
    role: z.enum(["viewer", "ops"]),
    operator_token_ref: z.string(),
    authority: z.enum(["view", "act"]),
  })
  .strict();
export type PreviewGrant = z.infer<typeof PreviewGrantSchema>;

const gateway = createHttpClient({ baseUrl: GATEWAY_URL });

/** GET /api/v1/auth/mode — public; which posture the gateway runs under. */
export function fetchAccessMode(): Promise<AccessModeResponse> {
  return gateway.get("/api/v1/auth/mode", {
    schema: AccessModeResponseSchema,
    schemaId: "AccessModeResponse",
    timeoutMs: ACCESS_CALL_TIMEOUT_MS,
  });
}

/** POST /api/v1/auth/preview — public in open mode; a one-hour grant, no refresh token. */
export function requestPreviewGrant(): Promise<PreviewGrant> {
  return gateway.post("/api/v1/auth/preview", undefined, {
    // A second grant is harmless, so a transient failure may be retried.
    idempotent: true,
    schema: PreviewGrantSchema,
    schemaId: "PreviewGrant",
    timeoutMs: ACCESS_CALL_TIMEOUT_MS,
  });
}
