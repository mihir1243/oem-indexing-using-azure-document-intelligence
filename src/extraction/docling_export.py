from __future__ import annotations

from typing import Any

from typing_extensions import override

from docling_core.transforms.serializer.base import BaseDocSerializer, SerializationResult
from docling_core.transforms.serializer.common import create_ser_result
from docling_core.transforms.serializer.markdown import (
    MarkdownDocSerializer,
    MarkdownParams,
    MarkdownTableSerializer,
    _caption_goes_after,
    _should_use_legacy_annotations,
)
from docling_core.types.doc import DoclingDocument, TableItem
from docling_core.types.doc.document import DEFAULT_CONTENT_LAYERS, DOCUMENT_TOKENS_EXPORT_LABELS

from src.models import PageSpan


class HtmlTableSerializer(MarkdownTableSerializer):
    """Serialize Docling tables as HTML while keeping markdown for other content."""

    @override
    def serialize(
        self,
        *,
        item: TableItem,
        doc_serializer: BaseDocSerializer,
        doc: DoclingDocument,
        **kwargs: Any,
    ) -> SerializationResult:
        if kwargs.get("_nested_in_table"):
            return super().serialize(
                item=item,
                doc_serializer=doc_serializer,
                doc=doc,
                **kwargs,
            )

        params = MarkdownParams(**kwargs)
        res_parts: list[SerializationResult] = []

        cap_res = doc_serializer.serialize_captions(item=item, **kwargs)
        cap_after = _caption_goes_after(item, doc, params, standard_after=False)
        if cap_res.text and not cap_after:
            res_parts.append(cap_res)

        if item.self_ref not in doc_serializer.get_excluded_refs(**kwargs):
            if _should_use_legacy_annotations(params=params, item=item):
                ann_res = doc_serializer.serialize_annotations(item=item, **kwargs)
                if ann_res.text:
                    res_parts.append(ann_res)

            table_html = item.export_to_html(doc=doc, add_caption=False).strip()
            if table_html:
                res_parts.append(create_ser_result(text=table_html, span_source=item))

        if cap_res.text and cap_after:
            res_parts.append(cap_res)

        text_res = "\n\n".join(part.text for part in res_parts if part.text)
        span_source = res_parts if res_parts else item
        return create_ser_result(text=text_res, span_source=span_source)


def export_docling_markdown(doc: DoclingDocument, *, page_no: int | None = None) -> str:
    params = MarkdownParams(
        labels=DOCUMENT_TOKENS_EXPORT_LABELS,
        layers=DEFAULT_CONTENT_LAYERS,
        pages={page_no} if page_no is not None else None,
        escape_html=True,
        escape_underscores=True,
        compact_tables=False,
    )
    serializer = MarkdownDocSerializer(
        doc=doc,
        table_serializer=HtmlTableSerializer(),
        params=params,
    )
    return serializer.serialize().text


def build_markdown_and_page_map(doc: DoclingDocument) -> tuple[str, list[PageSpan]]:
    num_pages = doc.num_pages()
    if num_pages < 1:
        markdown = export_docling_markdown(doc)
        if not markdown:
            return "", []
        return markdown, [PageSpan(start=0, end=len(markdown), page_number=1)]

    parts: list[str] = []
    spans: list[PageSpan] = []
    offset = 0
    for page_no in range(1, num_pages + 1):
        if parts:
            parts.append("\n")
            offset += 1
        start = offset
        page_md = export_docling_markdown(doc, page_no=page_no)
        parts.append(page_md)
        offset += len(page_md)
        spans.append(PageSpan(start=start, end=offset, page_number=page_no))

    return "".join(parts), spans
