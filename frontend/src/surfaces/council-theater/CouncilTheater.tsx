import { ConsensusChoreography, PageHeader } from "@ds/compounds";
import { useDecisionQuery } from "@hooks/use-decision";
import { useOnlineStatus } from "@hooks/use-online-status";
import { parseSharedPhase } from "@lib/replay";
import { resolveUniversalState } from "@lib/universal-state";
import { useCallback, useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

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
  const initialPhase = useMemo(() => parseSharedPhase(searchParams.get("phase")), [searchParams]);

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

  // Route the single-decision fetch through the shared resolver so an offline
  // session is distinct from a load failure and from an in-flight load
  // (Req 10.1, 10.7). A missing decision after a completed, non-error fetch is
  // still surfaced as "unavailable" rather than a silent blank stage (Req 10.8).
  const offline = useOnlineStatus();
  const state = resolveUniversalState({
    isLoading: query.isLoading,
    isError: query.isError,
    isOffline: offline,
    isDegraded: false, // the global DegradedBanner owns degraded posture here
    itemCount: decision ? 1 : 0,
  });

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

      {state === "offline" && (
        <div role="alert" className="text-sm text-confidence-risk">
          You're offline — the recorded deliberation can't be loaded right now.
          <div className="mt-2">
            <Link to="/decisions" className="text-2xs text-accent underline">
              Back to Decision Theater
            </Link>
          </div>
        </div>
      )}

      {state === "loading" && <p className="text-sm text-ink-muted">Loading deliberation…</p>}

      {(state === "error" || state === "empty") && (
        <div role="alert" className="text-sm text-confidence-risk">
          Decision unavailable: {(query.error as Error | undefined)?.message ?? "not found"}
          <div className="mt-2">
            <Link to="/decisions" className="text-2xs text-accent underline">
              Back to Decision Theater
            </Link>
          </div>
        </div>
      )}

      {state === "populated" && decision && (
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
