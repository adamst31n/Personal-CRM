# Personal CRM Agent — MCP Server Brief (v1.4)

*Architect-level spec. Hand to Claude Code when building. Concept-level, but now annotated with what's actually been built and verified.*
*v1.4: log_interaction (first write tool) fully specified — confirmation beat, batched whole-document write, lastContactedAt refresh. Build-state and hard-won lessons from sessions 1–2 folded in.*

## Build status (as of v1.4)

- **Scaffolding: DONE and verified.** Standalone Python MCP server, Firebase service-account auth, the Claude Agent SDK harness (`crm_agent.py`), env/PATH wiring, and tool restriction all work end to end.
- **Tool 1 `find_contact`: DONE**, verified against live data (3 real Aarons, correct dates).
- **Tool 2 `get_contact`: DONE**, verified (Aaron Farkas: 12-field profile + 19 interactions = 16 primary + 3 tagged, correct ISO date).
- **Tool 3 `log_interaction`: NEXT — this update.** First write tool.
- **Tools 4–5 (`list_outreach_candidates`, `get_interaction_history`): not started.**

## Hard-won lessons (apply to every tool from here)

1. **Epoch ms → ISO date conversion belongs in the TOOL, never the agent.** `lastContactedAt` and interaction dates are epoch milliseconds. The tool must convert to ISO (`YYYY-MM-DD`) before returning, using the shared `_ms_to_iso_date` helper. Handing the agent a raw 13-digit number makes it do epoch arithmetic, which it gets wrong (produced dates ~2 years off). Deterministic work in the tool; judgment in the agent.
2. **One shared document-read path.** `_read_user_doc()` / `get_user_data()` reads the single `users/{uid}` doc once and returns contacts + interactions together. Reuse it — do not duplicate the read.
3. **Agent SDK harness specifics:** MCP server launched via the **absolute** interpreter path (`/opt/homebrew/bin/python3.11`), because the explicit env dict passed to the subprocess has no PATH. Built-ins are removed via **`disallowed_tools`** (not `tools=[]`, which nukes MCP tools too; not `allowed_tools`, which only skips permission prompts). The init message may show the MCP server as `"pending"` — that's a startup snapshot; real connection is proven by the tool returning data.

## Storage model (the governing constraint)

All data in **one** Firestore document at `users/{uid}`. `contacts` and `interactions` are **arrays inside it**. The contact UUID (`contact.id`) is the logical key, not a doc ID. Every write is a **read-modify-write on the whole document**.

## The menu (tools)

### 1. `find_contact` — DONE
Case-insensitive substring match across `firstName`, `lastName`, legacy `name`. Returns candidates (`id`, name, `relationshipType`, ISO `lastContactedAt`). Zero matches = valid ("new person"). Read-only.

### 2. `get_contact` — DONE
Takes contact ID. Returns profile (`firstName`, `lastName`, `name`, `relationshipType`, `contactFrequency`, `company`, `position`, `industry`, `howWeMet`, `priority`, `muted`, `lastContactedAt`) + interaction history (primary where `contactId` matches AND tagged where ID is in `taggedContacts`), ISO dates, most-recent first. Read-only.

### 3. `log_interaction` — NEXT (first write tool)

**For:** Recording interactions, including several parsed from one free-form dump.

**Takes in (per entry):** contactId (UUID), date (`YYYY-MM-DD`), type (one of: Call, Text, In Person, Video, Email, LinkedIn), notes (freeform). Optional: taggedContacts (array of UUIDs). The tool accepts a **list** of entries so a multi-person dump is one call.

**Hands back:** confirmation echoing each written entry (with the ISO date and resolved contact name).

**Build notes — the write-safety design (this is the new, important part):**

