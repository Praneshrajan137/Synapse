import { useUIStore } from "@/app/store/uiStore";
import type { City } from "@/domain/city";
import { CITY_LABEL } from "@/domain/city";
import { cn } from "@/ui/lib/cn";
import { signal } from "@/ui/tokens";
import { useMemo } from "react";

/**
 * LivingMap — the dark-store network as a living constellation.
 *
 * A custom SVG spatial view (no map vendor, no tiles — tenet T-12):
 * stores are nodes sized by demand load, high-load stores breathe and
 * ping, and order arcs flow between them. Deterministic per city so the
 * layout is stable across renders.
 */

const VIEW_W = 800;
const VIEW_H = 500;

interface Store {
  id: string;
  x: number;
  y: number;
  load: number;
}

interface Arc {
  from: Store;
  to: Store;
  mid: { x: number; y: number };
}

function mulberry32(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function buildNetwork(city: City): { stores: Store[]; arcs: Arc[] } {
  const r = mulberry32(city === "mumbai" ? 7919 : 4231);
  const prefix = city === "mumbai" ? "MUM" : "BLR";
  // Mumbai's footprint is coastal and elongated; Bengaluru is rounder.
  const spreadX = city === "mumbai" ? 0.52 : 0.7;
  const spreadY = city === "mumbai" ? 0.78 : 0.66;

  const stores: Store[] = Array.from({ length: 25 }, (_, i) => {
    // Gaussian-ish placement around the center.
    const gx = (r() + r() + r()) / 3 - 0.5;
    const gy = (r() + r() + r()) / 3 - 0.5;
    return {
      id: `${prefix}-S-${String(i + 1).padStart(3, "0")}`,
      x: VIEW_W / 2 + gx * VIEW_W * spreadX,
      y: VIEW_H / 2 + gy * VIEW_H * spreadY,
      load: r(),
    };
  });

  const arcs: Arc[] = Array.from({ length: 7 }, () => {
    const from = stores[Math.floor(r() * stores.length)] as Store;
    let to = stores[Math.floor(r() * stores.length)] as Store;
    if (to === from) to = stores[(stores.indexOf(from) + 3) % stores.length] as Store;
    const mx = (from.x + to.x) / 2 + (r() - 0.5) * 120;
    const my = (from.y + to.y) / 2 + (r() - 0.5) * 120;
    return { from, to, mid: { x: mx, y: my } };
  });

  return { stores, arcs };
}

export function LivingMap({ className }: { className?: string }) {
  const city = useUIStore((s) => s.city);
  const { stores, arcs } = useMemo(() => buildNetwork(city), [city]);

  return (
    <div className={cn("relative overflow-hidden bg-void", className)}>
      <div className="absolute left-4 top-3 z-10">
        <h2 className="font-display text-2xs font-semibold uppercase tracking-[0.14em] text-ink-secondary">
          Living Map · {CITY_LABEL[city]}
        </h2>
        <p className="text-2xs text-ink-hint">
          {stores.length} dark stores · live order flow
        </p>
      </div>

      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        preserveAspectRatio="xMidYMid slice"
        className="size-full"
        role="img"
        aria-label={`${CITY_LABEL[city]} dark-store network — ${stores.length} stores`}
      >
        <title>{`${CITY_LABEL[city]} dark-store network`}</title>

        {/* Depth rings */}
        {[320, 220, 120].map((radius) => (
          <circle
            key={radius}
            cx={VIEW_W / 2}
            cy={VIEW_H / 2}
            r={radius}
            fill="none"
            stroke="var(--color-line-faint)"
          />
        ))}

        {/* Order arcs — faint base + flowing energy overlay */}
        {arcs.map((arc, i) => {
          const d = `M${arc.from.x} ${arc.from.y} Q${arc.mid.x} ${arc.mid.y} ${arc.to.x} ${arc.to.y}`;
          return (
            <g key={`arc-${arc.from.id}-${arc.to.id}-${i}`}>
              <path
                d={d}
                fill="none"
                stroke={signal.live}
                strokeOpacity={0.12}
                strokeWidth={1.5}
              />
              <path
                d={d}
                fill="none"
                stroke={signal.live}
                strokeWidth={1.6}
                strokeLinecap="round"
                className="animate-flow"
              />
            </g>
          );
        })}

        {/* Stores */}
        {stores.map((store) => {
          const radius = 3 + store.load * 6;
          const hot = store.load > 0.72;
          const color = hot ? signal.warn : signal.live;
          return (
            <g key={store.id}>
              {hot && (
                <circle
                  cx={store.x}
                  cy={store.y}
                  r={radius}
                  fill="none"
                  stroke={color}
                  strokeWidth={1.5}
                  style={{
                    transformOrigin: `${store.x}px ${store.y}px`,
                    animation: "synapse-ping 2.4s ease-out infinite",
                  }}
                />
              )}
              <circle
                cx={store.x}
                cy={store.y}
                r={radius}
                fill={color}
                fillOpacity={hot ? 0.9 : 0.55}
              >
                <title>{`${store.id} · demand load ${(store.load * 100).toFixed(0)}%`}</title>
              </circle>
            </g>
          );
        })}
      </svg>

      <div className="absolute bottom-3 left-4 flex items-center gap-4 text-2xs text-ink-hint">
        <span className="flex items-center gap-1.5">
          <span
            className="size-2 rounded-full"
            style={{ backgroundColor: signal.live }}
          />
          nominal load
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="size-2 rounded-full"
            style={{ backgroundColor: signal.warn }}
          />
          surge
        </span>
      </div>
    </div>
  );
}
