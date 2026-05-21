import { useUIStore } from "@/app/store/uiStore";
import { useSound } from "@/aux-ui/sound";
import { CITIES, CITY_LABEL } from "@/domain/city";
import { cn } from "@/ui/lib/cn";
import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import {
  Clapperboard,
  Gauge,
  MapPin,
  PanelLeft,
  PanelRight,
  Sliders,
  Volume2,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { SURFACES } from "./navigation";

/**
 * Command Palette (⌘K) — the primary navigation surface (tenet T-11).
 *
 * Fuzzy search over surfaces, view actions and city scope. Phases 4+
 * extend it with decision lookup and "/jump" verbs.
 */

const itemClass = cn(
  "flex cursor-pointer items-center gap-3 rounded-md px-2.5 py-2 text-xs text-ink-secondary",
  "data-[selected=true]:bg-elevated data-[selected=true]:text-ink-primary",
);

export function CommandPalette() {
  const open = useUIStore((s) => s.commandOpen);
  const setOpen = useUIStore((s) => s.setCommandOpen);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const toggleFeed = useUIStore((s) => s.toggleFeed);
  const cycleDensity = useUIStore((s) => s.cycleDensity);
  const setSoundEnabled = useUIStore((s) => s.setSoundEnabled);
  const soundEnabled = useUIStore((s) => s.soundEnabled);
  const setCity = useUIStore((s) => s.setCity);
  const setDemoMode = useUIStore((s) => s.setDemoMode);
  const navigate = useNavigate();
  const { play } = useSound();

  function run(action: () => void): void {
    action();
    setOpen(false);
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-command bg-void/70 backdrop-blur-sm" />
        <Dialog.Content
          aria-label="Command palette"
          className={cn(
            "fixed left-1/2 top-[14vh] z-command w-[min(36rem,92vw)] -translate-x-1/2",
            "overflow-hidden rounded-lg border border-line-strong bg-elevated shadow-overlay",
            "focus-visible:outline-none",
          )}
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Dialog.Description className="sr-only">
            Search surfaces, view actions and city scope.
          </Dialog.Description>

          <Command label="Command palette" className="flex flex-col">
            <Command.Input
              autoFocus
              placeholder="Search surfaces, actions, decisions…"
              className={cn(
                "h-12 w-full border-b border-line-faint bg-transparent px-4 text-sm",
                "text-ink-primary placeholder:text-ink-hint focus-visible:outline-none",
              )}
            />
            <Command.List className="max-h-80 overflow-y-auto p-1.5">
              <Command.Empty className="px-3 py-6 text-center text-xs text-ink-hint">
                No matches.
              </Command.Empty>

              <Command.Group
                heading="Surfaces"
                className="[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:font-display [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-ink-hint"
              >
                {SURFACES.map((surface) => {
                  const Icon = surface.icon;
                  return (
                    <Command.Item
                      key={surface.id}
                      value={`${surface.label} ${surface.description}`}
                      onSelect={() => run(() => navigate(surface.route))}
                      className={itemClass}
                    >
                      <Icon size={16} className="text-ink-hint" aria-hidden="true" />
                      <span className="flex-1">
                        <span className="text-ink-primary">{surface.label}</span>
                        <span className="ml-2 text-ink-hint">{surface.description}</span>
                      </span>
                      {surface.status === "construction" && (
                        <span className="text-2xs text-sig-warn">
                          Phase {surface.phase}
                        </span>
                      )}
                    </Command.Item>
                  );
                })}
              </Command.Group>

              <Command.Group
                heading="View"
                className="[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:font-display [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-ink-hint"
              >
                <Command.Item
                  value="toggle sidebar"
                  onSelect={() => run(toggleSidebar)}
                  className={itemClass}
                >
                  <PanelLeft size={16} className="text-ink-hint" aria-hidden="true" />
                  Toggle sidebar
                </Command.Item>
                <Command.Item
                  value="toggle synaptic feed"
                  onSelect={() => run(toggleFeed)}
                  className={itemClass}
                >
                  <PanelRight size={16} className="text-ink-hint" aria-hidden="true" />
                  Toggle Synaptic Feed
                </Command.Item>
                <Command.Item
                  value="cycle density"
                  onSelect={() => run(cycleDensity)}
                  className={itemClass}
                >
                  <Gauge size={16} className="text-ink-hint" aria-hidden="true" />
                  Cycle information density
                </Command.Item>
                <Command.Item
                  value="toggle sound cues"
                  onSelect={() =>
                    run(() => {
                      const next = !soundEnabled;
                      setSoundEnabled(next);
                      if (next) play("confirm");
                    })
                  }
                  className={itemClass}
                >
                  <Volume2 size={16} className="text-ink-hint" aria-hidden="true" />
                  {soundEnabled ? "Disable sound cues" : "Enable sound cues"}
                </Command.Item>
                <Command.Item
                  value="open steering governance"
                  onSelect={() => run(() => navigate("/steering"))}
                  className={itemClass}
                >
                  <Sliders size={16} className="text-ink-hint" aria-hidden="true" />
                  Open Steering
                </Command.Item>
                <Command.Item
                  value="start cinematic demo"
                  onSelect={() => run(() => setDemoMode(true))}
                  className={itemClass}
                >
                  <Clapperboard size={16} className="text-ink-hint" aria-hidden="true" />
                  Start cinematic demo
                </Command.Item>
              </Command.Group>

              <Command.Group
                heading="City scope"
                className="[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:font-display [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-ink-hint"
              >
                {CITIES.map((c) => (
                  <Command.Item
                    key={c}
                    value={`switch city ${CITY_LABEL[c]}`}
                    onSelect={() => run(() => setCity(c))}
                    className={itemClass}
                  >
                    <MapPin size={16} className="text-ink-hint" aria-hidden="true" />
                    Switch to {CITY_LABEL[c]}
                  </Command.Item>
                ))}
              </Command.Group>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
