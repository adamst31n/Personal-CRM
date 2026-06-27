"""find_contact: case-insensitive substring search over the contacts array."""

from __future__ import annotations

from datetime import datetime


def _ms_to_iso_date(ms: int | None) -> str | None:
    """Convert epoch milliseconds to YYYY-MM-DD (local time).

    lastContactedAt is stored as epoch ms by the browser (Date.getTime()),
    where the source date is midnight in the user's local timezone.
    datetime.fromtimestamp (also local) round-trips correctly.
    Returning an ISO string prevents the agent from having to do epoch
    arithmetic, which is where the units mismatch (ms vs seconds) occurred.
    """
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


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
                "lastContactedAt": _ms_to_iso_date(c.get("lastContactedAt")),
            })

    return results
