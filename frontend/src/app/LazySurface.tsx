import { type ReactNode, Suspense } from "react";

interface LazySurfaceProps {
  /** The surface's display name. It names the loading status AND keys the boundary. */
  readonly name: string;
  readonly children: ReactNode;
}

/**
 * The one Suspense boundary every route-split surface renders through (FE-INV-014/025).
 *
 * Keyed by `name`, so moving from one route-split surface to another REMOUNTS the boundary
 * instead of re-suspending a mounted one. A mounted boundary that suspends outside a
 * transition keeps the previous surface in the DOM under `display: none` while the fallback
 * shows, and anything reading `<main>`'s text -- the effectiveness harness's terminal checks
 * do -- would still see the page the operator just left. Unmounted, it cannot be read.
 *
 * The fallback is an `<output>`: its implicit role is `status` (an explicit `role="status"`
 * on a `<div>` is what Biome's `useSemanticElements` rejects), named by `aria-label` and
 * marked `aria-busy`. It carries no `aria-live` attribute on purpose, so selectors for the
 * surfaces' own polite regions (`output[aria-live="polite"]`) never match it. It changes no
 * layout outside itself: inside the Shell, `<main>` is a fixed flex track and the outlet is
 * its only child, and /login renders nothing beside it, so replacing the fallback with the
 * surface moves no element that was already on screen.
 */
export function LazySurface({ name, children }: LazySurfaceProps) {
  return (
    <Suspense key={name} fallback={<SurfaceLoading name={name} />}>
      {children}
    </Suspense>
  );
}

function SurfaceLoading({ name }: { readonly name: string }) {
  return (
    <output
      aria-busy="true"
      aria-label={`Loading ${name}`}
      className="block p-6 text-sm text-ink-muted"
    >
      Loading {name}…
    </output>
  );
}