- **Confirmation beat (agent-layer, not tool-layer).** The tool itself does the write when called — but the *agent* must first show the user the parsed entries and get an explicit "yes" before calling it. This is enforced by **turning `bypassPermissions` OFF for this tool**: `log_interaction` must require a permission prompt, while the read tools may stay auto-approved. Net: the agent proposes → user confirms → tool writes. Never write on the first turn.
- **Batched whole-document write.** Read the single doc once (`_read_user_doc`), append ALL parsed entries to the `interactions` array in memory, write the whole document back **once**. Never one write per entry — that widens the race window and hammers the doc.
- **`lastContactedAt` refresh in the same write.** For every affected contact (primary contactId AND anyone in taggedContacts), recompute `lastContactedAt` after appending — reuse the app's logic: most-recent non-future interaction date, counting tagged appearances, stored as epoch ms. Refresh it in the SAME document write as the interaction append, so it never goes stale.
- **Reuse `addInteraction()` shape:** entry fields are `id` (server-generated UUID), `contactId`, `taggedContacts[]`, `date` (`YYYY-MM-DD` string), `type`, `notes`, `createdAt` (epoch ms, server-generated). No migration.
- **Concurrency:** read immediately before writing. This is the race condition already fixed once in the browser app; the server is a second writer, so background/scheduled writes are the high-risk path. (v1 intake is paste-into-chat, lowest risk — see Intake.)
- **Validation before write:** reject unknown contactIds, invalid `type` values, and malformed dates rather than writing bad data. A dump entry that can't be resolved should surface to the user, not get silently dropped or guessed.

**Test plan (mirror the read tools — validate before any real write):**
- First a **dry-run mode**: parse + resolve + show exactly what *would* be written, with no Firestore write, against a real multi-entry example. Confirm the batched structure and the `lastContactedAt` recompute look right.
- Only then enable the real write, tested on a **single throwaway entry** that's easy to verify and delete, before trusting it with a real dump.

### 4. `list_outreach_candidates` — not started
Signal-gatherer, not a ranker. Returns candidates with deterministic signals (effective cadence via `getContactFrequency`, `lastContactedAt`, days overdue, `priority`); excludes `muted`. Reuses `get_user_data()` (needs contacts + interactions). Agent does the fuzzy weighing (interaction quality, follow-ups, relationship value via `company`/`position`/`industry`/`howWeMet`/`notes` + user's career context in agent instructions).

### 5. `get_interaction_history` — not started
Aggregate cadence analysis across many contacts. Reuses `get_user_data()`. Shaped for trend-spotting.

## Cross-server dependency
Outreach drafting is the agent's job; delivery (if wanted) calls `create_draft` on the existing **Gmail** MCP server. Not in this server.

## Permission posture (evolves with writes)
- Read tools (`find_contact`, `get_contact`, `list_outreach_candidates`, `get_interaction_history`): may stay auto-approved.
- Write tools (`log_interaction`): **must** prompt for confirmation — `bypassPermissions` off. This is the mechanism behind the confirmation beat.

## Intake (how updates reach the agent)
- **v1: paste-into-chat.** Zero plumbing, lowest concurrency risk (user present, not editing UI simultaneously).
- **Later: email** via Gmail MCP (background write path — concurrency rule matters most).
- **Deferred: SMS** (needs Twilio).

## Out of scope for v1
Auto-send. SMS intake. Editing/deleting past interactions (append-only). `linkedinData` join (v2).

## Confirmed schema reference
- Identity: `contact.id` (UUID v4), array element in single `users/{uid}` doc.
- Cadence defaults: Close Friend / Friend / Family = 30; Professional / Acquaintance / fallback = 60. Effective via `getContactFrequency(contact)` → `contactFrequency` (int days, null = default) else default.
- Names: `firstName`, `lastName`, legacy `name` all populated.
- Interaction shape: id, contactId, taggedContacts[], date, type, notes, createdAt (epoch ms). Reuse `addInteraction()`.
- Last-contacted: precomputed `contact.lastContactedAt` (epoch ms); counts tagged appearances, excludes future dates.
- Flags: `priority` (bool, default false), `muted` (bool).
- LinkedIn: enrichment writes `company`/`position` (if empty; conflicts flagged) + `connectedOn` into notes; fuller data in separate `linkedinData` array, not joined.

*Governing risks for log_interaction: (1) whole-document read-modify-write — batch all entries, refresh lastContactedAt in the same write, read immediately before writing; (2) the confirmation beat is enforced by permissions, not politeness — bypassPermissions OFF for writes; (3) dry-run and verify before trusting a real dump.*
