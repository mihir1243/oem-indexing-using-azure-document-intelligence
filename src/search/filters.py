from __future__ import annotations


def build_filter(filters: dict) -> str | None:
    clauses: list[str] = []

    manufacturer = filters.get("manufacturer")
    if manufacturer:
        clauses.append(f"manufacturer eq '{_escape_odata(manufacturer)}'")

    manual_type = filters.get("manual_type")
    if manual_type:
        clauses.append(f"manual_type eq '{_escape_odata(manual_type)}'")

    model = filters.get("model") or filters.get("model_series")
    if model:
        clauses.append(f"model_series/any(m: m eq '{_escape_odata(model)}')")

    if not clauses:
        return None
    return " and ".join(clauses)


def _escape_odata(value: str) -> str:
    return value.replace("'", "''")
