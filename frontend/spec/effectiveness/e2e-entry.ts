/**
 * Effectiveness_Harness -- the e2e-only entry (AD-12).
 *
 * This is the ONLY module that imports `./harness.ts`, and it is reachable only
 * through the `e2e` build mode: `frontend/vite.config.ts` injects a script tag
 * for this file into `index.html` when `mode === "e2e"`, which makes it a second
 * Rollup input alongside the app entry. In every other mode the file is never
 * resolved, so `window.__atlasHarness` cannot reach the shipped bundle -- the
 * property `scripts/audit/workflow_shape_truth.py::assert_harness_absent_from_bundle`
 * checks over `frontend/dist/`.
 *
 * The `import.meta.env` guard is the second, independent lock: even if this
 * module were pulled into a production graph by accident, the dynamic import
 * below is dead code under `VITE_E2E_HARNESS !== "1"` and the harness is never
 * installed. `frontend/.env.e2e` sets that flag for the `e2e` mode only.
 *
 * Top-level `await` is load-bearing. Module scripts execute in document order,
 * and an awaiting module delays the ones after it, so the seeded HTTP and stream
 * edges are in place before `/src/main.tsx` boots the Console and issues its
 * first request (Req 1.1, 1.5).
 *
 * An install failure is reported loudly and does NOT block the app from
 * booting: the specs then fail against a Console with no harness, which is the
 * honest outcome. It is never converted into a silent pass (I-7).
 */

const E2E_HARNESS_FLAG: unknown = import.meta.env.VITE_E2E_HARNESS;

if (E2E_HARNESS_FLAG === "1" || E2E_HARNESS_FLAG === true) {
  try {
    const { installAtlasHarness } = await import("./harness");
    await installAtlasHarness();
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error(
      "Effectiveness_Harness failed to install; the harness-dependent e2e specs will fail " +
        "against an un-harnessed Console (this is not a pass).",
      error,
    );
  }
}

export {};
