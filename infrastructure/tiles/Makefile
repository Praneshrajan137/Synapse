# SYNAPSE — Protomaps PMTiles (self-hosted basemap, P2.B12).
#
# Holds I-1 (zero paid SaaS): tiles are downloaded once from the Protomaps
# CDN under the ODbL OpenStreetMap data license and stored locally. The
# frontend nginx serves them at /tiles/india.pmtiles.
#
# Usage:
#   make -C infrastructure/tiles fetch
#   make -C infrastructure/tiles verify
#
# Source URL is parameterized so we can pin a snapshot date. Default fetches
# the latest planet build trimmed to India's bounding box.

DEST    := india.pmtiles
URL     := https://build.protomaps.com/20240701.pmtiles
BBOX    := 68.0,6.5,97.5,37.5  # min_lon,min_lat,max_lon,max_lat — India
TRIMMED := india.pmtiles

.PHONY: help fetch trim verify clean

help:
	@echo "Targets:"
	@echo "  fetch   — download the planet PMTiles snapshot (large)"
	@echo "  trim    — extract India bbox to $(TRIMMED) (requires pmtiles CLI)"
	@echo "  verify  — sanity-check the trimmed file"
	@echo "  clean   — remove generated files"

fetch:
	@if [ -f planet.pmtiles ]; then \
		echo "planet.pmtiles already present"; \
	else \
		echo "Downloading $(URL) (this may take a while)…"; \
		curl -fL "$(URL)" -o planet.pmtiles.partial && mv planet.pmtiles.partial planet.pmtiles; \
	fi

trim: fetch
	@command -v pmtiles >/dev/null 2>&1 || { \
		echo "pmtiles CLI required: go install github.com/protomaps/go-pmtiles/cmd/pmtiles@latest"; \
		exit 1; \
	}
	pmtiles extract planet.pmtiles $(TRIMMED) --bbox=$(BBOX)

verify:
	@test -f $(DEST) || { echo "$(DEST) missing — run 'make trim'"; exit 1; }
	@stat -c '%s' $(DEST) 2>/dev/null || stat -f '%z' $(DEST)
	@echo "$(DEST) OK"

clean:
	rm -f planet.pmtiles planet.pmtiles.partial $(TRIMMED)
