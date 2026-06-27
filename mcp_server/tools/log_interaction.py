"""log_interaction: validate, structure, and write interactions to Firestore."""

from __future__ import annotations

import time
import uuid
from datetime import datetime

from .find_contact import _ms_to_iso_date

# Case-insensitive input → canonical stored form (as saved by the HTML app).
# "Social" is intentionally absent — it is not a real type in this data model.
# Only natural spelling variants of the six real types are accepted.
_CANONICAL_TYPES: dict[str, str] = {
    "call":      "Call",
    "text":      "Text",
    "email":     "Email",
    "in-person": "In-Person",
    "in person": "In-Person",  # space variant, normalizes to hyphen form
    "video":     "Video",
    "linkedin":  "LinkedIn",
}

# Human-readable list shown in validation error messages.
_VALID_TYPE_DISPLAY = "Call, Text, Email, In-Person (or 'In Person'), Video, LinkedIn"


def _normalize_type(raw: str) -> str | None:
    """Return the canonical type string, or None if the input is not recognized."""
    return _CANONICAL_TYPES.get(raw.strip().lower())


def _is_valid_date(date_str: str) -> bool:
    """True iff date_str is a parseable YYYY-MM-DD calendar date."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def _is_future(date_str: str, today_str: str) -> bool:
    """True iff date_str is strictly after today (ISO string comparison is correct)."""
    return date_str > today_str


def _compute_last_contacted_ms(
    contact_id: str,
    all_interactions: list[dict],
    today_str: str,
) -> int | None:
    """Mirror JS updateContactLastInteraction.

    Finds the most-recent non-future interaction for contact_id (as primary
    or tagged participant), returns epoch ms at midnight local time, or None
    if no past interactions exist.

    Epoch ms at midnight local mirrors JS: new Date(year, month-1, day).getTime()
    which is also midnight local.
    """
    contact_ixns = [
        i for i in all_interactions
        if i.get("contactId") == contact_id
        or contact_id in (i.get("taggedContacts") or [])
    ]
    past = [i for i in contact_ixns if (i.get("date") or "") <= today_str]
    if not past:
        return None
    most_recent_date = max(i.get("date", "") for i in past)
    dt = datetime.strptime(most_recent_date, "%Y-%m-%d")
    return int(dt.timestamp() * 1000)


def _contact_display_name(c: dict) -> str:
    first = (c.get("firstName") or "").strip()
    last = (c.get("lastName") or "").strip()
    full = f"{first} {last}".strip()
    return full or c.get("name") or c.get("id", "?")


def log_interaction_impl(
    entries: list[dict],
    contacts: list[dict],
    existing_interactions: list[dict],
) -> dict:
    """Validate and build the write payload for a batch of interaction entries.

    Pure function — no Firestore write.  The caller (server.py) performs the
    actual write after inspecting the returned payload.

    Args:
        entries: List of dicts, each with:
            contactId      (str)    required — primary contact UUID
            date           (str)    required — YYYY-MM-DD
            type           (str)    required — see _CANONICAL_TYPES for accepted values
            notes          (str)    optional
            taggedContacts ([str])  optional — list of additional contact UUIDs

        contacts:              current contacts array from Firestore
        existing_interactions: current interactions array from Firestore

    Returns:
        On validation failure:
            {"valid": False, "errors": [...]}

        On success:
            {
              "valid": True,
              "new_interactions": [...],   # records ready to append
              "contact_updates": {         # lastContactedAt per affected contact
                  "<id>": {
                      "name": str,
                      "lastContactedAt_current": str | None,
                      "lastContactedAt_would_write": str | None,
                      "lastContactedAt_ms_would_write": int | None,
                  }
              }
            }
    """
    contact_map: dict[str, dict] = {c["id"]: c for c in contacts if c.get("id")}

    # ------------------------------------------------------------------ #
    # Step 1: validate every entry — collect all errors before rejecting  #
    # ------------------------------------------------------------------ #
    errors: list[str] = []
    for idx, entry in enumerate(entries):
        label = f"entry[{idx}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: expected an object, got {type(entry).__name__}")
            continue

        contact_id = entry.get("contactId")
        if not contact_id:
            errors.append(f"{label}: missing required field 'contactId'")
        elif contact_id not in contact_map:
            errors.append(f"{label}: unknown contactId {contact_id!r} — not in contacts")

        date_val = entry.get("date")
        if not date_val:
            errors.append(f"{label}: missing required field 'date'")
        elif not _is_valid_date(str(date_val)):
            errors.append(
                f"{label}: invalid date {date_val!r} — expected YYYY-MM-DD"
            )

        raw_type = entry.get("type")
        if not raw_type:
            errors.append(f"{label}: missing required field 'type'")
        else:
            if _normalize_type(str(raw_type)) is None:
                errors.append(
                    f"{label}: unknown type {raw_type!r} — "
                    f"valid values: {_VALID_TYPE_DISPLAY}"
                )

        for tagged_id in entry.get("taggedContacts") or []:
            if tagged_id not in contact_map:
                errors.append(
                    f"{label}: unknown taggedContacts entry {tagged_id!r} — not in contacts"
                )

    if errors:
        return {"valid": False, "errors": errors}

    # ------------------------------------------------------------------ #
    # Step 2: build new interaction records (addInteraction shape)        #
    # ------------------------------------------------------------------ #
    now_ms = int(time.time() * 1000)
    new_records: list[dict] = []
    for entry in entries:
        new_records.append({
            "id": str(uuid.uuid4()),
            "contactId": entry["contactId"],
            "taggedContacts": list(entry.get("taggedContacts") or []),
            "date": entry["date"],
            "type": _normalize_type(entry["type"]),
            "notes": entry.get("notes") or "",
            "createdAt": now_ms,
        })

    # ------------------------------------------------------------------ #
    # Step 3: compute lastContactedAt for every affected contact          #
    # ------------------------------------------------------------------ #
    today_str = datetime.now().strftime("%Y-%m-%d")

    affected_ids: set[str] = set()
    for r in new_records:
        affected_ids.add(r["contactId"])
        affected_ids.update(r["taggedContacts"])

    # Merge existing interactions with the new ones for the computation.
    merged = existing_interactions + new_records

    contact_updates: dict[str, dict] = {}
    for cid in sorted(affected_ids):
        c = contact_map[cid]
        current_ms = c.get("lastContactedAt")
        new_ms = _compute_last_contacted_ms(cid, merged, today_str)
        contact_updates[cid] = {
            "name": _contact_display_name(c),
            "lastContactedAt_current": _ms_to_iso_date(current_ms),
            "lastContactedAt_would_write": _ms_to_iso_date(new_ms),
            "lastContactedAt_ms_would_write": new_ms,
        }

    return {
        "valid": True,
        "new_interactions": new_records,
        "contact_updates": contact_updates,
    }
