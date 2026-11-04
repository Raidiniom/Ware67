"""CSV helpers shared by the export routes and the product import."""
import csv
import io

from fastapi import Response

# Spreadsheets run a cell starting with one of these as a formula, and names and
# notes can come from anyone (including partner API keys).
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value) -> object:
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


def unescape_cell(value: str) -> str:
    """Undoes _safe_cell, so an exported file can be imported again unchanged."""
    if value.startswith("'") and value[1:].startswith(FORMULA_PREFIXES):
        return value[1:]
    return value


def csv_response(filename: str, header: list[str], rows) -> Response:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows([_safe_cell(cell) for cell in row] for row in rows)
    # The byte order mark tells Excel the file is UTF-8.
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
