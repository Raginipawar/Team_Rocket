FROM python:3.11-slim

WORKDIR /app

# gdal for osmnx/geopandas, libgomp for LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libgdal-dev libgomp1 curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download polyline/h3 data at build time if needed
COPY . .

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
