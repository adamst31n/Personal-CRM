"""Dry-run create_contact against live Firestore data — no writes performed.

Runs three scenarios:

  1. NEW CONTACT — valid new person, shows the would-write contact record
  2. DEDUP CATCH — "Aaron Farkas" already exists; guard fires, no creation
  3. INVALID FIELDS — missing required fields + bad relationshipType

Usage:
    python3.11 scripts/dry_run_create_contact.py
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.firestore_client import get_contacts
from mcp_server.tools.create_contact import create_contact_impl


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def main() -> None:
    print("Fetching contacts from Firestore...")
    contacts = get_contacts()
    print(f"{len(contacts)} contacts loaded.")

    # ------------------------------------------------------------------ #
    # Scenario 1: valid new contact — show would-write record             #
    # ------------------------------------------------------------------ #
    _section("SCENARIO 1 — new contact (expected: valid=True, new_contact)")

    new_person = {
        "firstName": "Jamie",
        "lastName": "Okonkwo",
        "howWeMet": "Met at a16z office hours event, March 2026",
        "relationshipType": "Professional",
        "company": "Benchmark Capital",
        "position": "Principal",
        "industry": "Venture Capital",
        "notes": "Interested in AI-ops tools, offered to intro to two portfolio founders.",
    }

    result = create_contact_impl(new_person, contacts)
    print(json.dumps(result, indent=2))

    # ------------------------------------------------------------------ #
    # Scenario 2: dedup guard — Aaron Farkas already exists              #
    # ------------------------------------------------------------------ #
    _section("SCENARIO 2 — dedup catch (expected: duplicate=True, no new_contact)")

    duplicate_attempt = {
        "firstName": "Aaron",
        "lastName": "Farkas",
        "howWeMet": "College",
        "relationshipType": "Friend",
    }

    result_dup = create_contact_impl(duplicate_attempt, contacts)
    print(json.dumps(result_dup, indent=2))

    # ------------------------------------------------------------------ #
    # Scenario 3: validation errors — missing required fields + bad type  #
    # ------------------------------------------------------------------ #
    _section("SCENARIO 3 — invalid fields (expected: valid=False, errors list)")

    invalid_attempt = {
        "firstName": "Robin",
        # lastName missing
        "howWeMet": "",             # empty — treated as missing
        "relationshipType": "Buddy",  # not a valid type
        "contactFrequency": -5,     # must be positive
    }

    result_invalid = create_contact_impl(invalid_attempt, contacts)
    print(json.dumps(result_invalid, indent=2))


if __name__ == "__main__":
    main()
