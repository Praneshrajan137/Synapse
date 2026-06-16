import { ConsensusChoreography, PageHeader } from "@ds/compounds";
import { useDecisionQuery } from "@hooks/use-decision";
import { useCallback, useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

/**
 * Council Theater (ADR-051) — a flagship stage for the council's recorded
 * deliberation. Fetches one decision via the shared `useDecisionQuery` (the
 * same validated source the analyst Decision Theater detail uses, so the two
 * can never drift) and hands it to the ConsensusChoreography for a narrated,
 * motion-driven reconstruction of all five consensus phases.
 *
 * The surface owns the shareable `?phase=N` URL frame (FE-INV-028 spirit) and
 * passes it down; a shared link parks on that phase rather than auto-playing.
 * Route-split (lazy in router.tsx) so its motion/viz weight stays out of the
 * entry bundle (FE-INV-014/025).
 */
export function CouncilTheater() {
  const { id } = useParams<{ id: string }>();
  const query = useDecisionQuery(id);

  const [searchParams, setSearchParams] = useSearchParams();
  const phaseParam = useMemo(
    () => z.coerce.number().int().min(1).max(5).safeParse(searchParams.get("phase")),
    [searchParams],
  );
  const initialPhase = phaseParam.success ? phaseParam.data : undefined;

  const onPhaseChange = useCallback(
    (phase: number) => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev);
          params.set("phase", String(phase));
          return params;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const decision = query.data?.decision;
  const raw = query.data?.raw;

  return (
    <section className="space-y-5">
      <PageHeader
        size="hero"
        title="Council Theater"
        subtitle="Watch the eight-agent council deliberate — a narrated reconstruction of one recorded decision, phase by phase."
        status={
          <span className="rounded-sm bg-surface-raised px-2 py-0.5 text-2xs uppercase tracking-wide text-ink-muted">
            Recorded reconstruction
          </span>
        }
      >
        <Link
          to={id ? `/decisions/${id}` : "/decisions"}
          className="text-2xs text-ink-muted hover:text-ink"
        >
          ← Decision detail
        </Link>
      </PageHeader>

      {query.isLoading && <p className="text-sm text-ink-muted">Loading deliberation…</p>}

      {(query.isError || (!query.isLoading && !decision)) && (
        <div role="alert" className="text-sm text-confidence-risk">
          Decision unavailable: {(query.error as Error | undefined)?.message ?? "not found"}
          <div className="mt-2">
            <Link to="/decisions" className="text-2xs text-accent underline">
              Back to Decision Theater
            </Link>
          </div>
        </div>
      )}

      {decision && (
        <ConsensusChoreography
          decision={decision}
          raw={raw}
          initialPhase={initialPhase}
          autoPlay={initialPhase === undefined}
          onPhaseChange={onPhaseChange}
        />
      )}
    </section>
  );
}
