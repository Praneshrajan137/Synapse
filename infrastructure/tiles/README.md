# SYNAPSE — Self-hosted Map Tiles

This directory holds the **Protomaps PMTiles** blob the frontend serves as
its basemap (FE-INV-020 / I-1: no Mapbox).

## Why PMTiles?

- **Free** — sourced from OpenStreetMap under ODbL via the Protomaps
  community build (`build.protomaps.com`).
- **Single file** — one `india.pmtiles` blob (≈100–200 MB) instead of
  millions of tile files; range-served by nginx.
- **No backend** — the FE talks directly to nginx; no tile server needed.

## Setup (one-time)

```bash
make -C infrastructure/tiles fetch   # download planet snapshot (~50 GB)
make -C infrastructure/tiles trim    # extract India bbox → india.pmtiles
make -C infrastructure/tiles verify  # sanity check
```

After `trim` produces `india.pmtiles`, the frontend Docker compose service
mounts this directory so nginx exposes it at `/tiles/india.pmtiles`.

## Updating tiles

Pin a fresh snapshot date in the `URL` variable in the Makefile and rerun
`make trim`. Browser caches use a 1-day max-age (see `frontend/nginx.conf`).

## License

OSM data is © OpenStreetMap contributors, distributed under the
[Open Data Commons Open Database License](https://opendatacommons.org/licenses/odbl/).
The Protomaps schema is BSD-3-Clause. Both are I-1 compliant.
