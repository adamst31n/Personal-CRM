"""Dry-run log_interaction against live Firestore data — no writes performed.

Prints the full would-write payload: new interaction records + lastContactedAt
updates for every affected contact.  Runs two scenarios:

  1. VALID BATCH — two entries including a tagged participant
  2. INVALID BATCH — three entries with validation errors

Usage:
    python3.11 scripts/dry_run_log_interaction.py
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.firestore_client import get_user_data
from mcp_server.tools.log_interaction import log_interaction_impl

# Real contact IDs (confirmed against live Firestore)
FARKAS_ID = "6ca0693d-a0ce-4657-999f-1a75191046df"   # Aaron Farkas
KLEVAN_ID = "5735a96a-90aa-46cd-a740-e7bc5c75c3b7"   # Aaron Klevan


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def main() -> None:
    print("Fetching data from Firestore...")
    contacts, interactions = get_user_data()
    print(f"{len(contacts)} contacts, {len(interactions)} interactions loaded.")

    # ------------------------------------------------------------------ #
    # Scenario 1: valid batch — 2 entries, 3 affected contacts            #
    # Entry A: In-Person with Farkas (primary) + Klevan (tagged)          #
    # Entry B: Call with Klevan (primary, solo)                           #
    # ------------------------------------------------------------------ #
    _section("SCENARIO 1 — valid batch (expected: would-write payload)")

    valid_entries = [
        {
            "contactId": FARKAS_ID,
            "date": "2026-06-27",
            "type": "In Person",          # alias → should normalize to "In-Person"
            "notes": "Caught up over coffee, discussed startup ideas.",
            "taggedContacts": [KLEVAN_ID],
        },
        {
            "contactId": KLEVAN_ID,
            "date": "2026-06-25",
            "type": "Call",
            "notes": "Quick check-in, scheduling the next dinner.",
        },
    ]

    result = log_interaction_impl(valid_entries, contacts, interactions)
    print(json.dumps(result, indent=2))

    # ------------------------------------------------------------------ #
    # Scenario 2: invalid batch — should reject without writing anything  #
    # Three entries each with a distinct validation error                 #
    # ------------------------------------------------------------------ #
    _section("SCENARIO 2 — invalid batch (expected: errors, no would-write)")

    invalid_entries = [
        {
            "contactId": "00000000-0000-0000-0000-000000000000",  # unknown UUID
            "date": "2026-06-27",
            "type": "Call",
            "notes": "This contact doesn't exist.",
        },
        {
            "contactId": FARKAS_ID,
            "date": "27-06-2026",          # wrong format — DD-MM-YYYY
            "type": "Text",
            "notes": "Bad date format.",
        },
        {
            "contactId": KLEVAN_ID,
            "date": "2026-06-26",
            "type": "Smoke Signal",        # not a valid type
            "notes": "Invalid type.",
        },
    ]

    result_invalid = log_interaction_impl(invalid_entries, contacts, interactions)
    print(json.dumps(result_invalid, indent=2))


if __name__ == "__main__":
    main()
