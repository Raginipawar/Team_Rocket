import asyncio
from app.sim.runner import ScenarioRunner
from app.db.engine import get_db

async def run_all():
    runner = ScenarioRunner()
    scenarios = await runner.list_scenarios()
    print(f"Found scenarios: {scenarios}")
    # Mock db and api_base_url
    # Wait, the runner needs a real db session probably.
    async for db in get_db():
        for s in scenarios:
            print(f"Running {s}...")
            try:
                res = await runner.run(s, db, "http://localhost:8000")
                print(f"Result for {s}: {res['passed']}")
            except Exception as e:
                print(f"Error in {s}: {e}")
        break

if __name__ == '__main__':
    asyncio.run(run_all())
