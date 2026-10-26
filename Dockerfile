# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Some Docling / ML wheels need a compiler during install.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable


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

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MARKDOWN_OUTPUT_DIR=/data/extracted/markdown \
    HF_HOME=/data/.cache/huggingface \
    XDG_CACHE_HOME=/data/.cache

COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

VOLUME ["/data/pdfs", "/data/extracted", "/data/.cache"]

ENTRYPOINT ["/entrypoint.sh"]
CMD ["help"]
