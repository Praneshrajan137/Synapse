import { type ReactNode, Suspense } from "react";
import { LazyChunkBoundary } from "./LazyChunkBoundary";

interface LazySurfaceProps {
  /** The surface's display name: it names the loading and failed states and keys the boundary. */
  readonly name: string;
  readonly children: ReactNode;
}

/**
 * The one Suspense boundary every route-split surface renders through (FE-INV-014/025), inside
 * `LazyChunkBoundary`, which renders the surface's failed-chunk state (finding 92).
 *
 * Keyed by `name`, so moving from one route-split surface to another REMOUNTS both boundaries
 * instead of re-suspending a mounted one, and a failure caught on one surface does not follow
 * the operator to the next. A mounted boundary that suspends outside a transition keeps the
 * previous surface in the DOM under `display: none` while the fallback shows, and anything
 * reading `<main>`'s text -- the effectiveness harness's terminal checks do -- would still see
 * the page the operator just left. Unmounted, it cannot be read.
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
    <LazyChunkBoundary key={name} name={name}>
      <Suspense fallback={<SurfaceLoading name={name} />}>{children}</Suspense>
    </LazyChunkBoundary>
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
