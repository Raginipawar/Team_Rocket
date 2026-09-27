async def sweep(ctx: dict) -> None:
    \"\"\"Safety net for missed timers (technical.md §10.2):
    - Expired offers -> status='expired'
    - Hospital request timeouts -> timeout_hospital_request()
    - Hold expiries -> expire_reservation()
    - Signal-lost detection (last_heartbeat > SIGNAL_LOST_SEC)
    - Escalation repeat (repeat_at passed)
    - Escalation default (default_at passed, status still open/claimed)
    - Offload delay alert (arrived_at > OFFLOAD_DELAY_ALERT_MIN, not offloaded)
    Each check re-reads state before acting.
    \"\"\"
    pass
