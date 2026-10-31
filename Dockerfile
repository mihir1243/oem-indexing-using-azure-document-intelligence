# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Some Docling / ML wheels need a compiler during install.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY docker/prune_venv.sh ./docker/prune_venv.sh

RUN sed -i 's/\r$//' docker/prune_venv.sh \
    && chmod +x docker/prune_venv.sh \
    && uv sync --frozen --no-dev --no-editable \
    && /app/.venv/bin/python -c "import cv2" \
    && sh docker/prune_venv.sh /app/.venv \
    && /app/.venv/bin/python -c "import cv2" \
    && rm -rf /root/.cache/uv


FROM python:3.11-slim-bookworm

WORKDIR /app

# Runtime libraries for PDF parsing, OpenCV-style deps, and Docling OCR.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY .env ./.env

# Fail the build if API sources are missing (avoids stale layer cache surprises).
RUN test -f /app/src/api/app.py \
    && /app/.venv/bin/python -c "import cv2"

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MARKDOWN_OUTPUT_DIR=/data/extracted/markdown \
    API_JOBS_DIR=/data/jobs \
    HF_HOME=/data/.cache/huggingface \
    XDG_CACHE_HOME=/data/.cache \
    DOCLING_OCR_ENGINE=tesseract \
    DOCLING_TESSERACT_LANGS=eng

EXPOSE 8000

COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

VOLUME ["/data/pdfs", "/data/extracted", "/data/jobs", "/data/.cache"]

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "src.api"]
