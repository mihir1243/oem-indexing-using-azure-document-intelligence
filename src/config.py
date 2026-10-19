from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _max_dimensions_for_model(model_name: str) -> int:
    name = model_name.lower()
    if "large" in name:
        return 3072
    if "small" in name:
        return 1536
    return 1536


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    azure_search_endpoint: str
    azure_search_key: str
    azure_search_index_name: str = "oem-manuals-index"

    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    chunk_min_tokens: int = 500
    chunk_max_tokens: int = 1000
    chunk_overlap_tokens: int = 128
    embedding_batch_size: int = 100

    docling_do_ocr: bool = True
    docling_table_mode: Literal["accurate", "fast"] = "accurate"
    # Infer section-header depth (bookmarks, numbering, font style) instead of flat ## headings.
    docling_heading_hierarchy: bool = True

    # Set USE_SEMANTIC_SEARCH=true only if the index defines semantic configurations.
    use_semantic_search: bool = False
    semantic_configuration_name: str = "oem-semantic-config"
    vector_profile_name: str = "oem-vector-profile"

    use_scoring_profile: bool = False
    scoring_profile_name: str = "oem-diagnosis-boost"
    # Comma-separated section_tags values for tag boost (one Azure scoring parameter).
    scoring_boost_tags: str = "troubleshooting"
    scoring_boost_parameter_name: str = "boostTags"
    # Set true when the index default scoring profile requires tag parameters but
    # USE_SCORING_PROFILE=false (only field-weight boost on the profile).
    send_scoring_parameters: bool = False

    # Empty string disables writing markdown to disk.
    markdown_output_dir: str = "extracted/markdown"
    skip_extraction_if_markdown_exists: bool = True
    force_reextract: bool = False

    @field_validator(
        "azure_search_endpoint",
        "azure_search_key",
        "openai_api_key",
        mode="before",
    )
    @classmethod
    def strip_secrets(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_embedding_dimensions_for_model(self) -> Settings:
        max_dims = _max_dimensions_for_model(self.openai_embedding_model)
        if self.embedding_dimensions < 1:
            raise ValueError("EMBEDDING_DIMENSIONS must be at least 1.")
        if self.embedding_dimensions > max_dims:
            raise ValueError(
                f"{self.openai_embedding_model} supports at most {max_dims} dimensions, "
                f"but EMBEDDING_DIMENSIONS={self.embedding_dimensions}."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
