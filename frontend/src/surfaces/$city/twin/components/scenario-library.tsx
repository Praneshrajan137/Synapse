/**
 * SYNAPSE Atlas Console — saved scenario library panel.
 *
 * Lists Zustand-backed saved scenarios; click "Load" to push the
 * scenario back into the URL search-params (Twin Studio's input is
 * URL-driven, so loading is a navigation).
 */
import { memo } from "react";

import { Button } from "@shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";

import type { SavedScenario, ScenarioInput } from "../model/scenario";

export interface ScenarioLibraryProps {
  readonly scenarios: readonly SavedScenario[];
  readonly onLoad: (input: ScenarioInput) => void;
  readonly onRemove: (id: string) => void;
}

export const ScenarioLibrary = memo(function ScenarioLibrary({
  scenarios,
  onLoad,
  onRemove,
}: ScenarioLibraryProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-ops-base">Saved scenarios</CardTitle>
      </CardHeader>
      <CardContent>
        {scenarios.length === 0 ? (
          <p className="text-ops-sm text-muted-fg">
            No saved scenarios yet. Hit "Save scenario" after a run.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {scenarios.map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-center gap-2 rounded border border-border/60 bg-bg/40 p-2 text-ops-sm"
              >
                <span className="font-medium">{s.label}</span>
                <time
                  dateTime={s.createdAt}
                  className="text-ops-xs text-muted-fg"
                >
                  {new Date(s.createdAt).toLocaleString("en-IN", {
                    timeZone: "Asia/Kolkata",
                    hour12: false,
                  })}
                </time>
                <div className="ml-auto flex gap-1">
                  <Button size="sm" variant="outline" onClick={() => onLoad(s.input)}>
                    Load
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => onRemove(s.id)}>
                    Remove
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
});
