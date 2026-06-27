"""Probe Firestore connection before standing up the MCP server.

Lists all document IDs in the users collection (so you can identify your UID),
then reads your user document and confirms the contacts array and its field shape.

Usage:
    CRM_SERVICE_ACCOUNT=~/.crm-secrets/serviceAccount.json python scripts/probe_firestore.py

Set CRM_USER_UID to read a specific user; otherwise the script reads the first
document it finds and prints its ID so you know what to set.
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore

EXPECTED_FIELDS = [
    "id",
    "firstName",
    "lastName",
    "name",
    "relationshipType",
    "lastContactedAt",
]


def main() -> None:
    sa_path = os.environ.get("CRM_SERVICE_ACCOUNT")
    if not sa_path:
        sys.exit("ERROR: CRM_SERVICE_ACCOUNT env var is not set")

    sa_path = os.path.expanduser(sa_path)
    if not os.path.isfile(sa_path):
        sys.exit(f"ERROR: service account file not found: {sa_path}")

    print(f"Service account : {sa_path}")

    cred = credentials.Certificate(sa_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    # --- Step 1: list users collection ---
    print("\n=== users collection document IDs ===")
    user_docs = list(db.collection("users").stream())
    if not user_docs:
        sys.exit("No documents found in users collection.")

    uids = [d.id for d in user_docs]
    for uid in uids:
        print(f"  {uid}")

    # --- Step 2: read target user document ---
    target_uid = os.environ.get("CRM_USER_UID") or uids[0]
    print(f"\n=== Reading users/{target_uid} ===")

    doc = db.collection("users").document(target_uid).get()
    if not doc.exists:
        sys.exit(f"Document users/{target_uid} does not exist.")

    data = doc.to_dict() or {}
    contacts = data.get("contacts", [])
    interactions = data.get("interactions", [])

    print(f"contacts     : {len(contacts)}")
    print(f"interactions : {len(interactions)}")

    if not contacts:
        print("\nWARNING: contacts array is empty.")
        return

    # --- Step 3: confirm field shape on first contact ---
    sample = contacts[0]
    print("\n=== Sample contact — expected fields ===")
    all_present = True
    for field in EXPECTED_FIELDS:
        value = sample.get(field, "<MISSING>")
        status = "OK " if field in sample else "MISSING"
        if status == "MISSING":
            all_present = False
        print(f"  [{status}] {field}: {json.dumps(value)}")

    print("\n=== All fields on sample contact ===")
    print(f"  {sorted(sample.keys())}")

    if all_present:
        print("\nFIRESTORE CONNECTION OK — all expected fields present.")
    else:
        print("\nWARNING: some expected fields are missing on the sample contact.")


if __name__ == "__main__":
    main()
