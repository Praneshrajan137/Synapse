import { useQuery } from "@tanstack/react-query";
import { useCityStore } from "@state/city.store";

interface CityStore {
  readonly id: string;
  readonly lat: number;
  readonly lon: number;
}

/**
 * Loads `data/{city}/stores.json` (served as a static asset by nginx).
 * The fetch is cached per-city and stale-while-revalidated.
 */
export function useCityStores() {
  const city = useCityStore((s) => s.city);
  return useQuery<ReadonlyArray<CityStore>>({
    queryKey: ["city-stores", city],
    queryFn: async () => {
      const res = await fetch(`/data/${city}/stores.json`);
      if (!res.ok) return [];
      const body = (await res.json()) as unknown;
      if (!Array.isArray(body)) return [];
      return body.filter(
        (s): s is CityStore =>
          typeof s === "object" &&
          s !== null &&
          typeof (s as Record<string, unknown>)["id"] === "string" &&
          typeof (s as Record<string, unknown>)["lat"] === "number" &&
          typeof (s as Record<string, unknown>)["lon"] === "number",
      );
    },
    staleTime: 5 * 60_000,
  });
}
