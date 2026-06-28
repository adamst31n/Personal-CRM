"""list_outreach_candidates: signal-gatherer for outreach prioritization.

Returns every non-muted contact with deterministic signals attached.
Does NOT compute a score or ranking — the agent does the judgment.
"""

from __future__ import annotations

from datetime import date

from .find_contact import _ms_to_iso_date

# Cadence defaults from the brief's confirmed schema reference.
_CADENCE_BY_REL_TYPE: dict[str, int] = {
    "Close Friend": 30,
    "Friend":       30,
    "Family":       30,
    "Professional": 60,
    "Acquaintance": 60,
}
_DEFAULT_CADENCE = 60


def _get_contact_frequency(contact: dict) -> int:
    """Return effective cadence in days: custom setting wins, else relationship-type default."""
    custom = contact.get("contactFrequency")
    if custom is not None:
        try:
            return int(custom)
        except (ValueError, TypeError):
            pass
    rel_type = contact.get("relationshipType") or ""
    return _CADENCE_BY_REL_TYPE.get(rel_type, _DEFAULT_CADENCE)


def _days_overdue(contact: dict, today: date) -> int | None:
    """Days since last contact minus effective cadence.

    Positive  → overdue (missed the window).
    Negative  → within cadence.
    None      → never contacted; the agent should treat this as maximally overdue.
    """
    last_ms = contact.get("lastContactedAt")
    if not last_ms:
        return None
    last_date = date.fromtimestamp(last_ms / 1000)
    days_since = (today - last_date).days
    return days_since - _get_contact_frequency(contact)


def _display_name(contact: dict) -> str:
    first = (contact.get("firstName") or "").strip()
    last = (contact.get("lastName") or "").strip()
    full = f"{first} {last}".strip()
    return full or contact.get("name") or contact.get("id", "?")


def list_outreach_candidates_impl(
    contacts: list[dict],
    *,
    only_overdue: bool = False,
    only_priority: bool = False,
    relationship_type: str | None = None,
) -> list[dict]:
    """Return non-muted contacts with outreach signals.

    Args:
        contacts:          contacts array from Firestore
        only_overdue:      if True, exclude contacts with days_overdue <= 0
                           (never-contacted contacts are always included)
        only_priority:     if True, only return contacts with priority == True
        relationship_type: if set, filter to this relationship type (case-insensitive)

    Returns:
        List of candidate dicts sorted by days_overdue descending
        (never-contacted floats to the top). Fields per candidate:
            id, name, relationshipType, priority, lastContactedAt (ISO or null),
            effectiveCadence (days), daysOverdue (int or null).
    """
    today = date.today()
    rel_filter = relationship_type.strip().lower() if relationship_type else None

    candidates: list[dict] = []
    for c in contacts:
        if c.get("muted"):
            continue

        if only_priority and not c.get("priority", False):
            continue

        if rel_filter is not None:
            rel = (c.get("relationshipType") or "").lower()
            if rel != rel_filter:
                continue

        overdue = _days_overdue(c, today)

        if only_overdue and overdue is not None and overdue <= 0:
            continue

        candidates.append({
            "id": c.get("id"),
            "name": _display_name(c),
            "relationshipType": c.get("relationshipType"),
            "priority": c.get("priority", False),
            "lastContactedAt": _ms_to_iso_date(c.get("lastContactedAt")),
            "effectiveCadence": _get_contact_frequency(c),
            "daysOverdue": overdue,
        })

    # Stable sort: most overdue first; None (never contacted) sorts to the top.
    candidates.sort(key=lambda r: (r["daysOverdue"] is not None, -(r["daysOverdue"] or 0)))

    return candidates
