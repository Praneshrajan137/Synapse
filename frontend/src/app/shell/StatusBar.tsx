import { useUIStore } from "@/app/store/uiStore";
import { useHealth } from "@/application/system/useHealth";
import { useSound } from "@/aux-ui/sound";
import { CITIES, CITY_LABEL } from "@/domain/city";
import { cn } from "@/ui/lib/cn";
import { Kbd, Switch, Tooltip } from "@/ui/primitives";
import { PanelRight, Volume2, VolumeX } from "lucide-react";

/**
 * StatusBar — the always-on top strip.
 *
 * City scope, orchestrator health, information density, sound, the
 * Synaptic Feed toggle, and the command-palette affordance. Calm by
 * default (tenet T-7): nothing here moves unless something is wrong.
 */

const HEALTH_META = {
  online: { color: "var(--color-sig-ok)", label: "Orchestrator online" },
  offline: { color: "var(--color-sig-stop)", label: "Orchestrator offline" },
  connecting: { color: "var(--color-sig-warn)", label: "Connecting to orchestrator" },
} as const;

export function StatusBar() {
  const city = useUIStore((s) => s.city);
  const setCity = useUIStore((s) => s.setCity);
  const density = useUIStore((s) => s.density);
  const feedOpen = useUIStore((s) => s.feedOpen);
  const toggleFeed = useUIStore((s) => s.toggleFeed);
  const setCommandOpen = useUIStore((s) => s.setCommandOpen);
  const soundEnabled = useUIStore((s) => s.soundEnabled);
  const setSoundEnabled = useUIStore((s) => s.setSoundEnabled);
  const { play } = useSound();
  const { status } = useHealth();
  const health = HEALTH_META[status];

  return (
    <header
      className={cn(
        "z-statusbar flex h-8 shrink-0 items-center gap-3 border-b border-line-faint",
        "bg-paper px-3 text-2xs text-ink-secondary",
      )}
    >
      {/* City scope */}
      <div
        className="flex items-center gap-0.5 rounded-sm border border-line-faint p-0.5"
        // biome-ignore lint/a11y/useSemanticElements: a toggle-button group, not a form fieldset
        role="group"
        aria-label="Active city"
      >
        {CITIES.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setCity(c)}
            aria-pressed={city === c}
            className={cn(
              "rounded-xs px-2 py-0.5 font-medium transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sig-live",
              city === c
                ? "bg-elevated text-ink-primary"
                : "text-ink-hint hover:text-ink-secondary",
            )}
          >
            {CITY_LABEL[c]}
          </button>
        ))}
      </div>

      {/* Orchestrator health */}
      <Tooltip content={health.label}>
        <span className="flex items-center gap-1.5">
          <span
            className="size-2 rounded-full"
            style={{ backgroundColor: health.color }}
            aria-hidden="true"
          />
          <span className="text-ink-hint">{status}</span>
        </span>
      </Tooltip>

      <div className="flex-1" />

      {/* Density */}
      <Tooltip content="Information density — cycle with ⌘.">
        <span className="font-mono uppercase tracking-wide text-ink-hint">{density}</span>
      </Tooltip>

      {/* Sound */}
      <Tooltip content={soundEnabled ? "Sound cues on" : "Sound cues off"}>
        <span className="flex items-center gap-1.5">
          {soundEnabled ? (
            <Volume2 size={13} aria-hidden="true" />
          ) : (
            <VolumeX size={13} aria-hidden="true" />
          )}
          <Switch
            aria-label="Sound cues"
            checked={soundEnabled}
            onCheckedChange={(next) => {
              setSoundEnabled(next);
              if (next) play("confirm");
            }}
          />
        </span>
      </Tooltip>

      {/* Synaptic Feed toggle */}
      <Tooltip content={`${feedOpen ? "Hide" : "Show"} Synaptic Feed — ⌘/`}>
        <button
          type="button"
          onClick={toggleFeed}
          aria-pressed={feedOpen}
          aria-label="Toggle Synaptic Feed"
          className={cn(
            "rounded-xs p-1 transition-colors hover:bg-elevated",
            "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sig-live",
            feedOpen ? "text-sig-live" : "text-ink-hint",
          )}
        >
          <PanelRight size={14} aria-hidden="true" />
        </button>
      </Tooltip>

      {/* Command palette */}
      <button
        type="button"
        onClick={() => setCommandOpen(true)}
        className={cn(
          "flex items-center gap-1.5 rounded-sm border border-line-faint px-2 py-1",
          "text-ink-hint transition-colors hover:border-line-strong hover:text-ink-secondary",
          "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sig-live",
        )}
      >
        <span>Search</span>
        <Kbd keys={["⌘", "K"]} label="Open command palette" />
      </button>
    </header>
  );
}
