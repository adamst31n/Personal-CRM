"""Personal CRM MCP server — read-only, stdio transport.

Start with:
    python -m mcp_server.server

Required env vars (see .env.example):
    CRM_SERVICE_ACCOUNT  path to Firebase service account JSON
    CRM_USER_UID         your Firebase user UID
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP

from .firestore_client import get_contacts, get_user_data
from .tools.find_contact import find_contact_impl
from .tools.get_contact import get_contact_impl

mcp = FastMCP("personal-crm")


@mcp.tool()
def find_contact(name: str) -> list[dict]:
    """Search CRM contacts by name.

    Case-insensitive substring match across firstName, lastName, and the
    legacy name field. Returns zero or more matches; never writes.

    Args:
        name: Full or partial name to search for (e.g. "alice", "Smith").

    Returns:
        List of matching contacts, each with id, name, relationshipType,
        and lastContactedAt (epoch ms or null).
    """
    contacts = get_contacts()
    return find_contact_impl(name, contacts)


@mcp.tool()
def get_contact(contact_id: str) -> dict:
    """Fetch a contact's full profile and interaction history by ID.

    Use this after find_contact to get the complete record for a specific
    person.  Returns the full profile (name, relationship type, company,
    position, industry, how we met, contact frequency, priority, muted flag,
    and lastContactedAt as an ISO date) plus the full interaction history
    (date, type, notes) sorted most-recent first.

    Args:
        contact_id: The UUID id field of the contact (e.g. from find_contact).

    Returns:
        Dict with "profile" and "interactions" keys, or {"error": "..."} if
        no contact with that ID exists.  Never writes.
    """
    contacts, interactions = get_user_data()
    result = get_contact_impl(contact_id, contacts, interactions)
    if result is None:
        return {"error": f"No contact found with id {contact_id!r}"}
    return result


if __name__ == "__main__":
    mcp.run()
