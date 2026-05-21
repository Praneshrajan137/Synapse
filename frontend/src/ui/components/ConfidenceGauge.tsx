import { useReducedMotion } from "@/ui/hooks/useReducedMotion";
import { confidenceColor } from "@/ui/tokens";
import { motion } from "motion/react";

/**
 * ConfidenceGauge — a circular ring meter for a decision's confidence.
 *
 * Tenet T-4: a single number is a lie. Below the high-confidence
 * threshold the ring *breathes* — a slow scale modulation whose presence
 * itself signals "this value is uncertain, attend to it". Fully
 * confident gauges are still. Reduced-motion disables the breathing.
 */

export interface ConfidenceGaugeProps {
  /** Confidence in [0, 1]. */
  value: number;
  /** Pixel diameter. */
  size?: number;
  /** Show the numeric percentage in the center. */
  showValue?: boolean;
  /** Accessible label. */
  label?: string;
  className?: string;
}

/** At or above this, the decision is confident and the gauge is still. */
const STILL_THRESHOLD = 0.75;

export function ConfidenceGauge({
  value,
  size = 64,
  showValue = true,
  label,
  className,
}: ConfidenceGaugeProps) {
  const reducedMotion = useReducedMotion();
  const clamped = Math.min(1, Math.max(0, value));
  const color = confidenceColor(clamped);
  const stroke = Math.max(3, size * 0.08);
  const radius = (size - stroke) / 2;
  const breathing = clamped < STILL_THRESHOLD && !reducedMotion;

  return (
    <div
      className={className}
      role="meter"
      aria-valuenow={Number(clamped.toFixed(2))}
      aria-valuemin={0}
      aria-valuemax={1}
      aria-label={label ?? `Confidence ${(clamped * 100).toFixed(0)} percent`}
      style={{ width: size, height: size, position: "relative" }}
    >
      <motion.svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ transformOrigin: "center" }}
        animate={breathing ? { scale: [1, 1.02, 1] } : { scale: 1 }}
        transition={
          breathing
            ? { duration: 2, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }
            : { duration: 0.2 }
        }
      >
        <title>{label ?? "Confidence"}</title>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-line-strong)"
          strokeWidth={stroke}
        />
        {/* Value arc — pathLength=1 lets us use the raw fraction. */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray="1 1"
          initial={false}
          animate={{ strokeDashoffset: 1 - clamped }}
          transition={{ type: "spring", stiffness: 120, damping: 24 }}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </motion.svg>
      {showValue && (
        <span
          className="tnum absolute inset-0 flex items-center justify-center font-mono font-semibold"
          style={{ color, fontSize: size * 0.26 }}
        >
          {(clamped * 100).toFixed(0)}
        </span>
      )}
    </div>
  );
}
