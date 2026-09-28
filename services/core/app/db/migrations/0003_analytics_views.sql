-- DRAFT (see note in 0001_init.sql). A's file per work-distribution.md §2.2
-- (app/analytics/**). technical.md §11.16: response times, offload delay,
-- hospital acceptance/rejection, triage confusion matrix, stale-data
-- frequency, escalations, demand vs forecast, prank/duplicate counts.
-- Materialised views refreshed each minute by a job (not built yet, see
-- app/analytics/refresh.py note); plain views used where the query is cheap
-- enough not to need caching.

-- Response-time percentiles per hospital + system-wide (call->accept,
-- call->scene, scene->hospital, call->handoff).
CREATE MATERIALIZED VIEW mv_response_times AS
SELECT
  hospital_id,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (assigned_at - received_at))) AS call_to_accept_p50,
  percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (assigned_at - received_at))) AS call_to_accept_p90,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (at_scene_at - received_at))) AS call_to_scene_p50,
  percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (at_scene_at - received_at))) AS call_to_scene_p90,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (arrived_hospital_at - on_board_at))) AS scene_to_hospital_p50,
  percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (arrived_hospital_at - on_board_at))) AS scene_to_hospital_p90,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (handed_off_at - received_at))) AS call_to_handoff_p50,
  percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (handed_off_at - received_at))) AS call_to_handoff_p90,
  count(*) AS n_emergencies
FROM emergencies
WHERE status IN ('handed_off', 'closed')
GROUP BY hospital_id;

CREATE UNIQUE INDEX ON mv_response_times (hospital_id);

-- Offload delay distribution per hospital.
CREATE MATERIALIZED VIEW mv_offload_delay AS
SELECT
  hospital_id,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY offload_delay_sec) AS p50_sec,
  percentile_cont(0.9) WITHIN GROUP (ORDER BY offload_delay_sec) AS p90_sec,
  avg(offload_delay_sec) AS mean_sec,
  count(*) AS n_handoffs
FROM handoffs
WHERE offload_delay_sec IS NOT NULL
GROUP BY hospital_id;

CREATE UNIQUE INDEX ON mv_offload_delay (hospital_id);

-- Hospital acceptance/rejection by reason, plus timeout rate.
CREATE VIEW v_hospital_request_outcomes AS
SELECT
  hospital_id,
  status,
  reason_code,
  count(*) AS n,
  count(*) FILTER (WHERE status = 'timeout')::float / GREATEST(count(*), 1) AS timeout_rate
FROM hospital_requests
GROUP BY hospital_id, status, reason_code;

-- Rejection rate per hospital over the trailing 24h (technical.md §11.13,
-- also read directly by B's hospital-rank feature builder).
CREATE VIEW v_hospital_rejection_rate_24h AS
SELECT
  hospital_id,
  count(*) FILTER (WHERE status = 'rejected')::float / GREATEST(count(*), 1) AS rejection_rate_24h,
  count(*) AS n_requests_24h
FROM hospital_requests
WHERE sent_at > now() - interval '24 hours'
GROUP BY hospital_id;

-- Triage accuracy: AI vs paramedic-confirmed confusion matrix + critical-recall.
CREATE VIEW v_triage_confusion_matrix AS
SELECT ai_acuity, final_acuity, count(*) AS n
FROM triage_confirmations
GROUP BY ai_acuity, final_acuity;

CREATE VIEW v_triage_critical_recall AS
SELECT
  count(*) FILTER (WHERE ai_acuity = 'critical' AND final_acuity = 'critical')::float
    / GREATEST(count(*) FILTER (WHERE final_acuity = 'critical'), 1) AS critical_recall,
  count(*) FILTER (WHERE final_acuity = 'critical') AS n_actually_critical,
  count(*) FILTER (WHERE ai_acuity = 'critical' AND final_acuity != 'critical') AS n_false_critical
FROM triage_confirmations;

-- Stale-data frequency per hospital: how often reported resource counts are
-- older than FRESH_MAX_MIN/AGING_MAX_MIN (technical.md §4: 10/30 min).
CREATE VIEW v_stale_data_frequency AS
SELECT
  hospital_id,
  count(*) FILTER (WHERE now() - reported_at > interval '30 minutes')::float / GREATEST(count(*), 1) AS stale_ratio,
  count(*) FILTER (WHERE now() - reported_at BETWEEN interval '10 minutes' AND interval '30 minutes')::float
    / GREATEST(count(*), 1) AS aging_ratio,
  count(*) AS n_resource_rows
FROM hospital_resources
GROUP BY hospital_id;

-- Escalations: count by type, mean time to claim, auto-default rate.
CREATE VIEW v_escalation_stats AS
SELECT
  type,
  count(*) AS n,
  avg(EXTRACT(EPOCH FROM (claimed_at - created_at))) FILTER (WHERE claimed_at IS NOT NULL) AS mean_time_to_claim_sec,
  count(*) FILTER (WHERE status = 'auto_defaulted')::float / GREATEST(count(*), 1) AS auto_default_rate
FROM escalations
GROUP BY type;

-- Demand heatmap: actual calls vs forecast per H3 cell + hour window.
CREATE VIEW v_demand_actual_vs_forecast AS
SELECT
  df.h3_cell, df.window_start, df.predicted_calls,
  count(e.id) AS actual_calls
FROM demand_forecasts df
LEFT JOIN emergencies e
  ON e.received_at >= df.window_start AND e.received_at < df.window_start + interval '1 hour'
GROUP BY df.h3_cell, df.window_start, df.predicted_calls;

-- MCI events, prank/duplicate counts (system-wide, for the ops page).
CREATE VIEW v_mci_events AS
SELECT id, location, patient_count, status, created_at
FROM incidents
WHERE is_mass_casualty = true;

CREATE VIEW v_prank_duplicate_counts AS
SELECT
  count(*) FILTER (WHERE prank_score IS NOT NULL AND prank_score >= 0.5) AS suspicious_count,
  count(*) FILTER (WHERE duplicate_of IS NOT NULL) AS duplicate_count,
  count(*) AS total_emergencies
FROM emergencies
WHERE received_at > now() - interval '24 hours';
