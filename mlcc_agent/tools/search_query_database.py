"""search_query_database tool – free-form SQL query against the contiguous-condition view.

In production, this tool connects to the real PostgreSQL database and executes
a parameterised query against public.mdh_contiguous_condition_view_dsgnagent.

This mock version simulates the query against sample data so the agent
dialogue flow can be tested without a real DB connection.
"""

import os
import re

# ---------------------------------------------------------------------------
# Sample data – mirrors rows that would exist in the real view.
# In production this list is replaced by actual DB results.
# ---------------------------------------------------------------------------
_SAMPLE_ROWS = [
    {"chip_prod_id": "CL32A106KOY8NNE"},
    {"chip_prod_id": "CL32A106MOY8NNC"},
    {"chip_prod_id": "CL32B106KOY8NNE"},
    {"chip_prod_id": "CL32B106MOY8NNC"},
    {"chip_prod_id": "CL32A475KOY8NNE"},
    {"chip_prod_id": "CL32A475MOY8NNC"},
    {"chip_prod_id": "CL03A475MR3CNNC"},
    {"chip_prod_id": "CL03A475MR3CNNE"},
    {"chip_prod_id": "CL03X475MS3CNWC"},
    {"chip_prod_id": "CL10A106MQ8NNNC"},
    {"chip_prod_id": "CL10A106MQ8NNNE"},
    {"chip_prod_id": "CL10B225KP8NNNC"},
    {"chip_prod_id": "CL21A106KPFNNNE"},
    {"chip_prod_id": "CL21B106KOQNNNE"},
    {"chip_prod_id": "CL32A226MOY8NNC"},
    {"chip_prod_id": "CL32X106KOY8NNE"},
    {"chip_prod_id": "CL43A106MOA8NNC"},
    {"chip_prod_id": "CL43B106KOA8NNE"},
    {"chip_prod_id": "CL21A475KP8NNNC"},
    {"chip_prod_id": "CL10X475MS8CNWC"},
]


def search_query_database(query: str) -> dict:
    """Execute a SQL SELECT query against public.mdh_contiguous_condition_view_dsgnagent.

    Use this tool to search for contiguous (adjacent) chip products by writing
    a SQL query.  The target table is:

        public.mdh_contiguous_condition_view_dsgnagent

    Typical usage – find chip_prod_id rows matching a pattern:

        SELECT chip_prod_id
        FROM public.mdh_contiguous_condition_view_dsgnagent
        WHERE chip_prod_id ILIKE '%CL32%106%O%'

    The query MUST be a SELECT statement (read-only).  INSERT / UPDATE / DELETE
    are rejected.

    Args:
        query: A SQL SELECT query string.  Use ILIKE with '%' wildcards for
               pattern matching on chip_prod_id.
               Examples:
                 "SELECT chip_prod_id FROM public.mdh_contiguous_condition_view_dsgnagent WHERE chip_prod_id ILIKE '%CL32%106%'"
                 "SELECT chip_prod_id FROM public.mdh_contiguous_condition_view_dsgnagent WHERE chip_prod_id ILIKE 'CL32_106_O%'"

    Returns:
        A dict with 'status', 'query', 'row_count', and 'rows'.
        Each element in 'rows' is a dict with the selected column(s).
    """
    sql = query.strip().rstrip(";")

    # ── Safety: only allow SELECT ──────────────────────────────────────
    if not sql.upper().startswith("SELECT"):
        return {
            "status": "error",
            "message": "Only SELECT queries are allowed.",
            "query": query,
            "row_count": 0,
            "rows": [],
        }

    # ── Production path (when DATABASE_URL is set) ─────────────────────
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return _execute_real_query(database_url, sql)

    # ── Mock path – simulate ILIKE matching against sample data ────────
    return _execute_mock_query(sql)


# -----------------------------------------------------------------------
# Production helper – uses psycopg2
# -----------------------------------------------------------------------
def _execute_real_query(database_url: str, sql: str) -> dict:
    """Execute the query against a real PostgreSQL database."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        return {
            "status": "error",
            "message": "psycopg2 is not installed. Run: pip install psycopg2-binary",
            "query": sql,
            "row_count": 0,
            "rows": [],
        }

    try:
        conn = psycopg2.connect(database_url)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                rows = [dict(r) for r in cur.fetchall()]
            return {
                "status": "success",
                "query": sql,
                "row_count": len(rows),
                "rows": rows,
            }
        finally:
            conn.close()
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "query": sql,
            "row_count": 0,
            "rows": [],
        }


# -----------------------------------------------------------------------
# Mock helper – parse the WHERE clause and simulate ILIKE
# -----------------------------------------------------------------------
def _execute_mock_query(sql: str) -> dict:
    """Simulate the query against _SAMPLE_ROWS for testing."""
    # Try to extract an ILIKE pattern from the SQL
    ilike_match = re.search(
        r"chip_prod_id\s+ILIKE\s+'([^']+)'", sql, re.IGNORECASE
    )
    like_match = re.search(
        r"chip_prod_id\s+LIKE\s+'([^']+)'", sql, re.IGNORECASE
    )

    pattern_str = None
    if ilike_match:
        pattern_str = ilike_match.group(1)
    elif like_match:
        pattern_str = like_match.group(1)

    if pattern_str is None:
        # No recognisable WHERE filter → return all rows
        rows = list(_SAMPLE_ROWS)
    else:
        rows = [r for r in _SAMPLE_ROWS if _ilike(r["chip_prod_id"], pattern_str)]

    # Determine which columns were selected
    select_match = re.search(r"SELECT\s+(.+?)\s+FROM", sql, re.IGNORECASE)
    if select_match:
        cols_raw = select_match.group(1).strip()
        if cols_raw == "*":
            selected_cols = None  # all columns
        else:
            selected_cols = [c.strip() for c in cols_raw.split(",")]
    else:
        selected_cols = None

    if selected_cols:
        rows = [{c: r.get(c) for c in selected_cols} for r in rows]

    return {
        "status": "success",
        "query": sql,
        "row_count": len(rows),
        "rows": rows,
    }


def _ilike(value: str, pattern: str) -> bool:
    """Simulate SQL ILIKE: case-insensitive, '%' = any chars, '_' = single char."""
    regex = "^"
    for ch in pattern:
        if ch == "%":
            regex += ".*"
        elif ch == "_":
            regex += "."
        else:
            regex += re.escape(ch)
    regex += "$"
    return bool(re.match(regex, value, re.IGNORECASE))
