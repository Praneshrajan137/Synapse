/**
 * SYNAPSE Atlas Console — Modify form (Mission Control).
 *
 * Opens when the operator chooses "Modify" instead of approving the
 * orchestrator's recommendation. Output is a partial action override
 * the orchestrator applies before execution.
 *
 * S3 ships the generic shape (price multiplier + reorder quantity +
 * free-text reason). Surface-specific fields land alongside their
 * parent surfaces in S4/S5 (pricing-oracle modifications, route-leg
 * overrides, etc.).
 */
import { useId } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";

const ModifyFormSchema = z.object({
  price_multiplier: z.coerce.number().min(0).max(2).optional(),
  reorder_quantity: z.coerce.number().int().min(0).max(10_000).optional(),
  reason: z.string().min(1).max(500),
});
export type ModifyFormValues = z.infer<typeof ModifyFormSchema>;

export interface ModifyFormProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly onSubmit: (values: ModifyFormValues) => void;
  readonly decisionIdLabel: string;
}

export function ModifyForm({ open, onOpenChange, onSubmit, decisionIdLabel }: ModifyFormProps) {
  const { t } = useTranslation();
  const formId = useId();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<ModifyFormValues>({
    resolver: zodResolver(ModifyFormSchema),
    defaultValues: { reason: "" },
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) reset();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("missionControl.escalation.modify")}</DialogTitle>
          <DialogDescription className="font-mono text-ops-xs">{decisionIdLabel}</DialogDescription>
        </DialogHeader>

        <form
          id={formId}
          onSubmit={handleSubmit((values) => {
            onSubmit(values);
            onOpenChange(false);
            reset();
          })}
          className="space-y-3"
          noValidate
        >
          <Field
            label="Price multiplier"
            id={`${formId}-mul`}
            error={errors.price_multiplier?.message}
          >
            <input
              id={`${formId}-mul`}
              type="number"
              step="0.01"
              min={0}
              max={2}
              {...register("price_multiplier")}
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-ops-base text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </Field>
          <Field
            label="Reorder quantity"
            id={`${formId}-qty`}
            error={errors.reorder_quantity?.message}
          >
            <input
              id={`${formId}-qty`}
              type="number"
              min={0}
              {...register("reorder_quantity")}
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-ops-base text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </Field>
          <Field
            label="Reason (audit-trailed)"
            id={`${formId}-reason`}
            error={errors.reason?.message}
            required
          >
            <textarea
              id={`${formId}-reason`}
              rows={3}
              {...register("reason")}
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-ops-base text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </Field>
        </form>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" form={formId} disabled={isSubmitting}>
            {t("common.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  id,
  label,
  required,
  error,
  children,
}: {
  id: string;
  label: string;
  required?: boolean;
  error?: string | undefined;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-ops-sm text-muted-fg">
        {label}
        {required && <span className="ml-1 text-safety-critical">*</span>}
      </label>
      {children}
      {error && (
        <p role="alert" className="mt-1 text-ops-xs text-safety-critical">
          {error}
        </p>
      )}
    </div>
  );
}
