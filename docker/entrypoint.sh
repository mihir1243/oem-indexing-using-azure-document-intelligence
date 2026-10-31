#!/bin/sh
set -e

cd /app

# Docker Desktop on Windows can pass CRLF in argv; normalize the subcommand.
if [ $# -ge 1 ]; then
  arg1=$(printf '%s' "$1" | tr -d '\r')
  shift
  set -- "$arg1" "$@"
fi

print_help() {
  cat <<'EOF'
OEM manual indexing container

Usage:
  docker run --rm --env-file .env \
    -v /path/to/pdfs:/data/pdfs \
    -v /path/to/extracted:/data/extracted \
    -v oem-docling-cache:/data/.cache \
    IMAGE <command> [args]

Commands:
  api      Start HTTP API (upload / poll / download markdown) on port 8000
  index    Run scripts/index_manuals.py (default pipeline: extract → chunk → embed → search)
  search   Run scripts/search_manuals.py
  verify   Test Azure AI Search and OpenAI credentials
  python   Run arbitrary Python module, e.g. python -m pytest
  help     Show this message

Examples:
  IMAGE index --folder /data/pdfs --manifest /data/manifest.json
  IMAGE index --folder /data/pdfs --file "manual.pdf" --manufacturer OEM --model-series M1 --manual-type service
  IMAGE search --query "engine overheating" --manufacturer "GE Healthcare"

Environment:
  Set MARKDOWN_OUTPUT_DIR=/data/extracted/markdown (default in image).
  Model caches use /data/.cache (mount a volume to avoid re-downloading Docling models).
EOF
}

case "${1:-help}" in
  api)
    shift
    exec python -m src.api "$@"
    ;;
  index)
    shift
    exec python scripts/index_manuals.py "$@"
    ;;
  search)
    shift
    exec python scripts/search_manuals.py "$@"
    ;;
  verify)
    exec python scripts/verify_connections.py
    ;;
  python)
    shift
    exec python "$@"
    ;;
  help|-h|--help)
    print_help
    ;;
  *)
    exec "$@"
    ;;
esac
