import { z } from "zod";

// zod's global configuration. This module must be evaluated before any schema is built.
//
// Why: frontend/nginx.conf serves `script-src 'self'` (no 'unsafe-eval') with
// `report-uri /api/v1/csp-report`. zod 4 compiles a fast object parser with `new Function`, and
// decides whether it may by probing `new Function("")` once, when the first `z.object()` is
// constructed (`util.allowsEval`, zod 4.6.7 core/util.ts). The policy refuses the probe and zod
// falls back to its interpreted parser, but, in zod's own words there, "strict CSPs report the
// caught `new Function` as a `securitypolicyviolation` even though the throw is swallowed": one
// report per page load, which buries a real violation. `jitless: true` skips both the probe and
// the compiler (`$ZodConfig.jitless`, core/core.ts: "Disable JIT schema compilation. Useful in
// environments that disallow `eval`."), so the Console keeps the interpreted parser it already
// ended up on and files no report.
//
// Order: zod reads the flag when each `z.object()` is CONSTRUCTED (`const jit =
// !core.globalConfig.jitless` in the `$ZodObjectJIT` initializer, core/schemas.ts). A schema
// built before this line still runs the probe and keeps the compiled path. `src/main.tsx`
// imports this module first, and an ES module evaluates its imports in source order, so this
// runs before any schema module. `src/test/setup.ts` imports it first too, so vitest parses
// with the same interpreted parser production uses.
z.config({ jitless: true });
