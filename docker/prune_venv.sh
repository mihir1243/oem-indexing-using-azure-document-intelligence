#!/bin/sh
# Shrink copied .venv: drop caches, tests, and any accidental CUDA wheel trees.
set -e
VENV="${1:-/app/.venv}"
PY="python3.11"

find "$VENV" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$VENV" -type f -name '*.pyc' -delete 2>/dev/null || true
find "$VENV/lib/$PY/site-packages" -type d -name tests -exec rm -rf {} + 2>/dev/null || true
find "$VENV/lib/$PY/site-packages" -type d -name test -exec rm -rf {} + 2>/dev/null || true

rm -rf \
  "$VENV/lib/$PY/site-packages/nvidia" \
  "$VENV/lib/$PY/site-packages/triton" \
  "$VENV/lib/$PY/site-packages/cuda" \
  "$VENV/lib/$PY/site-packages/cuda_bindings" \
  "$VENV/lib/$PY/site-packages/cuda_bindings-"* \
  "$VENV/lib/$PY/site-packages/cuda_pathfinder" \
  "$VENV/lib/$PY/site-packages/cuda_pathfinder-"* \
  "$VENV/lib/$PY/site-packages/cuda_toolkit" \
  "$VENV/lib/$PY/site-packages/cuda_toolkit-"* \
  2>/dev/null || true

SP="$VENV/lib/$PY/site-packages"
for pkg in nvidia_cublas nvidia_cuda_cupti nvidia_cuda_nvrtc nvidia_cuda_runtime \
  nvidia_cudnn_cu13 nvidia_cufft nvidia_cufile nvidia_curand nvidia_cusolver \
  nvidia_cusparse nvidia_cusparselt_cu13 nvidia_nccl_cu13 nvidia_nvjitlink \
  nvidia_nvshmem_cu13 nvidia_nvtx triton cuda_bindings cuda_pathfinder cuda_toolkit; do
  rm -rf "$SP/${pkg}" "$SP/${pkg}-"* 2>/dev/null || true
done
