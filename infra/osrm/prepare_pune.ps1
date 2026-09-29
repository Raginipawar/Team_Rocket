$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
Set-Location $ScriptDir

$ZONE_URL = "https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf"
$ZONE_PBF = "western-zone.osm.pbf"
$PUNE_PBF = "pune.osm.pbf"

$BBOX_TOP = 18.63
$BBOX_LEFT = 73.72
$BBOX_BOTTOM = 18.42
$BBOX_RIGHT = 73.97
$BBOX = "$BBOX_LEFT,$BBOX_BOTTOM,$BBOX_RIGHT,$BBOX_TOP"

$OSRM_IMAGE = "osrm/osrm-backend"
$CAR_PROFILE = "/opt/car.lua"

if (-not (Test-Path $ZONE_PBF)) {
    Write-Host "[prepare_pune] Downloading Western Zone OSM extract (~150 MB) …"
    curl.exe -f -L -o $ZONE_PBF $ZONE_URL
} else {
    Write-Host "[prepare_pune] $ZONE_PBF already exists — skipping download."
}

Write-Host "[prepare_pune] Clipping to Pune bbox ($BBOX) using Dockerized osmium …"
docker run --rm -v "${ScriptDir}:/data" ubuntu:22.04 sh -c "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y osmium-tool && osmium extract -b $BBOX /data/$ZONE_PBF -o /data/$PUNE_PBF --overwrite"

Write-Host "[prepare_pune] Running osrm-extract …"
docker run --rm -v "${ScriptDir}:/data" $OSRM_IMAGE osrm-extract -p $CAR_PROFILE /data/$PUNE_PBF

Write-Host "[prepare_pune] Running osrm-partition …"
docker run --rm -v "${ScriptDir}:/data" $OSRM_IMAGE osrm-partition /data/pune.osrm

Write-Host "[prepare_pune] Running osrm-customize …"
docker run --rm -v "${ScriptDir}:/data" $OSRM_IMAGE osrm-customize /data/pune.osrm

Write-Host ""
Write-Host "[prepare_pune] ✓ OSRM MLD graph ready in ${ScriptDir}/"
Write-Host "               Files: pune.osrm, pune.osrm.mldgr, pune.osrm.partition, …"
Write-Host ""
Write-Host "  Next step: docker compose -f infra/docker-compose.yml up -d osrm"
