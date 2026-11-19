"""Native HTML for complete tables, with the existing cell window for sparse data."""

from html import escape
from urllib.parse import urlencode

from docling_core.transforms.serializer.common import create_ser_result
from docling_core.transforms.serializer.html import HTMLTableSerializer


class TableView(HTMLTableSerializer):
    def __init__(self, version: str | None):
        self.version = version

    def serialize(self, *, item, doc_serializer, doc, **kwargs):
        data = item.data
        query = dict(ref=item.self_ref)
        if self.version:
            query["version"] = self.version
        link = f'<p><a href="cells?{escape(urlencode(query))}">Tabellenzellen öffnen · {data.num_rows} × {data.num_cols}</a></p>'
        covered = sum(cell.row_span * cell.col_span for cell in data.table_cells)
        if covered >= data.num_rows * data.num_cols and data.table_cells:
            native = super().serialize(
                item=item, doc_serializer=doc_serializer, doc=doc, **kwargs
            )
            return create_ser_result(text=native.text + link, span_source=[native])
        return create_ser_result(
            text=link,
            span_source=item,
        )
