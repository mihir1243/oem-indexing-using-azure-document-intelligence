from __future__ import annotations

from functools import lru_cache

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

    azure_doc_intelligence_endpoint: str
    azure_doc_intelligence_key: str

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

    # auto: PyMuPDF when the PDF has enough selectable text; else Azure Document Intelligence
    extraction_backend: str = "auto"
    pymupdf_min_chars_per_page: int = 40
    pymupdf_min_text_page_fraction: float = 0.25
    # Strip repeating page header/footer bands (can remove body text on some PDFs)
    pymupdf_strip_page_header_footer: bool = False
    # Table format in pymupdf4llm output: markdown (GFM pipes) or html (like Azure DI)
    pymupdf_table_output: str = "html"

    @field_validator("extraction_backend", mode="before")
    @classmethod
    def normalize_extraction_backend(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @model_validator(mode="after")
    def validate_extraction_backend(self) -> Settings:
        allowed = {"auto", "pymupdf", "azure"}
        if self.extraction_backend not in allowed:
            raise ValueError(
                f"EXTRACTION_BACKEND must be one of {sorted(allowed)}, "
                f"got {self.extraction_backend!r}."
            )
        if not 0 < self.pymupdf_min_text_page_fraction <= 1:
            raise ValueError("PYMUPDF_MIN_TEXT_PAGE_FRACTION must be between 0 and 1.")
        if self.pymupdf_min_chars_per_page < 1:
            raise ValueError("PYMUPDF_MIN_CHARS_PER_PAGE must be at least 1.")
        if self.pymupdf_table_output not in {"markdown", "html"}:
            raise ValueError(
                "PYMUPDF_TABLE_OUTPUT must be 'markdown' or 'html'."
            )
        return self

    @field_validator(
        "azure_doc_intelligence_endpoint",
        "azure_doc_intelligence_key",
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
