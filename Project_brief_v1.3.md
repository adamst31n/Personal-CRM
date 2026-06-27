# Personal CRM Agent — MCP Server Brief (v1.3)

*Architect-level spec. Concept only — no code. Hand to Claude Code when ready to build.*
*v1.3: priority + muted confirmed; LinkedIn enrichment scope (and its limits) folded into the relationship-judgment design.*

## Purpose

Expose the Personal CRM's Firebase/Firestore data through a small MCP server so an agent — and, for free, Claude desktop and Claude Code — can read contact history, log interactions, and reason about who to reach out to, through one standard interface.

The agent loop (judging relationship value, prioritizing outreach, drafting) lives **outside** this server. The server exposes data + writes and supplies structured signals. Judgment is the agent's job.

## Storage model (the governing constraint — read first)

All data for a user lives in **one** Firestore document at `users/{uid}`. `contacts` and `interactions` are **arrays inside that single document**. The contact UUID (`contact.id`, v4) is the logical key, not a Firestore doc ID.

Every write is a **read-modify-write on the whole document**. Hard rules:
1. **Batch all writes.** A multi-person dump = one read-modify-write.
2. **Concurrency is real.** Last-write-wins clobbering is the race already fixed in this app once. Read immediately before writing; scheduled/background writes are the high-risk path.
3. **Keep derived fields consistent.** A write adding an interaction must also refresh affected contacts' `lastContactedAt` in the same write (tool #4).

## Where prioritization intelligence lives (the core design decision)

"Who should I reach out to" is NOT "who is most overdue." Factors split cleanly:

**Deterministic — surfaced by the tool:**
- Effective cadence + days overdue (via `getContactFrequency()`)
- `priority` (boolean) — already powers the app's "Contact ASAP" view
- `lastContactedAt`
- `muted` (boolean) — **exclusion** signal: muted contacts are not outreach candidates *(confirm semantics)*

**Fuzzy — judged by the agent:**
- Quality of recent interactions + follow-ups promised in `notes` (agent reads notes)
- Strategic value of the relationship — reasoned over the contact's `company`, `position`, `industry`, `howWeMet`, and `notes`, **plus the user's own career/employment history supplied in the agent's instructions** (not a tool)

The tool returns signals; the agent reads notes + relationship context and decides. The prioritization tool is a **signal-gatherer, not a ranker** — no scoring formula baked in.

### Known limitation (v1)
LinkedIn enrichment writes only `company` + `position` to the contact (when empty; conflicts flagged for manual resolution) and appends `connectedOn` into `notes` as a string. The fuller CSV data (email, location, etc.) lives in a separate `linkedinData` reference array **not cleanly joined to contacts**. So the agent's relationship-value judgment uses what persists on the contact, not a full LinkedIn profile. A `get_linkedin_data` join tool is a **v2** option if richer context is wanted.

## The menu (tools)

### 1. `find_contact`
- **For:** Resolving a messy name to a contact before any write. The dedup guard.
- **Takes in:** a name or fragment.
- **Hands back:** zero or more candidates (ID, full name, relationship type / last-touch). Zero = "new person."
- **Build note:** No existing name lookup; app matches only on UUID. Every contact carries `firstName`, `lastName`, **and** legacy `name` (all populated). Match case-insensitive substring across all three. Custom work. Call before `log_interaction` on free-form input.
- **Build this first** — riskiest tool, no existing code, everything else depends on name→ID resolution. Depends only on confirmed fields.

### 2. `get_contact`
- **For:** Full record + history before drafting or judging.
- **Takes in:** a contact ID.
- **Hands back:** profile (`firstName`/`lastName`/`name`, `relationshipType`, `contactFrequency`, `company`, `position`, `industry`, `howWeMet`, `priority`, `muted`) and interaction history (dated entries with type + **notes**).

