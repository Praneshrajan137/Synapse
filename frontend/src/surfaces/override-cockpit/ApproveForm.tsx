import { useState, type FormEvent } from "react";
import { Button } from "@ds/primitives";

interface ApproveFormProps {
  readonly requireReason?: boolean;
  readonly onCancel: () => void;
  readonly onSubmit: (payload: { action: "approved"; reason: string }) => void;
  readonly pending?: boolean;
}

/**
 * Approve form. When `requireReason` (sub-threshold confidence), reason is
 * mandatory; otherwise it's optional but recommended.
 */
export function ApproveForm({ requireReason, onCancel, onSubmit, pending }: ApproveFormProps) {
  const [reason, setReason] = useState(requireReason ? "" : "operator approved");
  return (
    <form
      onSubmit={(e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const value = reason.trim();
        if (requireReason && !value) return;
        onSubmit({ action: "approved", reason: value || "operator approved" });
      }}
      className="space-y-3"
      aria-label="Approve confirmation form"
    >
      <label className="block">
        <span className="block text-2xs uppercase tracking-wide text-ink-muted">
          Approval rationale {requireReason && <span className="text-confidence-risk">*</span>}
        </span>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          maxLength={4000}
          required={requireReason}
          className="mt-1 block w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus-visible:shadow-focus focus-visible:outline-none"
        />
      </label>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={pending}>
          Cancel
        </Button>
        <Button type="submit" variant="success" disabled={pending}>
          {pending ? "Committing…" : "Commit approve"}
        </Button>
      </div>
    </form>
  );
}
