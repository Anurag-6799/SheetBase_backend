"""Tests for the sheet -> JSON transform and the query engine.

Pure functions, no network and no database, so this runs anywhere:

    python tests/test_transform.py     (or: pytest tests/)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.transform import apply_query, parse_filters, rows_to_records  # noqa: E402

# Ragged on purpose: Google truncates trailing empty cells, so real sheets look
# like this rather than a neat rectangle.
VALUES = [
    ["Name", "Price", "Status"],
    ["Widget", "10", "active"],
    ["Gadget", "9", "Active"],
    ["Doohickey", "100"],           # short row - Status omitted by Google
    ["", "", ""],                   # blank spacer row
    ["Thing", "2", "archived", "x"],  # extra cell beyond the header
]


def test_rows_to_records_shapes_ragged_rows():
    records = rows_to_records(VALUES)
    assert len(records) == 4, "blank spacer row should be dropped"
    assert records[0] == {"Name": "Widget", "Price": "10", "Status": "active"}
    assert records[2]["Status"] == "", "short row should pad, not raise"
    assert set(records[3]) == {"Name", "Price", "Status"}, "extra cell must not create a None key"


def test_rows_to_records_handles_empty_and_unnamed():
    assert rows_to_records([]) == []
    assert rows_to_records([["Name", ""]]) == []  # header only, no data rows
    named = rows_to_records([["Name", ""], ["a", "b"]])
    assert named[0] == {"Name": "a", "column_2": "b"}


def test_filter_is_case_insensitive():
    rows = apply_query(rows_to_records(VALUES), filters={"Status": "active"})
    assert [r["Name"] for r in rows] == ["Widget", "Gadget"], "'Active' must match 'active'"


def test_filters_apply_before_pagination():
    rows = apply_query(rows_to_records(VALUES), filters={"Status": "active"}, limit=1)
    assert len(rows) == 1 and rows[0]["Name"] == "Widget"


def test_numeric_sort_beats_string_sort():
    rows = apply_query(rows_to_records(VALUES), order_by="Price")
    assert [r["Price"] for r in rows] == ["2", "9", "10", "100"], "must sort numerically, not '10' < '9'"

    desc = apply_query(rows_to_records(VALUES), order_by="Price", descending=True)
    assert desc[0]["Price"] == "100"


def test_sort_on_missing_column_does_not_raise():
    rows = apply_query(rows_to_records(VALUES), order_by="NoSuchColumn")
    assert len(rows) == 4


def test_columns_projection_and_offset():
    rows = apply_query(rows_to_records(VALUES), columns=["Name"], offset=1, limit=2)
    assert rows == [{"Name": "Gadget"}, {"Name": "Doohickey"}]


def test_parse_filters_ignores_reserved_params():
    params = {"limit": "10", "offset": "0", "columns": "Name", "order_by": "Price", "order": "asc", "Status": "active"}
    assert parse_filters(params) == {"Status": "active"}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nAll transform tests passed.")
