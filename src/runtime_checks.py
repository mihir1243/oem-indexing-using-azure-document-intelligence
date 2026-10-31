"""Fail fast when the container image is missing Docling runtime deps."""

from __future__ import annotations


def verify_docling_runtime() -> None:
    try:
        import cv2  # noqa: F401  # docling_ibm_models table structure
    except ImportError as exc:
        raise RuntimeError(
            "Missing opencv (cv2). Install opencv-python-headless in the image and redeploy. "
            "Manual pip install in a running Azure replica usually does not affect the API "
            "process until restart, and is lost on the next scale/restart."
        ) from exc
