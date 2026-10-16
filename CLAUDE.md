# Personal CRM

## File map
- relationship-crm.html: production app (vanilla JS module, Firebase Auth + Firestore). No build step.
- demo.html: hand-maintained localStorage copy for the portfolio. NOT generated from production; it lags behind.
- crm_agent.py, mcp_server/, scripts/: parked Python agent harness (Claude Agent SDK + MCP). Uses a service account.
- firestore.rules: reference copy of the live rules (edited in the Firebase console, not deployed from here).
- deploy.sh: the ONLY way to deploy Firebase Hosting. Publishes just relationship-crm.html (+ index.html) from dist/.
- agent-context.md, .env, data/: personal, git-ignored. Never commit, never deploy.

## Run locally
- `python3 -m http.server 8000`, open http://localhost:8000/relationship-crm.html, sign in with Google.

## Deploy
- GitHub Pages: push to main.
- Firebase Hosting: `./deploy.sh` only. Never run `firebase deploy` directly from this folder (a Jun 2026 deploy published .env and private files).

## Firestore schema (one document: users/{uid})
- contacts[]: id, firstName, lastName, name (legacy), relationshipType, howWeMet, phone, email, linkedin, company, position, industry, notes, birthdayMonth, birthdayDay, birthday (legacy), priority, muted, contactFrequency (null = default), createdAt, updatedAt, lastContactedAt (epoch ms), connectedOn
- interactions[]: id, contactId, taggedContacts[], date (YYYY-MM-DD), type, notes, createdAt
- linkedinData[], enrichmentConflicts[], version, lastUpdated
- The Python harness reads and writes this exact shape. Do not rename, remove, or re-nest fields without flagging the harness impact.

## Data-safety guards (do not weaken)
- saveState blocks writes until the first load succeeds, and refuses to save empty data if data existed on load.
- onSnapshot ignores an empty first snapshot while local data exists.
- Import/restore abort if the initial load failed.
- localStorage "crm-last-known-good" is the local restore point.
These exist because empty overwrites have happened before.

## Rendering rules
- Every data value rendered via innerHTML goes through escapeHtml (it escapes quotes, so it's safe in attributes).
- Every href built from data goes through safeUrl.
- Every id interpolated into an inline onclick goes through safeId.
- Status thresholds and colors: use constants, not new literals.

## Verify a change
- Load locally, sign in, open Dashboard, Contacts, one contact, Activity, Settings. Console must be error-free.
- Test with a throwaway contact (e.g. "ZZ Test") and delete it after. Never test destructive actions on real data.
- Import (JSON Merge/Replace) is not yet browser-tested: do not import into the real account.

## demo.html
- Change relationship-crm.html first. Note in your summary which fixes demo.html also needs; don't edit it unless asked.
