/**
 * SYNAPSE Atlas Console — PII reauth gate dialog.
 *
 * Operator clicks "Reveal PII" → password prompt → BFF reauth → on
 * success the elevated_until window opens and the surface re-renders
 * with PII unredacted. The window is short-lived (5 min by default —
 * see `SYNAPSE_ELEVATION_TTL` in api/routers/auth.py).
 */
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";

export interface PiiGateProps {
  readonly open: boolean;
  readonly busy: boolean;
  readonly error: string | null;
  readonly onSubmit: (password: string) => Promise<void>;
  readonly onOpenChange: (open: boolean) => void;
}

export function PiiGate({ open, busy, error, onSubmit, onOpenChange }: PiiGateProps) {
  const { t } = useTranslation();
  const [password, setPassword] = useState("");

  async function handle(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    await onSubmit(password);
    setPassword("");
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) setPassword("");
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("auth.elevateForPii")}</DialogTitle>
          <DialogDescription>{t("auditVault.redactedNotice")}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handle} className="space-y-3" noValidate>
          <label className="block">
            <span className="mb-1 block text-ops-sm text-muted-fg">{t("auth.password")}</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-ops-base text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>
          {error && (
            <p role="alert" className="text-ops-sm text-safety-critical">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button variant="ghost" type="button" onClick={() => onOpenChange(false)} disabled={busy}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={busy || password.length === 0}>
              {busy ? t("common.loading") : t("common.confirm")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
