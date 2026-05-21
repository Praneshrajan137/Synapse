import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { City } from "@domain/primitives";

interface CityState {
  readonly city: City;
  setCity(city: City): void;
}

const DEFAULT_CITY: City =
  ((import.meta.env.VITE_DEFAULT_CITY as City | undefined) ?? "bengaluru");

export const useCityStore = create<CityState>()(
  persist<CityState>(
    (set) => ({
      city: DEFAULT_CITY,
      setCity(city) {
        set({ city });
      },
    }),
    {
      name: "synapse.city",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
