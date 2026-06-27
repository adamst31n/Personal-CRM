"""find_contact: case-insensitive substring search over the contacts array."""

from __future__ import annotations


def find_contact_impl(name: str, contacts: list[dict]) -> list[dict]:
    """Return contacts whose firstName, lastName, or legacy name field
    contains *name* as a case-insensitive substring.

    Each result carries only the fields the MCP caller needs:
      id, name (display), relationshipType, lastContactedAt.
    Never writes.
    """
    query = name.strip().lower()
    if not query:
        return []

    results = []
    for c in contacts:
        first = c.get("firstName", "") or ""
        last = c.get("lastName", "") or ""
        legacy = c.get("name", "") or ""
        full_name = f"{first} {last}".strip()

        haystack = [
            first.lower(),
            last.lower(),
            full_name.lower(),
            legacy.lower(),
        ]

        if any(query in h for h in haystack):
            results.append({
                "id": c.get("id"),
                "name": full_name or legacy,
                "relationshipType": c.get("relationshipType"),
                "lastContactedAt": c.get("lastContactedAt"),
            })

    return results
