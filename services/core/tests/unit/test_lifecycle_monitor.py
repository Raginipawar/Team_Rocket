"""Idle/wrong-way ambulance detection + signal weak/lost (technical.md
Section11.10) -- neither existed before this session. Uses the real
database (outbox/audit writes) with a fake clock for progress timing and
a real-but-backdated last_heartbeat_at for signal timing, so the actual
thresholds are exercised rather than mocked away."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

import app.domain.lifecycle_monitor as lm
from app.db.session import get_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _idle_row(ambulance_id, emergency_id, dist_to_hospital_m):
    return {
        "ambulance_id": ambulance_id, "ambulance_status": "transporting",
        "last_heartbeat_at": datetime.now(timezone.utc), "heading": 90.0, "speed_kmh": 0.0,
        "lat": 18.5, "lng": 73.9,
        "emergency_id": emergency_id, "emergency_status": "patient_on_board",
        "dist_to_pickup_m": None, "dist_to_hospital_m": dist_to_hospital_m,
    }


async def test_idle_ambulance_alerts_then_redispatches():
    amb_id, em_id = str(uuid.uuid4()), str(uuid.uuid4())
    fake_time = [1000.0]

    with patch.object(lm, "_now_s", lambda: fake_time[0]), \
         patch("app.domain.dispatch.redispatch_to_point", new_callable=AsyncMock) as mock_redispatch, \
         patch("app.domain.dispatch.start_dispatch", new_callable=AsyncMock):
        async with get_session() as session:
            await lm.check_idle_progress(session, [_idle_row(amb_id, em_id, 500.0)])
            assert lm._progress_state[amb_id]["idle_alerted"] is False

            fake_time[0] = 1095.0  # 95s, no progress -> alert threshold (90s)
            await lm.check_idle_progress(session, [_idle_row(amb_id, em_id, 500.0)])
            assert lm._progress_state[amb_id]["idle_alerted"] is True
            assert lm._progress_state[amb_id]["idle_redispatched"] is False

            fake_time[0] = 1160.0  # 160s, still no progress -> redispatch threshold (150s)
            await lm.check_idle_progress(session, [_idle_row(amb_id, em_id, 500.0)])
            assert lm._progress_state[amb_id]["idle_redispatched"] is True
            mock_redispatch.assert_awaited_once()
            assert mock_redispatch.call_args.kwargs["reason"] == "idle_timeout"
            assert mock_redispatch.call_args.kwargs["broken_ambulance_id"] == amb_id

            await session.commit()


async def test_real_progress_resets_idle_clock():
    amb_id, em_id = str(uuid.uuid4()), str(uuid.uuid4())
    fake_time = [2000.0]

    with patch.object(lm, "_now_s", lambda: fake_time[0]):
        async with get_session() as session:
            await lm.check_idle_progress(session, [_idle_row(amb_id, em_id, 500.0)])

            fake_time[0] = 2095.0
            await lm.check_idle_progress(session, [_idle_row(amb_id, em_id, 500.0)])
            assert lm._progress_state[amb_id]["idle_alerted"] is True

            # ambulance moves 100m closer -- real progress, clock resets
            fake_time[0] = 2096.0
            await lm.check_idle_progress(session, [_idle_row(amb_id, em_id, 400.0)])
            assert lm._progress_state[amb_id]["idle_alerted"] is False
            assert lm._progress_state[amb_id]["last_distance_m"] == 400.0

            await session.commit()


async def test_signal_weak_then_lost_then_recovered():
    amb_id, em_id = str(uuid.uuid4()), str(uuid.uuid4())

    def row(seconds_ago):
        r = _idle_row(amb_id, em_id, 500.0)
        r["last_heartbeat_at"] = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
        r["speed_kmh"] = 40.0
        return r

    async with get_session() as session:
        await lm.check_signal_health(session, [row(5)])
        assert lm._progress_state[amb_id]["signal_state"] == "ok"

        await lm.check_signal_health(session, [row(45)])
        assert lm._progress_state[amb_id]["signal_state"] == "weak"

        await lm.check_signal_health(session, [row(150)])
        assert lm._progress_state[amb_id]["signal_state"] == "lost"

        await lm.check_signal_health(session, [row(5)])
        assert lm._progress_state[amb_id]["signal_state"] == "ok"

        await session.commit()


async def test_signal_lost_emits_dead_reckoned_position():
    amb_id, em_id = str(uuid.uuid4()), str(uuid.uuid4())
    row = _idle_row(amb_id, em_id, 500.0)
    row["last_heartbeat_at"] = datetime.now(timezone.utc) - timedelta(seconds=150)
    row["speed_kmh"] = 40.0
    row["heading"] = 90.0  # due east

    async with get_session() as session:
        await lm.check_signal_health(session, [row])
        await session.commit()
        data = (await session.execute(
            text("SELECT data FROM outbox WHERE channel = :c ORDER BY id DESC LIMIT 1"),
            {"c": f"ambulance:{amb_id}"},
        )).scalar_one()
        assert data["signal"] == "lost"
        assert "estimated_lat" in data and "estimated_lng" in data
        assert data["estimated_lng"] > row["lng"]  # moved east, as expected from heading=90


async def test_offload_delay_alerts_once_past_15_min():
    em_id = str(uuid.uuid4())
    async with get_session() as session:
        hospital_id = (await session.execute(text("SELECT id FROM hospitals LIMIT 1"))).scalar_one()
        incident_id = (await session.execute(text("INSERT INTO incidents DEFAULT VALUES RETURNING id"))).scalar_one()
        await session.execute(
            text("INSERT INTO emergencies (id, incident_id, channel, status, version) "
                 "VALUES (:id, :inc, 'app_text', 'arrived_hospital', 1)"),
            {"id": em_id, "inc": incident_id},
        )
        await session.execute(
            text("INSERT INTO handoffs (emergency_id, hospital_id, arrived_at) "
                 "VALUES (:em, :h, now() - interval '16 minutes')"),
            {"em": em_id, "h": hospital_id},
        )
        await session.commit()

        await lm.check_offload_delay(session)
        await session.commit()
        data = (await session.execute(
            text("SELECT data FROM outbox WHERE channel = :c ORDER BY id DESC LIMIT 1"),
            {"c": f"hospital:{hospital_id}"},
        )).scalar_one()
        assert data["kind"] == "offload_delay"
        assert data["emergency_id"] == em_id

        before = (await session.execute(
            text("SELECT count(*) FROM outbox WHERE channel = :c"), {"c": f"hospital:{hospital_id}"}
        )).scalar_one()
        await lm.check_offload_delay(session)  # second poll, still unresolved -- must not re-alert
        await session.commit()
        after = (await session.execute(
            text("SELECT count(*) FROM outbox WHERE channel = :c"), {"c": f"hospital:{hospital_id}"}
        )).scalar_one()
        assert before == after


async def test_offload_delay_does_not_fire_under_15_min():
    em_id = str(uuid.uuid4())
    async with get_session() as session:
        hospital_id = (await session.execute(text("SELECT id FROM hospitals LIMIT 1"))).scalar_one()
        incident_id = (await session.execute(text("INSERT INTO incidents DEFAULT VALUES RETURNING id"))).scalar_one()
        await session.execute(
            text("INSERT INTO emergencies (id, incident_id, channel, status, version) "
                 "VALUES (:id, :inc, 'app_text', 'arrived_hospital', 1)"),
            {"id": em_id, "inc": incident_id},
        )
        await session.execute(
            text("INSERT INTO handoffs (emergency_id, hospital_id, arrived_at) "
                 "VALUES (:em, :h, now() - interval '5 minutes')"),
            {"em": em_id, "h": hospital_id},
        )
        await session.commit()

        before = (await session.execute(
            text("SELECT count(*) FROM outbox WHERE channel = :c"), {"c": f"hospital:{hospital_id}"}
        )).scalar_one()
        await lm.check_offload_delay(session)
        await session.commit()
        after = (await session.execute(
            text("SELECT count(*) FROM outbox WHERE channel = :c"), {"c": f"hospital:{hospital_id}"}
        )).scalar_one()
        assert before == after, "must not alert before the 15-minute threshold"
