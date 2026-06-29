"""Firestore connection and data access."""

from __future__ import annotations

import os

import firebase_admin
from firebase_admin import credentials, firestore

_db = None


def _init() -> firestore.Client:
    global _db
    if _db is not None:
        return _db

    sa_path = os.environ.get("CRM_SERVICE_ACCOUNT")
    if not sa_path:
        raise RuntimeError("CRM_SERVICE_ACCOUNT env var is not set")

    sa_path = os.path.expanduser(sa_path)
    if not os.path.isfile(sa_path):
        raise RuntimeError(f"Service account file not found: {sa_path}")

    if not firebase_admin._apps:
        cred = credentials.Certificate(sa_path)
        firebase_admin.initialize_app(cred)

    _db = firestore.client()
    return _db


def _read_user_doc() -> dict:
    """Single document read; shared by the public getters below."""
    db = _init()

    uid = os.environ.get("CRM_USER_UID")
    if not uid:
        raise RuntimeError("CRM_USER_UID env var is not set")

    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        raise RuntimeError(f"No Firestore document found at users/{uid}")

    return doc.to_dict() or {}


def get_contacts() -> list[dict]:
    """Return the contacts array from the current user's Firestore document."""
    return _read_user_doc().get("contacts", [])


def get_user_data() -> tuple[list[dict], list[dict]]:
    """Return (contacts, interactions) from a single document read.

    Use this when a tool needs both arrays to avoid paying for two reads.
    """
    data = _read_user_doc()
    return data.get("contacts", []), data.get("interactions", [])


def write_user_arrays(contacts: list[dict], interactions: list[dict]) -> None:
    """Overwrite the contacts and interactions fields in the user's document.

    Other top-level fields (e.g. settings) are left untouched because
    update() only modifies the specified keys.
    """
    db = _init()
    uid = os.environ.get("CRM_USER_UID")
    if not uid:
        raise RuntimeError("CRM_USER_UID env var is not set")
    db.collection("users").document(uid).update({
        "contacts": contacts,
        "interactions": interactions,
    })


def write_new_contact(new_contact: dict) -> None:
    """Append a new contact to the contacts array.

    Re-reads the document immediately before writing so the contacts list
    is fresh.  Does not touch the interactions array.
    """
    data = _read_user_doc()
    contacts = list(data.get("contacts", []))
    contacts.append(new_contact)
    interactions = list(data.get("interactions", []))
    write_user_arrays(contacts, interactions)


def write_interaction_batch(
    new_interactions: list[dict],
    contact_updates: dict[str, dict],
) -> None:
    """Append new_interactions and write updated lastContactedAt for affected contacts.

    Re-reads the document immediately before writing so the interactions list
    is fresh.  The lastContactedAt values come from contact_updates (precomputed
    by log_interaction_impl against the state read at call time).
    """
    data = _read_user_doc()

    interactions = list(data.get("interactions", []))
    interactions.extend(new_interactions)

    contacts = list(data.get("contacts", []))
    for c in contacts:
        cid = c.get("id")
        if cid in contact_updates:
            c["lastContactedAt"] = contact_updates[cid]["lastContactedAt_ms_would_write"]

    write_user_arrays(contacts, interactions)