### 3. `list_outreach_candidates`
- **For:** First pass of "who should I reach out to." Returns a candidate set **with signals attached**, not a ranking.
- **Takes in:** optional filters (relationship type, only-overdue, only-priority).
- **Hands back:** per contact: name, `relationshipType`, effective cadence, `lastContactedAt`, days overdue, `priority`. **Excludes `muted` contacts by default.**
- **Build note:** read `lastContactedAt` directly; route cadence through `getContactFrequency()`.

### 4. `log_interaction`
- **For:** Recording interactions, including entries parsed from a free-form dump.
- **Takes in:** contactId, date (YYYY-MM-DD), type (Call, Text, In Person, Video, Email, Social), notes; optional taggedContacts[].
- **Hands back:** confirmation echoing the written entry/entries.
- **Build note:** Reuse `addInteraction()` shape (`id` + `createdAt` server-generated). **Whole-document write** — batch a dump into one write. **Must refresh `lastContactedAt`** for every affected contact (primary + tagged) via the app's `updateContactLastInteraction` logic (counts tagged appearances, excludes future dates). Runs only after the confirmation beat.

### 5. `get_interaction_history`
- **For:** Aggregate cadence analysis across many contacts.
- **Takes in:** optional filters (date range, relationship type).
- **Hands back:** records shaped for trend-spotting (grouped by relationship type with intervals).
- **Note:** Quality depends on logging discipline — tool #4 feeds this one.

## Cross-server dependency
Sending outreach is not in this server. To place a draft, the agent orders `create_draft` from your existing **Gmail** MCP server.

## Write-safety pattern
Any write shows structured entries first and waits for confirm. A dump = one batch shown, then one read-modify-write (interactions appended + `lastContactedAt` refreshed together).

## Intake
- **v1: paste-into-chat.** Zero plumbing; lowest concurrency risk.
- **Later: email.** Scheduled inbox read via Gmail — the background write path; concurrency rule matters most here.
- **Deferred: SMS.** Needs Twilio. Not v1.

## Out of scope for v1
- Auto-send (draft only). SMS intake. Editing/deleting past interactions. `linkedinData` join (v2).

## Acceptance criteria
- The agent answers "who should I reach out to" by combining tool signals (overdue, priority, cadence; muted excluded) with its own reading of notes + relationship/career context — demonstrably more than a raw overdue sort.
- A multi-person dump: each name resolved via `find_contact`, entries confirmed, written in one batched write with `lastContactedAt` refreshed; no duplicates, no clobbered data.
- Cadence routes through `getContactFrequency()` (custom override respected).
- Claude desktop / Claude Code can call the tools with no extra setup.

## To verify (from the garbled investigation report)
- `muted` semantics — confirm it means "suppress from outreach."
- `howWeMet` and `industry` field names exist as written.
- (Affects tool #2/#3 payloads only — does **not** block building `find_contact`.)

## Resolved (confirmed against relationship-crm.html)
- Identity: `contact.id` (UUID v4), array element in single `users/{uid}` doc.
- Cadence defaults: Close Friend / Friend / Family = 30; Professional / Acquaintance / fallback = 60.
- Effective cadence: `getContactFrequency(contact)` → `contactFrequency` (int days, null = default) else default. Authoritative.
- Names: `firstName`, `lastName`, legacy `name` all populated.
- Interaction shape: id, contactId, taggedContacts[], date, type, notes, createdAt — reuse `addInteraction()`.
- Last-contacted: precomputed `contact.lastContactedAt` (epoch ms); counts tagged, excludes future dates.
- Priority: `priority` boolean, default false; drives "Contact ASAP" view.
- LinkedIn: enrichment writes `company`/`position` (if empty; conflicts flagged) + `connectedOn` into notes; fuller data in separate `linkedinData` array, not joined.

*Governing risks: (1) single-document array store → batched, consistent whole-document writes; (2) prioritization is agent judgment over tool-supplied signals — don't hardcode a score; (3) on-contact LinkedIn context is thin — set the agent's expectations accordingly.*
