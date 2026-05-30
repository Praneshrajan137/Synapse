import { type PulseSignal, PulseSonifier } from "@lib/sonification";
import { useEffect, useRef } from "react";

/**
 * Drives the ambient {@link PulseSonifier} from a live pulse signal. OFF unless
 * `enabled` is true (which should itself originate from a user gesture — the
 * toggle click — to satisfy Web Audio autoplay policy). Retunes live as the
 * signal changes; tears the audio context down on disable/unmount.
 *
 * Two effects with honest dependencies: one owns the audio lifecycle (keyed on
 * `enabled` only, so retuning never restarts the sound), the other pushes live
 * pitch/cadence updates (keyed on the primitive signal values).
 */
export function useSonification(signal: PulseSignal, enabled: boolean): void {
  const { rate, confidence } = signal;
  const ref = useRef<PulseSonifier | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const sonifier = new PulseSonifier();
    sonifier.start();
    ref.current = sonifier;
    return () => {
      sonifier.stop();
      ref.current = null;
    };
  }, [enabled]);

  useEffect(() => {
    ref.current?.update({ rate, confidence });
  }, [rate, confidence]);
}
