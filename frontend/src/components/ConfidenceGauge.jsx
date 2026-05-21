import React from "react";
import { confidenceColor, confidenceZone, CONFIDENCE_GATE } from "@chromatic/tokens.ts";
import { useTheme } from "../theme/useTheme";

// Confidence is continuous data — encoded on the diverging confidence scale,
// interpolated in OKLCH (INV-CLR-007). The arc colour is a live function of
// `value`; the two ticks mark the I-5 gate thresholds (0.70 / 0.80); the zone
// label is the non-colour channel (INV-CLR-011).
const ZONE_LABEL = {
  low: "Below gate",
  escalation: "Escalation",
  autonomous: "Autonomous",
};

function polar(cx, cy, r, fraction) {
  const angle = (-90 + 360 * fraction) * (Math.PI / 180);
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

export default function ConfidenceGauge({ value = 0, size = 108, label = true }) {
  const { theme } = useTheme();
  const v = Math.min(1, Math.max(0, value));
  const pct = Math.round(v * 100);
  const zone = confidenceZone(v);
  const color = confidenceColor(v, theme);

  const stroke = 9;
  const c = size / 2;
  const r = c - stroke;
  const circ = 2 * Math.PI * r;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
        aria-label={`Confidence ${pct} percent, ${ZONE_LABEL[zone]}`}>
        <circle cx={c} cy={c} r={r} fill="none" stroke="var(--color-border-subtle)" strokeWidth={stroke} />
        <circle
          cx={c}
          cy={c}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - v)}
          strokeLinecap="round"
          transform={`rotate(-90 ${c} ${c})`}
          style={{ filter: `drop-shadow(0 0 5px ${color})`, transition: "stroke-dashoffset var(--motion-duration-slow) var(--motion-ease-decelerate)" }}
        />
        {[CONFIDENCE_GATE.low, CONFIDENCE_GATE.high].map((g) => {
          const [x1, y1] = polar(c, c, r - stroke / 2 - 1, g);
          const [x2, y2] = polar(c, c, r + stroke / 2 + 1, g);
          return (
            <line key={g} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="var(--color-text-primary)" strokeWidth={1.5} opacity={0.65} />
          );
        })}
        <text x="50%" y="48%" dominantBaseline="central" textAnchor="middle"
          fill={color} fontSize={size * 0.26} fontWeight="700">
          {pct}
        </text>
        <text x="50%" y="64%" dominantBaseline="central" textAnchor="middle"
          fill="var(--color-text-tertiary)" fontSize={size * 0.1} fontWeight="600">
          PERCENT
        </text>
      </svg>
      {label && (
        <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color }}>
          {ZONE_LABEL[zone]}
        </span>
      )}
    </div>
  );
}
