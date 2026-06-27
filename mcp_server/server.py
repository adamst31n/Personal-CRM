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

from .firestore_client import get_contacts
from .tools.find_contact import find_contact_impl

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


if __name__ == "__main__":
    mcp.run()
