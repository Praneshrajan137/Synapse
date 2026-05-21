import { useSubmitOverride } from "@/application/decisions";
import { useVoicePTT } from "@/aux-ui/voice";
import type { Escalation, HumanOverride } from "@/domain/decision";
import { cn } from "@/ui/lib/cn";
import { signed } from "@/ui/lib/format";
import { Button, Card, CardBody, CardHeader, CardTitle } from "@/ui/primitives";
import { signal } from "@/ui/tokens";
import { Check, Mic, MicOff, Pencil, X } from "lucide-react";
import { useEffect, useId, useMemo, useState } from "react";

/**
 * CounterfactualPanel — the operator's instrument.
 *
 * Approve / Reject / Modify, each requiring a non-empty reason
 * (UI-COUNCIL-002). The reason can be dictated via local voice PTT
 * (section 6.2). A twin pre-simulation previews the KPI deltas of
 * approving the recommended action.
 */

type Choice = HumanOverride["action"];

const CHOICES: {
  value: Choice;
  label: string;
  icon: typeof Check;
  variant: "signal" | "danger" | "secondary";
}[] = [
  { value: "approved", label: "Approve", icon: Check, variant: "signal" },
  { value: "rejected", label: "Reject", icon: X, variant: "danger" },
  { value: "modified", label: "Modify", icon: Pencil, variant: "secondary" },
];

interface KpiDelta {
  label: string;
  value: number;
  unit: string;
  goodWhenPositive: boolean;
}

export interface CounterfactualPanelProps {
  escalation: Escalation;
  onResolved?: () => void;
  className?: string;
}

export function CounterfactualPanel({
  escalation,
  onResolved,
  className,
}: CounterfactualPanelProps) {
  const reasonId = useId();
  const [choice, setChoice] = useState<Choice | null>(null);
  const [reason, setReason] = useState("");
  const voice = useVoicePTT();
  const override = useSubmitOverride();

  // Dictation drives the reason field while recording.
  useEffect(() => {
    if (voice.recording && voice.transcript) setReason(voice.transcript);
  }, [voice.recording, voice.transcript]);

  // Twin pre-simulation — deterministic preview of approving the action.
  const deltas = useMemo<KpiDelta[]>(() => {
    const c = escalation.decision.confidence;
    return [
      { label: "Fill rate", value: (c - 0.5) * 4, unit: "pp", goodWhenPositive: true },
      {
        label: "Waste rate",
        value: -(c - 0.45) * 2.4,
        unit: "pp",
        goodWhenPositive: false,
      },
      {
        label: "Margin",
        value: Math.round((c - 0.4) * 5200),
        unit: "₹",
        goodWhenPositive: true,
      },
    ];
  }, [escalation.decision.confidence]);

  const canSubmit = choice !== null && reason.trim().length > 0 && !override.isPending;

  function submit(): void {
    if (!choice) return;
    override.mutate(
      {
        decisionId: escalation.decision.id,
        request: { action: choice, reason: reason.trim(), operator: "operator" },
      },
      { onSuccess: () => onResolved?.() },
    );
  }

  if (override.isSuccess) {
    return (
      <Card tone="elevated" className={cn("flex flex-col", className)}>
        <CardBody className="flex flex-1 flex-col items-center justify-center gap-2 py-10 text-center">
          <Check size={28} className="text-sig-ok" aria-hidden="true" />
          <p className="text-sm text-ink-primary">Override recorded</p>
          <p className="text-2xs text-ink-hint">Logged to the immutable audit trail.</p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card tone="elevated" className={cn("flex flex-col", className)}>
      <CardHeader>
        <CardTitle>Counterfactual</CardTitle>
      </CardHeader>
      <CardBody className="flex flex-col gap-3">
        {/* Twin pre-simulation */}
        <div>
          <h4 className="mb-1.5 font-display text-2xs font-semibold uppercase tracking-[0.1em] text-ink-hint">
            Twin pre-simulation · 30 scenarios
          </h4>
          <ul className="flex flex-col gap-1">
            {deltas.map((delta) => {
              const favorable = delta.goodWhenPositive
                ? delta.value > 0
                : delta.value < 0;
              return (
                <li
                  key={delta.label}
                  className="flex items-center justify-between text-2xs"
                >
                  <span className="text-ink-secondary">{delta.label}</span>
                  <span
                    className="tnum font-mono"
                    style={{ color: favorable ? signal.ok : signal.stop }}
                  >
                    {delta.unit === "₹" ? "₹" : ""}
                    {signed(delta.value, delta.unit === "₹" ? 0 : 1)}
                    {delta.unit !== "₹" ? ` ${delta.unit}` : ""}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Choice */}
        <div
          className="flex gap-2"
          // biome-ignore lint/a11y/useSemanticElements: a toggle-button group, not a form fieldset
          role="group"
          aria-label="Override decision"
        >
          {CHOICES.map((c) => {
            const Icon = c.icon;
            const active = choice === c.value;
            return (
              <Button
                key={c.value}
                size="sm"
                variant={active ? c.variant : "secondary"}
                onClick={() => setChoice(c.value)}
                aria-pressed={active}
                className="flex-1"
              >
                <Icon size={13} aria-hidden="true" />
                {c.label}
              </Button>
            );
          })}
        </div>

        {/* Reason */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor={reasonId}
              className="font-display text-2xs font-semibold uppercase tracking-[0.1em] text-ink-hint"
            >
              Reason{" "}
              {voice.recording && <span className="text-sig-think">· listening</span>}
            </label>
            {voice.supported && (
              <button
                type="button"
                onClick={() => (voice.recording ? voice.stop() : voice.start())}
                className={cn(
                  "inline-flex size-6 items-center justify-center rounded-sm transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sig-live",
                  voice.recording
                    ? "bg-sig-think/20 text-sig-think"
                    : "text-ink-hint hover:bg-elevated hover:text-ink-secondary",
                )}
                aria-label={voice.recording ? "Stop dictation" : "Dictate reason"}
              >
                {voice.recording ? <MicOff size={13} /> : <Mic size={13} />}
              </button>
            )}
          </div>
          <textarea
            id={reasonId}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Why this decision is approved, rejected or modified…"
            className={cn(
              "w-full resize-none rounded-md border border-line-strong bg-void px-3 py-2",
              "text-xs text-ink-primary placeholder:text-ink-hint",
              "focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-sig-live",
            )}
          />
        </div>

        <Button variant="signal" disabled={!canSubmit} onClick={submit}>
          {override.isPending ? "Recording…" : "Submit override"}
        </Button>
        {override.isError && (
          <p className="text-2xs text-sig-stop">
            Submission failed — the decision was not overridden.
          </p>
        )}
      </CardBody>
    </Card>
  );
}
