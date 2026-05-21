import { defineConfig } from "orval";

// SYNAPSE Atlas Console — Orval codegen.
//
// Source of truth: ../packages/openapi/openapi.json. CI asserts byte-equality
// (modulo sorted keys) with `GET /openapi.json` from a fresh-booted gateway.
// Drift = red, see plan §11/B5 and tests/contract/test_openapi_byte_equality.py.
//
// Output: src/shared/api/__generated__/ (gitignored except .gitkeep). Hooks
// are TanStack Query 5 — keep keys in sync with the [cityId, ...] convention.
//
// Mock target intentionally omitted; MSW 2 handlers live alongside fixtures
// in src/shared/test/msw/ and are written by hand against the same Zod
// schemas (see scripts/json-schema-to-zod.mjs).
export default defineConfig({
  synapse: {
    input: {
      target: "../packages/openapi/openapi.json",
      validation: false,
    },
    output: {
      target: "src/shared/api/__generated__/synapse.ts",
      schemas: "src/shared/api/__generated__/schemas",
      client: "react-query",
      mode: "tags-split",
      clean: true,
      prettier: true,
      override: {
        mutator: {
          path: "src/shared/api/fetcher.ts",
          name: "synapseFetcher",
        },
        query: {
          useQuery: true,
          useInfinite: true,
          useInfiniteQueryParam: "cursor",
          options: {
            staleTime: 5_000,
            retry: 2,
          },
        },
        // Decision payloads MUST round-trip canonicalised JSON to preserve
        // KV-cache prefix stability (I-13). The fetcher applies sort-keys
        // serialization before the request body is dispatched.
        operations: {
          submitDecision: {
            requestOptions: { keepalive: true },
          },
        },
      },
    },
    hooks: {
      // Auto-format generated files; Prettier config is the project default.
      afterAllFilesWrite: "prettier --write",
    },
  },
});
