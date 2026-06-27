"""Remove one interaction by ID from Firestore and recompute lastContactedAt.

Reads the current document, finds the target interaction, removes it, then
recomputes lastContactedAt for the primary contact and any tagged contacts
before writing the updated arrays back.

Usage:
    python3.11 scripts/delete_interaction.py <interaction_id>

Example:
    python3.11 scripts/delete_interaction.py 8421deb3-7e0c-45be-bb0d-f8bbada3d630
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.firestore_client import get_user_data, write_user_arrays
from mcp_server.tools.find_contact import _ms_to_iso_date
from mcp_server.tools.log_interaction import _compute_last_contacted_ms, _contact_display_name


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: python3.11 scripts/delete_interaction.py <interaction_id>")

    target_id = sys.argv[1]

    print("Fetching Firestore data...")
    contacts, interactions = get_user_data()
    print(f"{len(contacts)} contacts, {len(interactions)} interactions loaded.")

    target = next((i for i in interactions if i.get("id") == target_id), None)
    if target is None:
        sys.exit(f"ERROR: no interaction found with id {target_id!r}")

    print(f"\nInteraction to delete:")
    print(json.dumps(target, indent=2))
    print()

    confirm = input("Delete? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted — nothing written.")
        sys.exit(0)

    updated_interactions = [i for i in interactions if i.get("id") != target_id]

    # Recompute lastContactedAt for every contact touched by this interaction.
    today_str = datetime.now().strftime("%Y-%m-%d")
    affected_ids = {target.get("contactId")} | set(target.get("taggedContacts") or [])
    contact_map = {c["id"]: c for c in contacts if c.get("id")}

    updated_contacts = [dict(c) for c in contacts]  # shallow-copy each contact dict
    for c in updated_contacts:
        cid = c.get("id")
        if cid not in affected_ids:
            continue
        old_ms = c.get("lastContactedAt")
        new_ms = _compute_last_contacted_ms(cid, updated_interactions, today_str)
        c["lastContactedAt"] = new_ms
        name = _contact_display_name(contact_map.get(cid, c))
        print(
            f"  {name}: lastContactedAt "
            f"{_ms_to_iso_date(old_ms) or 'null'} -> "
            f"{_ms_to_iso_date(new_ms) or 'null'}"
        )

    write_user_arrays(updated_contacts, updated_interactions)
    print(
        f"\nDone. Interactions: {len(interactions)} -> {len(updated_interactions)}."
    )


if __name__ == "__main__":
    main()
