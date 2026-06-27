"""get_contact: fetch one contact's full profile and interaction history by ID."""

from __future__ import annotations

from .find_contact import _ms_to_iso_date


def get_contact_impl(
    contact_id: str,
    contacts: list[dict],
    interactions: list[dict],
) -> dict | None:
    """Return the full profile and interaction history for contact_id.

    Returns None if no contact with that ID exists.

    Profile fields returned: id, firstName, lastName, name, relationshipType,
    contactFrequency, company, position, industry, howWeMet, priority, muted,
    lastContactedAt (ISO date string or null).

    Interaction history: every entry where contactId == contact_id (primary)
    OR contact_id appears in taggedContacts (participant), sorted most-recent
    first.  Each entry carries date (ISO string), type, and notes.
    Never writes.
    """
    contact = next((c for c in contacts if c.get("id") == contact_id), None)
    if contact is None:
        return None

    profile = {
        "id": contact_id,
        "firstName": contact.get("firstName"),
        "lastName": contact.get("lastName"),
        "name": contact.get("name"),
        "relationshipType": contact.get("relationshipType"),
        "contactFrequency": contact.get("contactFrequency"),
        "company": contact.get("company"),
        "position": contact.get("position"),
        "industry": contact.get("industry"),
        "howWeMet": contact.get("howWeMet"),
        "priority": contact.get("priority", False),
        "muted": contact.get("muted", False),
        "lastContactedAt": _ms_to_iso_date(contact.get("lastContactedAt")),
    }

    # Match interactions where this contact is primary OR tagged participant.
    contact_interactions = [
        i for i in interactions
        if i.get("contactId") == contact_id
        or contact_id in (i.get("taggedContacts") or [])
    ]

    # ISO date strings sort lexicographically, so reverse() gives most-recent first.
    contact_interactions.sort(key=lambda i: i.get("date", ""), reverse=True)

    history = [
        {
            "date": i.get("date"),
            "type": i.get("type"),
            "notes": i.get("notes") or None,
        }
        for i in contact_interactions
    ]

    return {"profile": profile, "interactions": history}
