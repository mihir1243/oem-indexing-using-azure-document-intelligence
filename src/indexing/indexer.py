from __future__ import annotations

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from src.config import Settings, get_settings
from src.models import IndexDocument


class SearchIndexer:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = SearchClient(
            endpoint=self._settings.azure_search_endpoint,
            index_name=self._settings.azure_search_index_name,
            credential=AzureKeyCredential(self._settings.azure_search_key),
        )

    def validate_connection(self) -> None:
        next(self._client.search(search_text="*", top=1), None)

    def delete_manual_chunks(
        self,
        manual_id_prefix: str,
        manufacturer: str,
        manual_type: str,
    ) -> int:
        """Delete chunks for one manual without OData startswith (not supported on all indexes)."""
        safe_manufacturer = manufacturer.replace("'", "''")
        safe_manual_type = manual_type.replace("'", "''")
        filter_expr = (
            f"manufacturer eq '{safe_manufacturer}' and manual_type eq '{safe_manual_type}'"
        )
        candidate_ids = self._collect_ids(filter_expr)
        needle = f"{manual_id_prefix}_"
        ids = [doc_id for doc_id in candidate_ids if doc_id.startswith(needle)]
        if not ids:
            return 0

        deleted = 0
        batch_size = 1000
        for start in range(0, len(ids), batch_size):
            batch = [{"id": doc_id} for doc_id in ids[start : start + batch_size]]
            result = self._client.delete_documents(documents=batch)
            deleted += sum(1 for item in result if item.succeeded)
        return deleted

    def delete_by_manufacturer_and_type(self, manufacturer: str, manual_type: str) -> int:
        safe_manufacturer = manufacturer.replace("'", "''")
        safe_manual_type = manual_type.replace("'", "''")
        filter_expr = (
            f"manufacturer eq '{safe_manufacturer}' and manual_type eq '{safe_manual_type}'"
        )
        ids = self._collect_ids(filter_expr)
        if not ids:
            return 0

        deleted = 0
        batch_size = 1000
        for start in range(0, len(ids), batch_size):
            batch = [{"id": doc_id} for doc_id in ids[start : start + batch_size]]
            result = self._client.delete_documents(documents=batch)
            deleted += sum(1 for item in result if item.succeeded)
        return deleted

    def upload_documents(self, documents: list[IndexDocument]) -> int:
        if not documents:
            return 0

        uploaded = 0
        errors: list[str] = []
        batch_size = 1000
        payload = [doc.to_search_dict() for doc in documents]

        for start in range(0, len(payload), batch_size):
            batch = payload[start : start + batch_size]
            result = self._client.merge_or_upload_documents(documents=batch)
            for item in result:
                if item.succeeded:
                    uploaded += 1
                else:
                    errors.append(f"{item.key}: {item.error_message}")

        if errors:
            preview = "; ".join(errors[:5])
            extra = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
            raise RuntimeError(
                f"Azure Search upload failed for {len(errors)} document(s): {preview}{extra}"
            )

        return uploaded

    def count_documents(self, filter_expr: str | None = None) -> int:
        total = 0
        skip = 0
        page_size = 1000
        while True:
            results = self._client.search(
                search_text="*",
                filter=filter_expr,
                select=["id"],
                top=page_size,
                skip=skip,
                include_total_count=True if skip == 0 else None,
            )
            if skip == 0 and results.get_count() is not None:
                return int(results.get_count())
            page_ids = [doc["id"] for doc in results if doc.get("id")]
            if not page_ids:
                break
            total += len(page_ids)
            skip += len(page_ids)
            if len(page_ids) < page_size:
                break
        return total

    def _collect_ids(self, filter_expr: str) -> list[str]:
        ids: list[str] = []
        skip = 0
        page_size = 1000
        while True:
            results = self._client.search(
                search_text="*",
                filter=filter_expr,
                select=["id"],
                top=page_size,
                skip=skip,
            )
            page_ids = [doc["id"] for doc in results if doc.get("id")]
            if not page_ids:
                break
            ids.extend(page_ids)
            skip += len(page_ids)
            if len(page_ids) < page_size:
                break
        return ids
