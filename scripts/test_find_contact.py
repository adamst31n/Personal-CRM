"""Offline test harness for find_contact logic — no Firebase, no writes.

Exercises the matching function against a fixed set of synthetic contacts
so you can eyeball results before touching live data.

Usage:
    python scripts/test_find_contact.py              # runs built-in queries
    python scripts/test_find_contact.py "alice" "sm" # runs custom queries
"""

from __future__ import annotations

import json
import os
import sys

# Allow running from the project root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.tools.find_contact import find_contact_impl

SAMPLE_CONTACTS = [
    {
        "id": "uuid-001",
        "firstName": "Alice",
        "lastName": "Johnson",
        "name": "Alice Johnson",
        "relationshipType": "Close Friend",
        "lastContactedAt": 1_700_000_000_000,
    },
    {
        "id": "uuid-002",
        "firstName": "Bob",
        "lastName": "Smith",
        "name": "Bob Smith",
        "relationshipType": "Professional",
        "lastContactedAt": None,
    },
    {
        "id": "uuid-003",
        "firstName": "",
        "lastName": "",
        "name": "Carol Williams",   # legacy name-only contact
        "relationshipType": "Friend",
        "lastContactedAt": 1_710_000_000_000,
    },
    {
        "id": "uuid-004",
        "firstName": "David",
        "lastName": "Smithson",
        "name": "David Smithson",
        "relationshipType": "Acquaintance",
        "lastContactedAt": 1_720_000_000_000,
    },
]

DEFAULT_QUERIES = [
    "alice",        # exact firstName (case-insensitive)
    "SMITH",        # lastName substring — should match Bob Smith AND David Smithson
    "son",          # partial lastName — should match Alice Johnson + David Smithson
    "carol",        # legacy name field only
    "bob sm",       # full-name substring spanning firstName + lastName
    "z",            # no match
    "",             # empty — should return nothing
]


def run(query: str) -> None:
    results = find_contact_impl(query, SAMPLE_CONTACTS)
    label = repr(query) if query else repr(query) + " (empty)"
    print(f"Query {label:<16} → {len(results)} match(es)")
    for r in results:
        print(f"    {json.dumps(r)}")


if __name__ == "__main__":
    queries = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_QUERIES
    for q in queries:
        run(q)
    print("\nDone.")
