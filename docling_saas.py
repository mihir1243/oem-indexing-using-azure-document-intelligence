from pathlib import Path

from docling.service_client import DoclingServiceClient

from src.config import get_settings
from src.timing import configure_logging, log_step

PDF_PATH = Path("./manuals/CM20210119-674b3-bd997.pdf")
OUTPUT_PATH = Path("output.md")


def main() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.docling_saas_url or not settings.docling_saas_api_key:
        raise SystemExit(
            "Set DOCLING_SAAS_URL and DOCLING_SAAS_API_KEY in .env "
            "(see .env.example)."
        )

    with log_step("docling saas run", extra=PDF_PATH.name):
        with DoclingServiceClient(
            url=settings.docling_saas_url,
            api_key=settings.docling_saas_api_key,
        ) as client:
            with log_step("docling saas convert", extra=PDF_PATH.name):
                result = client.convert(source=PDF_PATH)

        with log_step("export markdown"):
            markdown = result.document.export_to_markdown()

        with log_step("write output", extra=str(OUTPUT_PATH)):
            OUTPUT_PATH.write_text(markdown, encoding="utf-8")

    print(f"Output written to {OUTPUT_PATH} ({len(markdown):,} chars)")


if __name__ == "__main__":
    main()
