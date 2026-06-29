"""create_contact: validate, dedup-check, and build a new contact for Firestore."""

from __future__ import annotations

import time
import uuid

from .find_contact import find_contact_impl

_VALID_RELATIONSHIP_TYPES = {
    "Close Friend",
    "Friend",
    "Family",
    "Professional",
    "Acquaintance",
}
_RELATIONSHIP_TYPE_MAP: dict[str, str] = {rt.lower(): rt for rt in _VALID_RELATIONSHIP_TYPES}
_VALID_RELATIONSHIP_DISPLAY = "Close Friend, Friend, Family, Professional, Acquaintance"


def _normalize_relationship_type(raw: str) -> str | None:
    return _RELATIONSHIP_TYPE_MAP.get(raw.strip().lower())


def _dedup_check(first: str, last: str, contacts: list[dict]) -> list[dict]:
    """Return contacts that likely match the proposed first+last name.

    Uses intersection logic: a contact is flagged only if it matches BOTH
    the proposed firstName and lastName.  This avoids false positives from
    common first names (e.g. "Aaron" alone would match many contacts).

    Falls back to a single-field search if only one name part is provided.
    """
    if not first and not last:
        return []
    if not first:
        return find_contact_impl(last, contacts)
    if not last:
        return find_contact_impl(first, contacts)

    first_matches = {c["id"]: c for c in find_contact_impl(first, contacts)}
    last_matches = {c["id"]: c for c in find_contact_impl(last, contacts)}
    common_ids = set(first_matches) & set(last_matches)
    return [first_matches[cid] for cid in sorted(common_ids)]


def create_contact_impl(
    fields: dict,
    contacts: list[dict],
) -> dict:
    """Validate, dedup-check, and build a new contact record.

    Pure function — no Firestore write.  The caller (server.py) performs
    the actual write only when this returns {"valid": True, ...}.

    Returns one of three shapes:
        {"duplicate": True, "matches": [...]}   dedup guard fired; abort
        {"valid": False, "errors": [...]}        required-field or format error
        {"valid": True, "new_contact": {...}}    ready to write

    The new_contact dict matches the addContact() shape from relationship-crm.html:
        id, firstName, lastName, name (legacy), relationshipType, howWeMet,
        linkedin, company, position, industry, notes,
        birthdayMonth, birthdayDay, birthday (legacy),
        priority=False, muted=False, contactFrequency=None,
        createdAt (epoch ms), lastContactedAt=None
    """
    first = (fields.get("firstName") or "").strip()
    last = (fields.get("lastName") or "").strip()
    full_name = f"{first} {last}".strip()

    # ------------------------------------------------------------------ #
    # Step 1: dedup guard — runs before any validation                   #
    # The agent is expected to call find_contact first, but this is the  #
    # programmatic safety net against duplicates even if it doesn't.     #
    # ------------------------------------------------------------------ #
    matches = _dedup_check(first, last, contacts)
    if matches:
        return {"duplicate": True, "matches": matches}

    # ------------------------------------------------------------------ #
    # Step 2: validate required fields                                    #
    # ------------------------------------------------------------------ #
    errors: list[str] = []

    if not first:
        errors.append("missing required field 'firstName'")
    if not last:
        errors.append("missing required field 'lastName'")

    how_we_met = (fields.get("howWeMet") or "").strip()
    if not how_we_met:
        errors.append("missing required field 'howWeMet'")

    raw_rel = fields.get("relationshipType") or ""
    rel_type = _normalize_relationship_type(str(raw_rel))
    if not raw_rel:
        errors.append("missing required field 'relationshipType'")
    elif rel_type is None:
        errors.append(
            f"invalid relationshipType {raw_rel!r} — "
            f"valid values: {_VALID_RELATIONSHIP_DISPLAY}"
        )

    contact_frequency = fields.get("contactFrequency")
    if contact_frequency is not None:
        try:
            contact_frequency = int(contact_frequency)
            if contact_frequency <= 0:
                errors.append("contactFrequency must be a positive integer (days)")
                contact_frequency = None
        except (TypeError, ValueError):
            errors.append(f"contactFrequency must be an integer, got {contact_frequency!r}")
            contact_frequency = None

    if errors:
        return {"valid": False, "errors": errors}

    # ------------------------------------------------------------------ #
    # Step 3: build contact record — mirrors addContact() in the HTML app #
    # ------------------------------------------------------------------ #
    new_contact = {
        "id": str(uuid.uuid4()),
        "firstName": first,
        "lastName": last,
        "name": full_name,
        "relationshipType": rel_type,
        "howWeMet": how_we_met,
        "linkedin": (fields.get("linkedin") or "").strip(),
        "company": (fields.get("company") or "").strip(),
        "position": (fields.get("position") or "").strip(),
        "industry": (fields.get("industry") or "").strip(),
        "notes": (fields.get("notes") or "").strip(),
        "birthdayMonth": "",
        "birthdayDay": "",
        "birthday": "",
        "priority": False,
        "muted": False,
        "contactFrequency": contact_frequency,
        "createdAt": int(time.time() * 1000),
        "lastContactedAt": None,
    }

    return {"valid": True, "new_contact": new_contact}
