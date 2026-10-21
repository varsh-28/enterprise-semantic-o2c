import re

ALLOWED_LABELS = {"Customer", "SalesOrder", "Delivery", "Invoice", "Payment", "SourceRecord"}
ALLOWED_RELS = {
    "HAS_CUSTOMER", "HAS_ORDER", "FOR_ORDER", "FOR_INVOICE",
    "HAS_SOURCE_RECORD", "POSSIBLE_MATCH",
}

_FORBIDDEN = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|FOREACH|LOAD|CALL|"
    r"ALTER|GRANT|DENY|REVOKE)\b",
    re.IGNORECASE,
)
_STRING_LITERAL = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
_TOKEN = re.compile(r"[\(\[]\s*\w*\s*:\s*([A-Za-z_]+)")
_STARTS = re.compile(r"^\s*(MATCH|OPTIONAL\s+MATCH)\b", re.IGNORECASE)
_HAS_LIMIT = re.compile(r"\bLIMIT\s+\d+\s*$", re.IGNORECASE)


class UnsafeCypherError(ValueError):
    pass


def enforce_read_only(query: str, max_rows: int = 200) -> str:
    """Validate a Cypher query and return it with a LIMIT guaranteed."""
    stripped = _STRING_LITERAL.sub("''", query).strip().rstrip(";").strip()

    if ";" in stripped:
        raise UnsafeCypherError("multiple statements are not allowed")
    if not _STARTS.match(stripped):
        raise UnsafeCypherError("query must start with MATCH or OPTIONAL MATCH")
    if not re.search(r"\bRETURN\b", stripped, re.IGNORECASE):
        raise UnsafeCypherError("query must contain RETURN")
    hit = _FORBIDDEN.search(stripped)
    if hit:
        raise UnsafeCypherError(f"forbidden keyword: {hit.group(1).upper()}")

    for token in _TOKEN.findall(stripped):
        if token not in ALLOWED_LABELS and token not in ALLOWED_RELS:
            raise UnsafeCypherError(f"label or relationship not in allowlist: {token}")

    safe = query.strip().rstrip(";").strip()
    if not _HAS_LIMIT.search(safe):
        safe = f"{safe} LIMIT {int(max_rows)}"
    return safe