import { Button } from "@ds/primitives";
import { type FormEvent, useId, useState } from "react";

interface ModifyFormProps {
  readonly initialAction: Record<string, unknown>;
  readonly onCancel: () => void;
  readonly onSubmit: (action: {
    action: "modified";
    reason: string;
    modified_action: Record<string, unknown>;
  }) => void;
  readonly pending?: boolean;
}

/**
 * Modify form — operator edits the proposed action JSON and supplies a reason.
 *
 * P1 ships a controlled-JSON editor (free-form, validated as JSON) — the
 * full per-schema RHF + Zod renderer is scheduled for P3 once
 * `selected_action.action_type` is consistently populated across agents.
 */
export function ModifyForm({ initialAction, onCancel, onSubmit, pending }: ModifyFormProps) {
  const [text, setText] = useState(() => JSON.stringify(initialAction, null, 2));
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Which field the current error belongs to, so we can associate the text
  // error message with the invalid input via aria-describedby/aria-invalid
  // (Req 9.7). null = no error.
  const [errorField, setErrorField] = useState<"json" | "reason" | null>(null);
  const errorId = useId();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setErrorField(null);
    let parsed: Record<string, unknown>;
    try {
      const candidate: unknown = JSON.parse(text);
      if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
        throw new Error("modified action must be a JSON object");
      }
      parsed = candidate as Record<string, unknown>;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setErrorField("json");
      return;
    }
    if (!reason.trim()) {
      setError("reason is required");
      setErrorField("reason");
      return;
    }
    onSubmit({ action: "modified", reason: reason.trim(), modified_action: parsed });
  }

  const jsonInvalid = errorField === "json";
  const reasonInvalid = errorField === "reason";

  return (
    <form onSubmit={handleSubmit} className="space-y-3" aria-label="Modify action form">
      <label className="block">
        <span className="block text-2xs uppercase tracking-wide text-ink-muted">
          Modified action (JSON)
        </span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          spellCheck={false}
          aria-invalid={jsonInvalid}
          aria-describedby={jsonInvalid ? errorId : undefined}
          className="mt-1 block w-full rounded-md border border-border bg-surface-sunken px-2 py-1.5 font-mono text-xs text-ink focus-visible:shadow-focus focus-visible:outline-none aria-[invalid=true]:border-signal-danger"
        />
      </label>
      <label className="block">
        <span className="block text-2xs uppercase tracking-wide text-ink-muted">Reason</span>
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          required
          maxLength={4000}
          placeholder="why is the agent's proposal being modified?"
          aria-invalid={reasonInvalid}
          aria-describedby={reasonInvalid ? errorId : undefined}
          className="mt-1 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-ink placeholder:text-ink-subtle focus-visible:shadow-focus focus-visible:outline-none aria-[invalid=true]:border-signal-danger"
        />
      </label>
      {error && (
        <div id={errorId} role="alert" className="text-xs text-confidence-risk">
          {error}
        </div>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={pending}>
          Cancel
        </Button>
        <Button type="submit" variant="warning" disabled={pending}>
          {pending ? "Committing…" : "Commit modify"}
        </Button>
      </div>
    </form>
  );
}
