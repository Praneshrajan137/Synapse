import { surfaceByRoute } from "@/app/shell/navigation";
import { useLocation } from "react-router-dom";

/**
 * Placeholder for surfaces not yet rebuilt (Theater, Streams). Renders
 * the surface identity and the phase that delivers it, so the
 * navigation model is fully explorable before every surface exists.
 */
export default function ConstructionSurface() {
  const { pathname } = useLocation();
  const surface = surfaceByRoute(pathname);

  if (!surface) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-hint">
        Unknown surface.
      </div>
    );
  }

  const Icon = surface.icon;

  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-md text-center">
        <div className="mx-auto mb-5 flex size-16 items-center justify-center rounded-xl border border-line-faint bg-elevated">
          <Icon size={28} className="text-sig-think" aria-hidden="true" />
        </div>
        <h1 className="font-display text-xl font-semibold text-ink-primary">
          {surface.label}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-secondary">
          {surface.description}.
        </p>
        <p className="mt-4 inline-flex items-center gap-2 rounded-md border border-line-faint bg-paper px-3 py-1.5 text-2xs text-ink-hint">
          <span className="size-1.5 rounded-full bg-sig-warn" aria-hidden="true" />
          Delivered in Phase {surface.phase} of the Synaptic Calm rebuild
        </p>
      </div>
    </div>
  );
}
