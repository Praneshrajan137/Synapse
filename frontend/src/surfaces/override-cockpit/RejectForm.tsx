import { Button } from "@ds/primitives";
import { type FormEvent, useId, useState } from "react";

interface RejectFormProps {
  readonly onCancel: () => void;
  readonly onSubmit: (payload: { action: "rejected"; reason: string }) => void;
  readonly pending?: boolean;
}

/** Reject form — reason is mandatory (audit trail compliance). */
export function RejectForm({ onCancel, onSubmit, pending }: RejectFormProps) {
  const [reason, setReason] = useState("");
  // Programmatic error association (Req 9.7): an empty submit marks the field
  // invalid and points assistive tech at the text error via aria-describedby.
  const [error, setError] = useState<string | null>(null);
  const errorId = useId();

  return (
    <form
      onSubmit={(e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!reason.trim()) {
          setError("A reason is required to reject a proposal.");
          return;
        }
        setError(null);
        onSubmit({ action: "rejected", reason: reason.trim() });
      }}
      className="space-y-3"
      aria-label="Reject reason form"
    >
      <label className="block">
        <span className="block text-2xs uppercase tracking-wide text-ink-muted">
          Reason for rejection
        </span>
        <textarea
          value={reason}
          onChange={(e) => {
            setReason(e.target.value);
            if (error && e.target.value.trim()) setError(null);
          }}
          rows={4}
          required
          maxLength={4000}
          placeholder="why is the proposed action being rejected?"
          aria-invalid={error !== null}
          aria-describedby={error ? errorId : undefined}
          className="mt-1 block w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus-visible:shadow-focus focus-visible:outline-none aria-[invalid=true]:border-signal-danger"
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
        <Button type="submit" variant="danger" disabled={pending || !reason.trim()}>
          {pending ? "Committing…" : "Commit reject"}
        </Button>
      </div>
    </form>
  );
}
