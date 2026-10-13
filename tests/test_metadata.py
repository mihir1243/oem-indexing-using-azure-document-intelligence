from src.chunking.metadata import chunks_to_index_documents
from src.models import Chunk, ManualMetadata


def test_chunks_to_index_documents_maps_schema_fields():
    meta = ManualMetadata(
        manufacturer="GE Healthcare",
        model_series=["Voluson E10"],
        manual_type="service",
    )
    chunk = Chunk(
        id="abc123_000001_deadbeef",
        chunk_content="Engine > Troubleshooting\nCheck coolant level.",
        raw_text="Check coolant level.",
        chapter_title="Engine",
        section_title="Troubleshooting",
        section_path="Engine > Troubleshooting",
        page_number=42,
        char_offset=100,
        metadata=meta,
    )
    vector = [0.1, 0.2, 0.3]
    docs = chunks_to_index_documents([chunk], {chunk.id: vector})
    assert len(docs) == 1
    payload = docs[0].to_search_dict()
    assert payload["manufacturer"] == "GE Healthcare"
    assert payload["model_series"] == ["Voluson E10"]
    assert payload["manual_type"] == "service"
    assert payload["page_number"] == 42
    assert payload["content_vector"] == vector
