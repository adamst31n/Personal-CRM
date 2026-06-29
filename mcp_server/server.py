"""Personal CRM MCP server — stdio transport.

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

from .firestore_client import get_contacts, get_user_data, write_interaction_batch, write_new_contact
from .tools.create_contact import create_contact_impl
from .tools.find_contact import find_contact_impl
from .tools.get_contact import get_contact_impl
from .tools.list_outreach_candidates import list_outreach_candidates_impl
from .tools.log_interaction import log_interaction_impl

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


@mcp.tool()
def log_interaction(entries: list[dict]) -> dict:
    """Log one or more interactions — validates, writes to Firestore, returns receipt.

    Accepts a batch of interaction entries.  Validates every entry before
    touching Firestore — rejects the entire batch if any entry fails.

    On success: appends all new interaction records to the interactions array,
    updates lastContactedAt for every affected contact (primary and tagged),
    and returns a receipt showing exactly what was written.

    Args:
        entries: List of dicts, each with:
            contactId      (str)    required — UUID from find_contact / get_contact
            date           (str)    required — YYYY-MM-DD (past or future)
            type           (str)    required — Call | Text | Email | In-Person |
                                              Video | LinkedIn
                                              ("In Person" is accepted as an alias
                                               for "In-Person"; case-insensitive)
            notes          (str)    optional
            taggedContacts ([str])  optional — other contact UUIDs in this interaction

    Returns:
        On validation error (nothing written):
            {"valid": False, "errors": [...]}
        On success (Firestore updated):
            {
              "valid": True,
              "written": True,
              "new_interactions": [...],
              "contact_updates": {
                  "<id>": {
                      "name": str,
                      "lastContactedAt_current": str | None,
                      "lastContactedAt_would_write": str | None,
                      "lastContactedAt_ms_would_write": int | None
                  }
              }
            }
    """
    contacts, interactions = get_user_data()
    result = log_interaction_impl(entries, contacts, interactions)
    if result["valid"]:
        write_interaction_batch(result["new_interactions"], result["contact_updates"])
        result["written"] = True
    return result


@mcp.tool()
def list_outreach_candidates(
    only_overdue: bool = False,
    only_priority: bool = False,
    relationship_type: str = "",
) -> list[dict]:
    """List non-muted contacts with outreach signals for the agent to weigh.

    Signal-gatherer only — returns raw signals, no score or ranking formula.
    The agent decides who to reach out to based on these signals plus context
    it holds (interaction quality, relationship value, user's career context).

    All filters are off by default; combine freely.

    Args:
        only_overdue:      If True, exclude contacts still within their cadence
                           window (days_overdue <= 0).  Never-contacted contacts
                           are always included regardless of this flag.
        only_priority:     If True, restrict to contacts marked priority=True.
        relationship_type: If non-empty, restrict to this relationship type
                           (case-insensitive). E.g. "Friend", "Professional".

    Returns:
        List of candidates sorted by days_overdue descending (never-contacted
        floats to the top).  Each candidate has:
            id               — contact UUID
            name             — display name
            relationshipType — e.g. "Friend", "Professional"
            priority         — bool
            lastContactedAt  — ISO date string (YYYY-MM-DD) or null
            effectiveCadence — int, days between contacts (custom or default)
            daysOverdue      — int (positive=overdue, negative=within cadence)
                               or null (never contacted)
    """
    contacts, _ = get_user_data()
    return list_outreach_candidates_impl(
        contacts,
        only_overdue=only_overdue,
        only_priority=only_priority,
        relationship_type=relationship_type or None,
    )


@mcp.tool()
def create_contact(
    firstName: str,
    lastName: str,
    howWeMet: str,
    relationshipType: str,
    company: str = "",
    position: str = "",
    industry: str = "",
    contactFrequency: int | None = None,
    linkedin: str = "",
    notes: str = "",
) -> dict:
    """Create a new contact — validates, dedup-checks, and writes to Firestore.

    Runs a dedup guard before creating: if any existing contact matches both
    the proposed firstName and lastName, returns the existing match(es) instead
    of writing.  The agent should surface "this person may already exist" to the
    user rather than creating a duplicate.

    Requires agent-layer confirmation before calling (not auto-approved).

    Args:
        firstName:       required — contact's first name
        lastName:        required — contact's last name
        howWeMet:        required — brief context (e.g. "college", "Transom colleague")
        relationshipType: required — one of: Close Friend, Friend, Family,
                          Professional, Acquaintance (case-insensitive)
        company:         optional
        position:        optional
        industry:        optional
        contactFrequency: optional — custom cadence in days (overrides the
                          default of 30 for friends/family or 60 for professional)
        linkedin:        optional — LinkedIn profile URL or handle
        notes:           optional — freeform notes

    Returns:
        Dedup hit (nothing written):
            {"duplicate": True, "matches": [...]}
        Validation error (nothing written):
            {"valid": False, "errors": [...]}
        Success (Firestore updated):
            {"valid": True, "written": True, "new_contact": {...}}
    """
    contacts = get_contacts()
    result = create_contact_impl(
        {
            "firstName": firstName,
            "lastName": lastName,
            "howWeMet": howWeMet,
            "relationshipType": relationshipType,
            "company": company,
            "position": position,
            "industry": industry,
            "contactFrequency": contactFrequency,
            "linkedin": linkedin,
            "notes": notes,
        },
        contacts,
    )
    if result.get("valid"):
        write_new_contact(result["new_contact"])
        result["written"] = True
    return result


if __name__ == "__main__":
    mcp.run()
