LEADER_KEY = "leader:core"
LEADER_TTL_MS = 10_000
LEADER_RENEW_INTERVAL_S = 3

async def try_acquire_leader(redis, worker_id: str) -> bool:
    """SET leader:core <worker_id> NX PX 10000"""
    res = await redis.set(LEADER_KEY, worker_id, nx=True, px=LEADER_TTL_MS)
    return bool(res)

async def renew_leader(redis, worker_id: str) -> bool:
    """Lua script: if GET leader:core == worker_id then PEXPIRE 10000"""
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("pexpire", KEYS[1], ARGV[2])
    else
        return 0
    end
    """
    res = await redis.eval(script, 1, LEADER_KEY, worker_id, LEADER_TTL_MS)
    return bool(res)

async def is_leader(redis, worker_id: str) -> bool:
    val = await redis.get(LEADER_KEY)
    return val == worker_id.encode('utf-8') if val else False
