"""Pure sheet -> JSON transformation and the query engine.

Deliberately free of I/O: no Google, no Redis, no database. Everything here is a
plain function over plain data, which is what makes it the one part of the
service worth unit testing directly (see tests/test_transform.py).
"""
from typing import Any, Dict, List, Optional, Sequence

# Query params that drive the engine itself and are therefore never treated as
# column filters.
RESERVED_PARAMS = {"columns", "limit", "offset", "order_by", "order"}


def rows_to_records(values: Sequence[Sequence[Any]]) -> List[Dict[str, Any]]:
    """Turn raw Sheets `values` (a list of rows) into a list of JSON objects.

    The first row is the header. Google truncates trailing empty cells, so rows
    come back ragged - short rows are padded and over-long rows are ignored past
    the last named column, otherwise a single stray cell would produce records
    with a `None` key.
    """
    if not values:
        return []

    headers = [str(h).strip() for h in values[0]]
    # An unnamed column cannot be addressed in a query, so give it a stable name.
    headers = [h if h else f"column_{i + 1}" for i, h in enumerate(headers)]

    records: List[Dict[str, Any]] = []
    for row in values[1:]:
        if not any(str(cell).strip() for cell in row):
            continue  # skip blank spacer rows
        record = {header: (row[i] if i < len(row) else "") for i, header in enumerate(headers)}
        records.append(record)
    return records


def apply_query(
    records: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
    filters: Optional[Dict[str, str]] = None,
    order_by: Optional[str] = None,
    descending: bool = False,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Filter, sort, paginate and project records - in that order.

    Filtering before pagination matters: `?status=active&limit=10` must mean the
    first ten active rows, not "the first ten rows, of which some are active".
    """
    result = records

    if filters:
        # Case-insensitive equality: sheet data is hand-typed, so exact-match
        # would surprise people who wrote "Active" and queried "active".
        result = [
            r for r in result
            if all(str(r.get(k, "")).strip().lower() == str(v).strip().lower() for k, v in filters.items())
        ]

    if order_by:
        # Missing keys sort as empty rather than raising - a sheet column can be
        # renamed at any time and a stale bookmark should not 500.
        result = sorted(result, key=lambda r: _sort_key(r.get(order_by, "")), reverse=descending)

    if offset:
        result = result[offset:]
    if limit is not None:
        result = result[:limit]

    if columns:
        result = [{c: r.get(c, "") for c in columns} for r in result]

    return result


def _sort_key(value: Any):
    """Sort numerically when the whole column looks numeric, else as text.

    Sheets hands back everything as strings, so "10" would otherwise sort before
    "9".
    """
    text = str(value).strip()
    try:
        return (0, float(text), "")
    except ValueError:
        return (1, 0.0, text.lower())


def parse_filters(query_params: Dict[str, str]) -> Dict[str, str]:
    """Any query param that is not a reserved keyword is a column filter."""
    return {k: v for k, v in query_params.items() if k not in RESERVED_PARAMS}
