# ADR-012: Frontend Visualization Stack — React + Deck.gl + MapLibre GL

## Status
Accepted

## Context
The HITL console must render: 25-50 dark stores on a city map, real-time order flow, rider GPS trails, demand heatmaps, decision logs, agent debate visualization, and a 3D supply network from Neo4j. Mapbox is paid (violates I-1). Plain D3 cannot handle the WebGL volume needed for 1000+ live markers at 60 fps. Leaflet has no 3D primitive. Kepler.gl is opinionated to the point that custom HITL UI becomes awkward.

## Decision
Frontend stack:
- **React 18** (MIT) for component composition.
- **Deck.gl** (MIT) for WebGL-accelerated map layers — handles 100K+ markers at 60 fps.
- **MapLibre GL JS** (BSD-3) for basemap rendering; uses free OpenMapTiles vector tiles, no Mapbox token required.
- **Vite** (MIT) for build tooling.
- **Recharts** (MIT) for KPI ticker / Pareto-front charts.

Five pages mapped 1:1 to plan §6.3: `Dashboard.jsx`, `DecisionLog.jsx`, `OverrideConsole.jsx`, `AgentStatus.jsx`, `DigitalTwin.jsx`, plus `components/AgentDebate.jsx`.

## Consequences
- Zero map vendor cost; satisfies I-1.
- WebGL layers handle the visual scale; CPU stays free for WebSocket consumption.
- Deck.gl + MapLibre integration requires explicit projection alignment — documented in `frontend/src/services/api.js`.
- 3D supply network in `DigitalTwin.jsx` uses Deck.gl's `ScatterplotLayer` + `ArcLayer` rather than a separate three.js scene.

## Alternatives Rejected
- **Mapbox**: rejected — paid tier required at our usage.
- **D3 only**: rejected — DOM saturation at 1000+ markers.
- **Leaflet**: rejected — no 3D primitive.
- **Kepler.gl**: rejected — UI inflexibility for HITL console.
