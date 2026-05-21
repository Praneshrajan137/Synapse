import { useQuery } from "@tanstack/react-query";

export type HealthStatus = "online" | "offline" | "connecting";

interface HealthPayload {
  status?: string;
}

/**
 * Polls the orchestrator /health endpoint. Drives the StatusBar health
 * indicator. Failure is expected when the backend is not running and is
 * surfaced calmly as "offline" rather than thrown.
 */
export function useHealth(): { status: HealthStatus; raw: HealthPayload | undefined } {
  const query = useQuery({
    queryKey: ["system", "health"],
    queryFn: async (): Promise<HealthPayload> => {
      const res = await fetch("/health");
      if (!res.ok) throw new Error(`health ${res.status}`);
      return (await res.json()) as HealthPayload;
    },
    refetchInterval: 30_000,
    retry: false,
    staleTime: 25_000,
  });

  const status: HealthStatus = query.isSuccess
    ? "online"
    : query.isError
      ? "offline"
      : "connecting";

  return { status, raw: query.data };
}
