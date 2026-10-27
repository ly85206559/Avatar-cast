# Phase 1 skeleton: ffmpeg + Python. Model runtimes are added per-adapter,
# not baked into the base image, so the base stays reproducible.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .
CMD ["dhp", "examples/demo-script.json"]
