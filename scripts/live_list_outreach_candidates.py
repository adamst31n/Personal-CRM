"""Run list_outreach_candidates against live Firestore data — read-only, no writes.

Usage:
    python3.11 scripts/live_list_outreach_candidates.py [--only-overdue] [--only-priority] [--rel-type <type>]

Examples:
    python3.11 scripts/live_list_outreach_candidates.py
    python3.11 scripts/live_list_outreach_candidates.py --only-overdue
    python3.11 scripts/live_list_outreach_candidates.py --only-priority --only-overdue
    python3.11 scripts/live_list_outreach_candidates.py --rel-type Professional
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.firestore_client import get_user_data
from mcp_server.tools.list_outreach_candidates import list_outreach_candidates_impl


def main() -> None:
    parser = argparse.ArgumentParser(description="List outreach candidates from live Firestore data.")
    parser.add_argument("--only-overdue", action="store_true", help="Exclude contacts within cadence window")
    parser.add_argument("--only-priority", action="store_true", help="Only priority contacts")
    parser.add_argument("--rel-type", default=None, help="Filter by relationship type (e.g. Professional)")
    args = parser.parse_args()

    print("Fetching data from Firestore...")
    contacts, _ = get_user_data()
    print(f"{len(contacts)} contacts loaded.\n")

    candidates = list_outreach_candidates_impl(
        contacts,
        only_overdue=args.only_overdue,
        only_priority=args.only_priority,
        relationship_type=args.rel_type,
    )

    today = date.today()
    active_filters = []
    if args.only_overdue:
        active_filters.append("only_overdue=True")
    if args.only_priority:
        active_filters.append("only_priority=True")
    if args.rel_type:
        active_filters.append(f"relationship_type={args.rel_type!r}")
    filter_str = ", ".join(active_filters) if active_filters else "none"

    print(f"Candidates: {len(candidates)}  |  Filters: {filter_str}  |  Today: {today}\n")

    if not candidates:
        print("(no candidates match the given filters)")
        return

    # Column widths
    name_w   = max(len("Name"),        max(len(c["name"]) for c in candidates))
    rel_w    = max(len("Rel Type"),     max(len(c["relationshipType"] or "") for c in candidates))
    last_w   = len("Last Contact")
    cad_w    = len("Cadence")
    due_w    = len("Days Overdue")
    pri_w    = len("Pri")

    header = (
        f"{'Name':<{name_w}}  {'Rel Type':<{rel_w}}  {'Pri':<{pri_w}}  "
        f"{'Last Contact':<{last_w}}  {'Cadence':>{cad_w}}  {'Days Overdue':>{due_w}}"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)

    for c in candidates:
        pri      = "yes" if c["priority"] else ""
        last     = c["lastContactedAt"] or "(never)"
        cadence  = f"{c['effectiveCadence']}d"
        overdue  = "(never contacted)" if c["daysOverdue"] is None else str(c["daysOverdue"])

        print(
            f"{c['name']:<{name_w}}  {(c['relationshipType'] or ''):<{rel_w}}  "
            f"{pri:<{pri_w}}  {last:<{last_w}}  {cadence:>{cad_w}}  {overdue:>{due_w}}"
        )

    print()
    print(f"Total: {len(candidates)} candidates")


if __name__ == "__main__":
    main()
