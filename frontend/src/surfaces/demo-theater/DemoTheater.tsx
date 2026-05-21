import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Badge } from "@ds/primitives";
import { cn } from "@lib/cn";
import { SEGMENTS, useDemoRun, type DemoSegmentId } from "./useDemoRun";
import { useArtifact } from "./useArtifact";

const SEGMENT_LABEL_KEY: Record<DemoSegmentId, string> = {
  "01_living_map": "segments.living_map",
  "02_ipl_signal": "segments.ipl_signal",
  "03_disruption": "segments.disruption",
  "04_debate": "segments.debate",
  "05_evidence": "segments.evidence",
};

const SEGMENT_SUMMARY_KEY: Record<DemoSegmentId, string> = {
  "01_living_map": "Stores, SKUs, zones — the scale of the network before perturbation.",
  "02_ipl_signal": "3–5× demand multiplier hits snacks/beverages/dairy across 8 stores.",
  "03_disruption": "Monsoon flood / warehouse offline / supplier default — agents react.",
  "04_debate": "Tier 3 consensus: 4 proposals, Pareto arbitration, audit_id stamped.",
  "05_evidence": "Audit immutability • twin KL divergence • MLflow convergence speedup.",
};

export function DemoTheater() {
  const { t } = useTranslation("demo-theater");
  const demo = useDemoRun();
  const [selected, setSelected] = useState<DemoSegmentId>("01_living_map");

  // Auto-follow the current segment as the BE streams progress.
  useEffect(() => {
    if (demo.currentSegment) setSelected(demo.currentSegment);
  }, [demo.currentSegment]);

  // Keyboard 1-5 scrubs segments (FE-P10).
  useEffect(() => {
    function onKey(ev: KeyboardEvent) {
      const target = ev.target;
      if (target instanceof HTMLElement && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      const idx = Number(ev.key);
      if (idx >= 1 && idx <= SEGMENTS.length) {
        const next = SEGMENTS[idx - 1];
        if (next) setSelected(next);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const artifact = useArtifact(demo.jobId, selected);

  return (
    <section className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-0.5">
          <h1 className="text-2xl font-semibold text-ink">{t("title")}</h1>
          <p className="text-sm text-ink-muted">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          {demo.running ? (
            <>
              <Badge tone="info">running</Badge>
              <Button variant="ghost" size="sm" onClick={() => void demo.cancel()}>
                {t("controls.cancel")}
              </Button>
            </>
          ) : (
            <Button variant="primary" size="md" onClick={() => void demo.start()}>
              {t("controls.run")}
            </Button>
          )}
        </div>
      </header>

      {demo.error && (
        <div role="alert" className="syn-card border-l-4 border-confidence-risk p-3 text-sm text-confidence-risk">
          {demo.error}
        </div>
      )}

      <ol aria-label="Demo segments" className="flex flex-wrap gap-2 rounded-md bg-surface-raised p-1">
        {SEGMENTS.map((id, i) => {
          const isActive = id === selected;
          const isCurrent = id === demo.currentSegment;
          return (
            <li key={id}>
              <button
                type="button"
                onClick={() => setSelected(id)}
                aria-current={isActive ? "step" : undefined}
                aria-keyshortcuts={`${i + 1}`}
                className={cn(
                  "rounded px-3 py-1.5 text-xs font-medium transition-colors duration-fast ease-standard",
                  "focus-visible:outline-none focus-visible:shadow-focus",
                  isActive ? "bg-accent text-ink-inverse" : "text-ink-muted hover:text-ink",
                  isCurrent && !isActive && "ring-1 ring-accent",
                )}
              >
                <span className="mr-1.5 font-mono text-2xs tabular-nums opacity-70">{i + 1}</span>
                {t(SEGMENT_LABEL_KEY[id])}
              </button>
            </li>
          );
        })}
      </ol>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="syn-card-raised space-y-3 p-5">
          <h2 className="text-lg font-semibold text-ink">{t(SEGMENT_LABEL_KEY[selected])}</h2>
          <p className="text-sm text-ink-muted">{SEGMENT_SUMMARY_KEY[selected]}</p>
          {demo.logs.length > 0 && (
            <details className="text-xs text-ink-muted" open={demo.running}>
              <summary className="cursor-pointer text-sm font-medium text-ink">Live log</summary>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono text-2xs">
                {demo.logs.join("\n")}
              </pre>
            </details>
          )}
        </div>

        <aside aria-label={t("evidence.header")} className="syn-card-raised space-y-2 p-4">
          <h2 className="text-sm font-semibold text-ink">{t("evidence.header")}</h2>
          {artifact.isLoading && (
            <p className="text-xs text-ink-muted">{t("evidence.waiting")}</p>
          )}
          {artifact.isError && (
            <p className="text-xs text-confidence-risk">
              {(artifact.error as Error).message}
            </p>
          )}
          {artifact.data && (
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-surface-sunken p-2 font-mono text-2xs text-ink">
              {JSON.stringify(artifact.data.body, null, 2)}
            </pre>
          )}
        </aside>
      </div>
    </section>
  );
}
