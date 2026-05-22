import { useQuery } from "@tanstack/react-query";
import type { DemoSegmentId } from "./useDemoRun";

interface ArtifactResponse {
  readonly segment: string;
  readonly city: string;
  readonly body: Record<string, unknown>;
}

export function useArtifact(jobId: string | null, segment: DemoSegmentId | null) {
  return useQuery<ArtifactResponse>({
    queryKey: ["demo-artifact", jobId, segment],
    enabled: !!jobId && !!segment,
    queryFn: async () => {
      const resp = await fetch(`/api/v1/demo/${jobId}/artifact/${segment}`);
      if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
      return (await resp.json()) as ArtifactResponse;
    },
    staleTime: 30_000,
  });
}
