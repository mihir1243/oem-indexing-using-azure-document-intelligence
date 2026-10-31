# OEM Manual Indexing and Retrieval

Pipeline for extracting OEM service manuals with Docling (PDF-only install: `docling-slim` + PDF/OCR/model extras), hierarchical chunking, OpenAI embeddings, and Azure AI Search retrieval.

## Docker (run anywhere)

Build once, then run on any host with Docker (Azure Container Apps, App Service for Containers, ACI, local, etc.).

### HTTP API (Azure Container Apps / API-only access)

Default container command starts the extraction API on port **8000**:

```bash
docker build -t oem-manual-indexing:latest .
docker run --rm --env-file .env -p 8000:8000 \
  -v oem-docling-cache:/data/.cache \
  -v oem-extraction-jobs:/data/jobs \
  oem-manual-indexing:latest api
```

Or: `docker compose up --build` (see `docker-compose.yml`).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness (no auth) |
| `/api/v1/extractions` | POST | Upload PDF (`multipart/form-data`, field `file`) → `{ job_id, status, poll_url }` |
| `/api/v1/extractions/{job_id}` | GET | Poll `status`: `queued` → `running` → `completed` or `failed`. While `running`, response includes `progress_message`, optional `progress_percent`, and page counts when Docling reports them. |
| `/api/v1/extractions/{job_id}/markdown` | GET | Download markdown when `completed` |
| `/api/v1/extractions/{job_id}/page-map` | GET | Download page map JSON when `completed` |

If `API_KEY` is set in `.env`, send header `X-API-Key: <value>` on all routes except `/health`.

Example (PowerShell):

```powershell
curl.exe -X POST "http://localhost:8000/api/v1/extractions" `
  -H "X-API-Key: YOUR_KEY" `
  -F "file=@manuals\caterpiller manual.pdf"

curl.exe "http://localhost:8000/api/v1/extractions/<job_id>" -H "X-API-Key: YOUR_KEY"

curl.exe -o output.md "http://localhost:8000/api/v1/extractions/<job_id>/markdown" -H "X-API-Key: YOUR_KEY"
```

On Azure Container Apps, set ingress to port **8000**, mount **Azure Files** (or similar) on `/data/jobs` and `/data/.cache` so jobs and models survive restarts.

### CLI batch indexing

```bash
docker run --rm --env-file .env \
  -v "%CD%\manuals:/data/pdfs" \
  -v "%CD%\extracted:/data/extracted" \
  -v "%CD%\manifest.json:/data/manifest.json" \
  -v oem-docling-cache:/data/.cache \
  oem-manual-indexing:latest \
  index --folder /data/pdfs --manifest /data/manifest.json
```

| Mount | Purpose |
|-------|---------|
| `/data/pdfs` | Input PDFs (read-only is enough) |
| `/data/extracted` | Markdown cache (`MARKDOWN_OUTPUT_DIR` defaults to `/data/extracted/markdown`) |
| `/data/jobs` | API job uploads and outputs |
| `/data/.cache` | Docling / Hugging Face model cache |

Other CLI commands: `search`, `verify`, `help`.

First extraction in a fresh cache volume can take a long time while models download.

**CPU / memory:** set `cpus`, `mem_limit`, and `mem_reservation` on the service in `docker-compose.yml` (defaults: 4 CPUs, 8 GB cap, 4 GB reserved). For plain `docker run`, use `--cpus 4 --memory 8g`.

**Image size:** dependencies use CPU-only PyTorch (`pytorch-cpu` index in `pyproject.toml`) and Docling’s PDF stack only—not `docling-slim[standard]` (no Office/email/HTML converters). Rebuild after `uv.lock` changes.

## Setup

```bash
uv sync --extra dev
cp .env.example .env
```

Fill in Azure AI Search and OpenAI credentials in `.env`. Docling runs locally; the first extraction may download models. By default, `DOCLING_HEADING_HIERARCHY=true` infers `#` / `##` / `###` from PDF bookmarks, outline numbering, and font style (not flat `##` for every heading).

## Index manuals

```bash
uv run python scripts/index_manuals.py --folder ./pdfs --manifest ./manifest.json
```

After extraction, markdown is saved under `extracted/markdown/` by default (one `.md` file per PDF, plus a `.page_map.json` sidecar). Configure with `MARKDOWN_OUTPUT_DIR` in `.env`; set it to empty to disable.

If `{stem}.md` already exists, indexing **skips Docling** and reuses the cached file (`SKIP_EXTRACTION_IF_MARKDOWN_EXISTS=true`). Use `--force-extract` or `FORCE_REEXTRACT=true` to re-run extraction.

## Search

```bash
uv run python scripts/search_manuals.py --query "engine overheating fault code" --manufacturer "GE Healthcare"
```

## Tests

```bash
uv run pytest
```

## Scoring profile (boost troubleshooting sections)

See [docs/azure-scoring-profile-setup.md](docs/azure-scoring-profile-setup.md) for Azure Portal steps (new `section_tags` field + `oem-diagnosis-boost` profile), then re-index and set `USE_SCORING_PROFILE=true`.

## Enable semantic search on the index

Your search service must support **semantic ranking** (Basic+ tier with the feature enabled).

```bash
uv run python scripts/enable_semantic_config.py
```

Then in `.env`:

```env
USE_SEMANTIC_SEARCH=true
SEMANTIC_CONFIGURATION_NAME=oem-semantic-config
```

## Troubleshooting Azure keys

If indexing fails with *"The given API key doesn't match service's internal, primary or secondary keys"*, the **Azure AI Search** key does not match `AZURE_SEARCH_ENDPOINT` (common after key rotation or copying from the wrong resource).

```bash
uv run python scripts/verify_connections.py
```

In Azure Portal → **Azure AI Search** → **Keys**, copy the **Primary admin key** into `AZURE_SEARCH_KEY`.
