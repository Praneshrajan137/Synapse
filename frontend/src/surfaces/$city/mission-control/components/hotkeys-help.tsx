/**
 * SYNAPSE Atlas Console — Mission Control hotkeys help dialog.
 *
 * Triggered by `?`. Lists every hotkey the surface owns so the
 * keyboard-first contract from plan §5.2 is discoverable.
 */
import { useTranslation } from "react-i18next";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";

interface HotkeysHelpProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
}

const ROWS: ReadonlyArray<{ keys: string; i18nKey: string }> = [
  { keys: "j / ↓", i18nKey: "missionControl.hotkeys.next" },
  { keys: "k / ↑", i18nKey: "missionControl.hotkeys.prev" },
  { keys: "Enter", i18nKey: "missionControl.hotkeys.approve" },
  { keys: "r", i18nKey: "missionControl.hotkeys.reject" },
  { keys: "m", i18nKey: "missionControl.hotkeys.modify" },
  { keys: "Esc", i18nKey: "missionControl.escalation.modify" },
  { keys: "?", i18nKey: "missionControl.hotkeys.help" },
];

export function HotkeysHelp({ open, onOpenChange }: HotkeysHelpProps) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("missionControl.hotkeys.help")}</DialogTitle>
          <DialogDescription>
            {t("missionControl.title")} —{" "}
            <span className="font-mono text-ops-xs">
              keyboard-first ops shortcuts
            </span>
          </DialogDescription>
        </DialogHeader>
        <table className="mt-2 w-full border-collapse text-ops-sm">
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.keys} className="border-b border-border last:border-0">
                <td className="py-2 pr-4 font-mono text-ops-sm">
                  <kbd className="rounded border border-border bg-muted px-2 py-0.5 text-ops-xs">
                    {row.keys}
                  </kbd>
                </td>
                <td className="py-2 text-muted-fg">{t(row.i18nKey)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </DialogContent>
    </Dialog>
  );
}
