import asyncio
import yaml
from fastapi.openapi.utils import get_openapi
from app.main import app

def generate_openapi():
    openapi_schema = get_openapi(
        title="GoldenHour ML API",
        version="1.0.0",
        routes=app.routes,
    )
    with open("/app/openapi.ml.yaml", "w") as f:
        yaml.dump(openapi_schema, f, sort_keys=False)
    print("Generated openapi.ml.yaml")

if __name__ == '__main__':
    generate_openapi()

