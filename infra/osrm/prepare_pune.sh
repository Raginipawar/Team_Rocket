#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# infra/osrm/prepare_pune.sh
#
# Download the Maharashtra OSM extract, clip it to the Pune demo bounding box,
# and prepare the OSRM MLD routing graph.
#
# Pune demo bbox (§15 of technical.md):
#   South/West : 18.42°N, 73.72°E
#   North/East : 18.63°N, 73.97°E
#
# Prerequisites (install on the host, not inside Docker):
#   - wget or curl
#   - osmosis  (https://wiki.openstreetmap.org/wiki/Osmosis)
#   - docker   (for osrm-extract / partition / customize steps)
#
# Output files placed in the same directory as this script (infra/osrm/):
#   pune.osrm.*    — ready to mount in the OSRM Docker container
#
# Run time: ~5–15 min depending on connection speed and host CPU.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MAHARASHTRA_URL="https://download.geofabrik.de/asia/india/maharashtra-latest.osm.pbf"
MAHARASHTRA_PBF="maharashtra.osm.pbf"
PUNE_PBF="pune.osm.pbf"

# Pune demo bounding box (§15)
BBOX_TOP=18.63
BBOX_LEFT=73.72
BBOX_BOTTOM=18.42
BBOX_RIGHT=73.97

OSRM_IMAGE="osrm/osrm-backend"
CAR_PROFILE="/opt/car.lua"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Download Maharashtra OSM extract
# ─────────────────────────────────────────────────────────────────────────────
if [[ -f "$MAHARASHTRA_PBF" ]]; then
    echo "[prepare_pune] $MAHARASHTRA_PBF already exists — skipping download."
    echo "               Delete it to force a fresh download."
else
    echo "[prepare_pune] Downloading Maharashtra OSM extract (~350 MB) …"
    wget --continue \
         --progress=bar:force:noscroll \
         -O "$MAHARASHTRA_PBF" \
         "$MAHARASHTRA_URL"
    echo "[prepare_pune] Download complete."
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Clip to Pune bounding box with osmosis
# ─────────────────────────────────────────────────────────────────────────────
echo "[prepare_pune] Clipping to Pune bbox (top=${BBOX_TOP}, left=${BBOX_LEFT}, bottom=${BBOX_BOTTOM}, right=${BBOX_RIGHT}) …"
osmosis \
    --read-pbf "$MAHARASHTRA_PBF" \
    --bounding-box \
        top="${BBOX_TOP}" \
        left="${BBOX_LEFT}" \
        bottom="${BBOX_BOTTOM}" \
        right="${BBOX_RIGHT}" \
        completeWays=yes \
        completeRelations=yes \
    --write-pbf "$PUNE_PBF"
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
        /data/pune.osm.pbf

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
echo "  The osrm service is configured with:"
echo "    volumes: [\"./osrm:/data\"]"
echo "    command: osrm-routed --algorithm mld /data/pune.osrm"
