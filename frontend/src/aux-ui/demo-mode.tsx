import { useUIStore } from "@/app/store/uiStore";
import { useSound } from "@/aux-ui/sound";
import { useReducedMotion } from "@/ui/hooks/useReducedMotion";
import { cn } from "@/ui/lib/cn";
import { ChevronRight, Pause, Play, X } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

/**
 * Demo Mode (plan section 6.3) — a cinematic presentation layer over the
 * real interface. It walks the canonical five-segment SYNAPSE narrative,
 * auto-navigating surfaces. Not a mock: it drives the real surfaces.
 */

interface Segment {
  readonly index: number;
  readonly title: string;
  readonly narration: string;
  readonly route: string;
  readonly durationMs: number;
}

const SEGMENTS: readonly Segment[] = [
  {
    index: 1,
    title: "The Living Map",
    narration:
      "Twenty-five dark stores across the city, each a node in a living network. Order flow pulses between them in real time.",
    route: "/",
    durationMs: 10_000,
  },
  {
    index: 2,
    title: "IPL Demand Signal",
    narration:
      "A cricket match begins. Demand for snacks and beverages surges 3–5×. The Demand Prophet sees it coming.",
    route: "/theater",
    durationMs: 11_000,
  },
  {
    index: 3,
    title: "Disruption Injection",
    narration:
      "A warehouse goes offline. The digital twin diverges from reality — the Disruption Shield retrieves a recovery playbook.",
    route: "/twin",
    durationMs: 11_000,
  },
  {
    index: 4,
    title: "Five-Phase Consensus",
    narration:
      "Eight agents propose, debate and arbitrate. A Pareto front is computed; the knee solution is selected under conflict.",
    route: "/theater",
    durationMs: 12_000,
  },
  {
    index: 5,
    title: "Evidence & Audit Trail",
    narration:
      "Every decision is replayable with perfect fidelity. The audit row is immutable, tamper-evident, and provable.",
    route: "/replay",
    durationMs: 11_000,
  },
];

export function DemoOverlay() {
  const active = useUIStore((s) => s.demoMode);
  const setDemoMode = useUIStore((s) => s.setDemoMode);
  const navigate = useNavigate();
  const { play } = useSound();
  const reduced = useReducedMotion();
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(true);

  const exit = useCallback(() => {
    setDemoMode(false);
    setStep(0);
    setPlaying(true);
  }, [setDemoMode]);

  // Navigate to the current segment's surface.
  useEffect(() => {
    if (!active) return;
    const segment = SEGMENTS[step];
    if (segment) {
      navigate(segment.route);
      play("phase");
    }
  }, [active, step, navigate, play]);

  // Auto-advance.
  useEffect(() => {
    if (!active || !playing) return;
    const segment = SEGMENTS[step];
    if (!segment) return;
    const timer = setTimeout(() => {
      setStep((s) => (s + 1 < SEGMENTS.length ? s + 1 : s));
      if (step + 1 >= SEGMENTS.length) setPlaying(false);
    }, segment.durationMs);
    return () => clearTimeout(timer);
  }, [active, playing, step]);

  // Escape exits.
  useEffect(() => {
    if (!active) return;
    function onKey(e: KeyboardEvent): void {
      if (e.key === "Escape") exit();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, exit]);

  if (!active) return null;
  const segment = SEGMENTS[step];
  if (!segment) return null;
  const atEnd = step + 1 >= SEGMENTS.length;

  return (
    <motion.div
      className="fixed inset-x-0 bottom-0 z-hailer"
      initial={reduced ? false : { y: 80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 240, damping: 28 }}
    >
      <div className="mx-auto mb-4 max-w-3xl rounded-xl border border-line-strong bg-elevated/95 shadow-overlay backdrop-blur">
        <div className="flex items-start gap-4 px-5 py-4">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-sig-think/40 bg-sig-think/12 font-display text-sm font-semibold text-sig-think">
            {segment.index}
          </div>
          <div className="flex flex-1 flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="font-display text-2xs font-semibold uppercase tracking-[0.16em] text-sig-think">
                Demo · Segment {segment.index} of {SEGMENTS.length}
              </span>
            </div>
            <h2 className="font-display text-base font-semibold text-ink-primary">
              {segment.title}
            </h2>
            <p className="text-xs leading-relaxed text-ink-secondary">
              {segment.narration}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              className="inline-flex size-7 items-center justify-center rounded-sm text-ink-hint hover:bg-membrane hover:text-ink-primary"
              aria-label={playing ? "Pause demo" : "Resume demo"}
            >
              {playing ? <Pause size={14} /> : <Play size={14} />}
            </button>
            <button
              type="button"
              onClick={() => {
                if (atEnd) exit();
                else setStep((s) => s + 1);
              }}
              className="inline-flex size-7 items-center justify-center rounded-sm text-ink-hint hover:bg-membrane hover:text-ink-primary"
              aria-label={atEnd ? "Finish demo" : "Next segment"}
            >
              <ChevronRight size={15} />
            </button>
            <button
              type="button"
              onClick={exit}
              className="inline-flex size-7 items-center justify-center rounded-sm text-ink-hint hover:bg-membrane hover:text-ink-primary"
              aria-label="Exit demo"
            >
              <X size={14} />
            </button>
          </div>
        </div>
        {/* Segment progress */}
        <div className="flex gap-1 px-5 pb-3">
          {SEGMENTS.map((s) => (
            <div
              key={s.index}
              className={cn(
                "h-0.5 flex-1 rounded-full",
                s.index <= segment.index ? "bg-sig-think" : "bg-membrane",
              )}
            />
          ))}
        </div>
      </div>
    </motion.div>
  );
}
