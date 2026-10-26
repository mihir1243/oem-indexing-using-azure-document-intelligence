# OEM Manual Indexing and Retrieval

Pipeline for extracting OEM service manuals with Docling (HTML tables in markdown), hierarchical chunking, OpenAI embeddings, and Azure AI Search retrieval.

## Docker (run anywhere)

Build once, then run on any host with Docker (Azure Container Apps, App Service for Containers, ACI, local, etc.).

```bash
docker build -t oem-manual-indexing:latest .
docker run --rm --env-file .env \
  -v "%CD%\pdfs:/data/pdfs" \
  -v "%CD%\extracted:/data/extracted" \
  -v "%CD%\manifest.json:/data/manifest.json" \
  -v oem-docling-cache:/data/.cache \
  oem-manual-indexing:latest \
  index --folder /data/pdfs --manifest /data/manifest.json
```

On Linux/macOS, replace the volume paths with `$(pwd)/pdfs`, etc.

| Mount | Purpose |
|-------|---------|
| `/data/pdfs` | Input PDFs (read-only is enough) |
| `/data/extracted` | Markdown cache (`MARKDOWN_OUTPUT_DIR` defaults to `/data/extracted/markdown`) |
| `/data/.cache` | Docling / Hugging Face model cache (use a named volume so models are not re-downloaded every run) |
| `/data/manifest.json` | Optional manifest file for batch indexing |

Other commands: `search`, `verify`, `help`. With Compose: `docker compose run --rm oem-manuals index --folder /data/pdfs --manifest /data/manifest.json` (set `command` in `docker-compose.yml` or pass it after the service name).

First extraction in a fresh cache volume can take a long time while models download.

**CPU / memory:** set `cpus`, `mem_limit`, and `mem_reservation` on the service in `docker-compose.yml` (defaults: 4 CPUs, 8 GB cap, 4 GB reserved). For plain `docker run`, use `--cpus 4 --memory 8g`.

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
