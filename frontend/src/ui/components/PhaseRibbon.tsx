import type { ConsensusPhase } from "@/domain/decision";
import { CONSENSUS_PHASES, PHASE_LABEL } from "@/domain/decision";
import { useReducedMotion } from "@/ui/hooks/useReducedMotion";
import { cn } from "@/ui/lib/cn";
import { motion } from "motion/react";

/**
 * PhaseRibbon — the five consensus phases as a sweeping progress rail.
 *
 * The current phase glows; completed phases settle to the success
 * signal. A latency-budget bar fills beneath the active phase (tenet
 * T-2 — latency shapes the interaction).
 */

export interface PhaseRibbonProps {
  current: ConsensusPhase;
  /** 0..1 progress within the current phase's latency budget. */
  budgetProgress?: number;
  className?: string;
}

export function PhaseRibbon({
  current,
  budgetProgress = 0,
  className,
}: PhaseRibbonProps) {
  const reduced = useReducedMotion();
  const currentIndex = CONSENSUS_PHASES.indexOf(current);

  return (
    <div
      className={cn("flex flex-col gap-1.5 px-4 py-3", className)}
      aria-label={`Consensus phase: ${PHASE_LABEL[current]}`}
    >
      <ol className="flex items-center">
        {CONSENSUS_PHASES.map((phase, index) => {
          const done = index < currentIndex;
          const active = index === currentIndex;
          const color = done
            ? "var(--color-sig-ok)"
            : active
              ? "var(--color-sig-think)"
              : "var(--color-ink-disabled)";
          return (
            <li key={phase} className="flex flex-1 items-center last:flex-none">
              <div className="flex flex-col items-center gap-1">
                <motion.span
                  className="size-2.5 rounded-full"
                  style={{ backgroundColor: color }}
                  animate={
                    active && !reduced
                      ? { boxShadow: [`0 0 0 0 ${color}`, "0 0 0 6px transparent"] }
                      : {}
                  }
                  transition={{ duration: 1.6, repeat: Number.POSITIVE_INFINITY }}
                />
                <span
                  className={cn(
                    "font-display text-2xs font-semibold uppercase tracking-[0.1em]",
                    active
                      ? "text-ink-primary"
                      : done
                        ? "text-ink-secondary"
                        : "text-ink-disabled",
                  )}
                >
                  {PHASE_LABEL[phase]}
                </span>
              </div>
              {index < CONSENSUS_PHASES.length - 1 && (
                <div className="mx-1 h-px flex-1 self-start" style={{ marginTop: 5 }}>
                  <div
                    className="h-full"
                    style={{
                      background: done
                        ? "var(--color-sig-ok)"
                        : "var(--color-line-strong)",
                    }}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {/* Latency budget bar */}
      <div className="h-0.5 overflow-hidden rounded-full bg-membrane">
        <div
          className="h-full rounded-full bg-sig-think transition-[width] duration-500"
          style={{ width: `${Math.min(100, Math.max(0, budgetProgress * 100))}%` }}
        />
      </div>
    </div>
  );
}
