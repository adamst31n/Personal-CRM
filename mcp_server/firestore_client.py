"""Firestore connection and data access. Read-only — never writes."""

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
