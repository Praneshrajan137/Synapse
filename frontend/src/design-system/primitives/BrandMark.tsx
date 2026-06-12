interface BrandMarkProps {
  readonly size?: number;
}

/**
 * The SYNAPSE mark (ADR-045): a pulse-ring glyph — two concentric rings
 * around a live center dot, in the brand cognition-blue. Echoes the Cortex
 * Pulse, the system's signature motif: a breathing ring around a living
 * core. Replaces the anonymous gradient square. Decorative (aria-hidden);
 * the wordmark beside it carries the name.
 */
export function BrandMark({ size = 22 }: BrandMarkProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 22 22" aria-hidden="true" className="shrink-0">
      <circle
        cx="11"
        cy="11"
        r="9.5"
        fill="none"
        stroke="rgb(var(--syn-brand))"
        strokeOpacity="0.35"
        strokeWidth="1.5"
      />
      <circle
        cx="11"
        cy="11"
        r="6"
        fill="none"
        stroke="rgb(var(--syn-brand))"
        strokeOpacity="0.7"
        strokeWidth="1.5"
      />
      <circle cx="11" cy="11" r="2.5" fill="rgb(var(--syn-brand))" />
    </svg>
  );
}
