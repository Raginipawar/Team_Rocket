"""Real-data feeder for demand-forecast + pre-positioning (technical.md A16,
Section11.15). Neither ML capability had ANY caller anywhere before this --
both only ever worked if someone manually constructed the feature payload
and called the ML service directly. This is the 15-minute recurring job
that was missing: pulls real recent call history, buckets it into H3 cells,
computes the lag/neighbour features the demand model actually needs, calls
the real /demand-forecast and /preposition endpoints, stores the forecast,
and pushes any resulting reposition suggestion to the relevant ambulance.

Same 'simple asyncio loop, B's real job framework will eventually own the
scheduling' pattern as realtime/relay.py and domain/lifecycle_monitor.py --
started from main.py's lifespan alongside them."""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

import h3
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repos import identity as identity_repo
from app.integrations.push.sender import send_push
from app.integrations.ml.routing import ML_BASE_URL
from app.realtime import outbox

logger = logging.getLogger("ml_feeder")

POLL_INTERVAL_S = 900  # 15 minutes, per technical.md A16
H3_RESOLUTION = 8
LOOKBACK_HOURS = 168


async def _recent_calls(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(text(
        "SELECT ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng, received_at "
        "FROM emergencies WHERE location IS NOT NULL "
        "AND received_at > now() - interval '1 hour' * :lookback"
    ), {"lookback": LOOKBACK_HOURS})).mappings().all()
    return [dict(r) for r in rows]


def _compute_cell_features(calls: list[dict], now: datetime) -> dict[str, dict]:
    cell_times: dict[str, list[datetime]] = defaultdict(list)
    for c in calls:
        cell = h3.latlng_to_cell(c["lat"], c["lng"], H3_RESOLUTION)
        cell_times[cell].append(c["received_at"])

    features = {}
    for cell, times in cell_times.items():
        lag_1h = sum(1 for t in times if (now - t).total_seconds() <= 3600)
        lag_24h = sum(1 for t in times if (now - t).total_seconds() <= 86400)
        lag_168h = len(times)
        features[cell] = {"lag_1h": lag_1h, "lag_24h": lag_24h, "lag_168h": lag_168h}

    for cell, feat in features.items():
        neighbours = h3.grid_disk(cell, 1)
        feat["neighbour_sum_calls"] = sum(
            features[n]["lag_1h"] for n in neighbours if n != cell and n in features
        )
    return features


async def _call_demand_forecast(cells_payload: list[dict]) -> list[dict]:
    try:
        async with httpx.AsyncClient(base_url=ML_BASE_URL, timeout=10.0) as client:
            resp = await client.post("/ml/v1/demand-forecast", json={"horizon_min": 60, "cells": cells_payload})
            resp.raise_for_status()
            return resp.json().get("cells", [])
    except httpx.HTTPError:
        logger.exception("ml_feeder: demand-forecast call failed")
        return []


async def _call_preposition(idle_ambulances: list[dict], forecast: list[dict]) -> list[dict]:
    if not idle_ambulances or not forecast:
        return []
    try:
        async with httpx.AsyncClient(base_url=ML_BASE_URL, timeout=15.0) as client:
            resp = await client.post("/ml/v1/preposition", json={
                "idle_ambulances": idle_ambulances, "forecast": forecast,
            })
            resp.raise_for_status()
            return resp.json().get("suggestions", [])
    except httpx.HTTPError:
        logger.exception("ml_feeder: preposition call failed")
        return []


async def _idle_ambulances(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(text(
        "SELECT id, type, ST_Y(current_location::geometry) AS lat, ST_X(current_location::geometry) AS lng "
        "FROM ambulances WHERE status = 'available' AND current_location IS NOT NULL"
    ))).mappings().all()
    return [{"id": str(r["id"]), "type": r["type"], "location": {"lat": r["lat"], "lng": r["lng"]}} for r in rows]


async def run_feeder_once(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    calls = await _recent_calls(session)
    cell_features = _compute_cell_features(calls, now)

    if not cell_features:
        logger.info("ml_feeder: no recent call history -- nothing to forecast this cycle")
        return {"cells_forecast": 0, "suggestions": 0}

    cells_payload = [
        {
            "h3_cell": cell, "hour": now.hour, "weekday": now.weekday(), "is_festival": 0,
            "lag_1h": feat["lag_1h"], "lag_24h": feat["lag_24h"], "lag_168h": feat["lag_168h"],
            "neighbour_sum_calls": feat["neighbour_sum_calls"], "cell_kind_enc": 0,
        }
        for cell, feat in cell_features.items()
    ]
    forecast_cells = await _call_demand_forecast(cells_payload)
    if not forecast_cells:
        return {"cells_forecast": 0, "suggestions": 0}

    for fc in forecast_cells:
        await session.execute(text(
            "INSERT INTO demand_forecasts (h3_cell, window_start, predicted_calls, model_version) "
            "VALUES (:cell, :window_start, :predicted, :model_version) "
            "ON CONFLICT (h3_cell, window_start) DO UPDATE SET predicted_calls = :predicted"
        ), {"cell": fc["h3_cell"], "window_start": now, "predicted": fc["predicted_calls"],
            "model_version": fc.get("model_version", "demand:v0")})

    # real_preposition needs each forecast zone's own lat/lng -- the
    # demand-forecast response only carries h3_cell/predicted_calls (cheaply
    # derivable by any caller), so this job derives it before passing on.
    # If the demand capability is running in its mock fallback (ML service
    # down, or ML_MODE=mock), it returns its own placeholder cell IDs
    # (demand/mock.py's DEMO_CELLS) that aren't real H3 cells at all --
    # found by this crashing on exactly that. Skip what can't be decoded
    # rather than let one bad zone take down the whole job.
    forecast_with_latlng = []
    for fc in forecast_cells:
        try:
            lat, lng = h3.cell_to_latlng(fc["h3_cell"])
        except Exception:
            logger.warning("ml_feeder: skipping non-decodable h3_cell %r (likely a mock-mode placeholder)",
                            fc.get("h3_cell"))
            continue
        forecast_with_latlng.append({**fc, "lat": lat, "lng": lng})

    idle = await _idle_ambulances(session)
    suggestions = await _call_preposition(idle, forecast_with_latlng)

    for s in suggestions:
        await outbox.emit(session, channel=f"ambulance:{s['ambulance_id']}", event="preposition.suggested", data={
            "ambulance_id": s["ambulance_id"], "target": s["target"], "h3_cell": s["h3_cell"],
            "expected_coverage_gain": s["expected_coverage_gain"],
        })
        for paramedic_user_id in await identity_repo.get_user_ids_by_ambulance_id(session, s["ambulance_id"]):
            try:
                await send_push(paramedic_user_id, "Reposition suggestion",
                                 "Moving to this area may help you reach the next call faster.", data={
                                     "ambulance_id": s["ambulance_id"], "h3_cell": s["h3_cell"],
                                 })
            except Exception:
                logger.exception("ml_feeder: send_push failed for ambulance %s", s["ambulance_id"])

    logger.info("ml_feeder: forecast %d cells, %d preposition suggestions", len(forecast_cells), len(suggestions))
    return {"cells_forecast": len(forecast_cells), "suggestions": len(suggestions)}


async def run_feeder_forever(session_factory) -> None:
    logger.info("ml_feeder started, running every %ss", POLL_INTERVAL_S)
    while True:
        try:
            async with session_factory() as session:
                await run_feeder_once(session)
                await session.commit()
        except Exception:
            logger.exception("ml_feeder iteration failed -- continuing")
        await asyncio.sleep(POLL_INTERVAL_S)
