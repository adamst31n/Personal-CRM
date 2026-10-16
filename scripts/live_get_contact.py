"""Run get_contact against live Firestore data — read-only, no writes.

Usage:
    python3.11 scripts/live_get_contact.py <contact_id>

Example:
    python3.11 scripts/live_get_contact.py <CONTACT_ID>
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.firestore_client import get_user_data
from mcp_server.tools.get_contact import get_contact_impl


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: python3.11 scripts/live_get_contact.py <contact_id>")

    contact_id = sys.argv[1]

    print("Fetching data from Firestore...")
    contacts, interactions = get_user_data()
    print(f"{len(contacts)} contacts, {len(interactions)} interactions loaded.\n")

    result = get_contact_impl(contact_id, contacts, interactions)
    if result is None:
        print(f"No contact found with id {contact_id!r}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
