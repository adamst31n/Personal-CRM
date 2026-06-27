"""Run find_contact against live Firestore data — read-only, no writes.

Usage:
    python3 scripts/live_query.py "aaron"
    python3 scripts/live_query.py "smith" "carol"
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.firestore_client import get_contacts
from mcp_server.tools.find_contact import find_contact_impl


def main() -> None:
    queries = sys.argv[1:]
    if not queries:
        sys.exit("Usage: python3 scripts/live_query.py <name> [<name> ...]")

    print("Fetching contacts from Firestore...")
    contacts = get_contacts()
    print(f"{len(contacts)} contacts loaded.\n")

    for query in queries:
        results = find_contact_impl(query, contacts)
        print(f"Query {repr(query)} → {len(results)} match(es)")
        for r in results:
            print(f"    {json.dumps(r)}")
        print()


if __name__ == "__main__":
    main()
