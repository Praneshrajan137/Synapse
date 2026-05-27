import type { LayersList } from "@deck.gl/core";
import { DeckGL } from "@deck.gl/react";
import { useCityStore } from "@state/city.store";
import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import { useEffect, useRef } from "react";
import { buildBasemapStyle, registerPMTilesProtocol } from "./basemap";
import "maplibre-gl/dist/maplibre-gl.css";

const TILES_URL = import.meta.env.VITE_TILES_URL ?? "/tiles/india.pmtiles";

interface CityMapProps {
  readonly layers?: LayersList | undefined;
  readonly height?: number | string | undefined;
}

type CityView = { longitude: number; latitude: number; zoom: number };

const BENGALURU_VIEW: CityView = { longitude: 77.59, latitude: 12.97, zoom: 11 };

const CITY_VIEWS: Record<string, CityView> = {
  bengaluru: BENGALURU_VIEW,
  mumbai: { longitude: 72.87, latitude: 19.08, zoom: 11 },
};

/**
 * MapLibre + Deck.gl composed map, anchored to the active city.
 * Lazy-loaded by surfaces that need it (Mission Control). Deck.gl layers
 * are passed in by the caller so this component stays decoupled.
 */
export function CityMap({ layers = [], height = 420 }: CityMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const city = useCityStore((s) => s.city);
  // Safe lookup: BENGALURU_VIEW is the named-constant fallback so the
  // expression cannot be undefined and we don't need a non-null assertion
  // (lint/style/noNonNullAssertion).
  const view: CityView = CITY_VIEWS[city] ?? BENGALURU_VIEW;

  useEffect(() => {
    registerPMTilesProtocol();
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: buildBasemapStyle(TILES_URL),
      center: [view.longitude, view.latitude],
      zoom: view.zoom,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // The init effect only runs once; subsequent city changes are handled
    // by the flyTo effect below. Listing the view here would re-create the
    // map every time the city changes (wasteful + janks deck.gl layers).
  }, [view.latitude, view.longitude, view.zoom]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.flyTo({ center: [view.longitude, view.latitude], zoom: view.zoom, duration: 600 });
  }, [view.longitude, view.latitude, view.zoom]);

  return (
    <div
      ref={containerRef}
      style={{ position: "relative", height }}
      role="img"
      aria-label={`${city} live map`}
    >
      <DeckGL
        initialViewState={view}
        controller
        layers={[...layers]}
        style={{ position: "absolute", inset: "0", pointerEvents: "none" }}
      />
    </div>
  );
}
