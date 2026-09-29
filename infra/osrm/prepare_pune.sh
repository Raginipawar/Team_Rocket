#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# infra/osrm/prepare_pune.sh
#
# Download the Western Zone OSM extract (includes Maharashtra), clip it to the 
# Pune demo bounding box, and prepare the OSRM MLD routing graph.
#
# Prerequisites:
#   - docker (all tools including download, clip, and graph generation run in Docker)
#
# Output files placed in the same directory as this script (infra/osrm/):
#   pune.osrm.*    — ready to mount in the OSRM Docker container
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Geofabrik's India data is split by zones; Maharashtra is in the western zone.
ZONE_URL="https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf"
ZONE_PBF="western-zone.osm.pbf"
PUNE_PBF="pune.osm.pbf"

# Pune demo bounding box (§15)
BBOX_TOP=18.63
BBOX_LEFT=73.72
BBOX_BOTTOM=18.42
BBOX_RIGHT=73.97
# Osmium bounding box format: min_lon,min_lat,max_lon,max_lat
BBOX="${BBOX_LEFT},${BBOX_BOTTOM},${BBOX_RIGHT},${BBOX_TOP}"

OSRM_IMAGE="osrm/osrm-backend"
CAR_PROFILE="/opt/car.lua"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Download Western Zone OSM extract
# ─────────────────────────────────────────────────────────────────────────────
if [[ -f "$ZONE_PBF" ]]; then
    echo "[prepare_pune] $ZONE_PBF already exists — skipping download."
else
    echo "[prepare_pune] Downloading Western Zone OSM extract (~150 MB) …"
    # -f fails on HTTP errors (like 404), -L follows redirects
    curl -f -L -o "$ZONE_PBF" "$ZONE_URL"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Clip to Pune bounding box
# ─────────────────────────────────────────────────────────────────────────────
echo "[prepare_pune] Clipping to Pune bbox ($BBOX) using Dockerized osmium …"
# We run osmium-tool inside an ephemeral Alpine container so you don't need it on your host
docker run --rm -v "${SCRIPT_DIR}:/data" alpine sh -c "
    apk add --no-cache osmium-tool &&
    osmium extract -b ${BBOX} /data/${ZONE_PBF} -o /data/${PUNE_PBF} --overwrite
"
echo "[prepare_pune] Clipped: ${PUNE_PBF}"

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: OSRM extract (car profile)
# ─────────────────────────────────────────────────────────────────────────────
echo "[prepare_pune] Running osrm-extract …"
docker run --rm \
    -v "${SCRIPT_DIR}:/data" \
    "${OSRM_IMAGE}" \
    osrm-extract \
        -p "${CAR_PROFILE}" \
        /data/${PUNE_PBF}

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: OSRM partition (MLD)
# ─────────────────────────────────────────────────────────────────────────────
echo "[prepare_pune] Running osrm-partition …"
docker run --rm \
    -v "${SCRIPT_DIR}:/data" \
    "${OSRM_IMAGE}" \
    osrm-partition /data/pune.osrm

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: OSRM customize (MLD weights)
# ─────────────────────────────────────────────────────────────────────────────
echo "[prepare_pune] Running osrm-customize …"
docker run --rm \
    -v "${SCRIPT_DIR}:/data" \
    "${OSRM_IMAGE}" \
    osrm-customize /data/pune.osrm

# ─────────────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "[prepare_pune] ✓ OSRM MLD graph ready in ${SCRIPT_DIR}/"
echo "               Files: pune.osrm, pune.osrm.mldgr, pune.osrm.partition, …"
echo ""
echo "  Next step: docker compose -f infra/docker-compose.yml up -d osrm"
