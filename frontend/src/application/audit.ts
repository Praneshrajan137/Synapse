import { useUIStore } from "@/app/store/uiStore";
import { api } from "@/infrastructure/api/client";
import { useQuery } from "@tanstack/react-query";

/** Audit use-cases — the Replay surface timeline and rows. */

export function useAuditTimeline(count = 60) {
  const city = useUIStore((s) => s.city);
  return useQuery({
    queryKey: ["audit", "timeline", city, count],
    queryFn: () => api.auditTimeline(count, city),
  });
}

export function useAuditRow(id: string | undefined) {
  return useQuery({
    queryKey: ["audit", "row", id],
    queryFn: () => api.auditRow(id ?? ""),
    enabled: Boolean(id),
  });
}
