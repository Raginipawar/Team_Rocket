FROM python:3.11-slim

WORKDIR /app

# gdal for osmnx/geopandas, libgomp for LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgdal-dev libgomp1 curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install CPU-only PyTorch first to avoid downloading 5.5+ GB of CUDA / NVIDIA packages
# which fills the Docker WSL2 disk and triggers [Errno 30] Read-only file system
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchaudio && \
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
