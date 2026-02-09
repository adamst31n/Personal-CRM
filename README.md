# Personal Relationship CRM

I built this because I kept losing touch with people I cared about. The problem wasn't that I didn't want to stay connected — it was that I had no system. This is a web app that helps you track your relationships and reminds you when it's been too long since you last reached out to someone.

The whole thing is a single HTML file using Firebase for the backend. No framework, no build process, just vanilla JavaScript.

> **[Try the live demo →](https://adamst31n.github.io/Personal-CRM/demo.html)** — preloaded with sample data, no setup required

![Dashboard view](Screenshots/dashboard.png)

## Features

You add contacts (friends, family, colleagues) and log interactions whenever you talk to them. Each contact has a "cadence goal" — how often you want to stay in touch. The app shows you who you're overdue to contact and keeps a history of all your interactions.

**Core functionality:**
- Contact management with notes, birthdays, and custom cadence goals
- Interaction logging (calls, texts, emails, meetings, meals, video calls, activities)
- Dashboard that surfaces who needs your attention using a color-coded priority system
- Search and filtering across all contacts
- LinkedIn CSV import for bulk onboarding
- Dark mode
- Mobile-responsive design
- Real-time sync across devices via Firebase

**Status system:**
- 🟢 Green — contacted recently
- 🟡 Yellow — getting close to being overdue
- 🟠 Orange — overdue
- 🔴 Red — very overdue
- ⚪ Gray — not yet contacted

## Quick Start

There are two ways to try this:

### Option 1: Live demo (no setup)

**[Open the demo →](https://adamst31n.github.io/Personal-CRM/demo.html)** — runs entirely in your browser using localStorage. Comes preloaded with sample contacts so you can explore the full interface without creating an account.

### Option 2: Full version with Firebase (for actual use)

The full version syncs across devices and persists your data in the cloud. You'll need a free Firebase account.

<details>
<summary><strong>Firebase setup instructions</strong></summary>

1. Go to the [Firebase Console](https://console.firebase.google.com/) and create a new project
2. Turn on Authentication with Google as the sign-in provider
3. Create a Firestore database (start in production mode, pick a region near you)
4. Set up security rules so users can only access their own data:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId}/contacts/{contactId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    match /users/{userId}/interactions/{interactionId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

5. Register a web app in your project settings and copy the config object
6. Download `relationship-crm.html`
7. Open it in a text editor and find the Firebase config section (around line 5500)
8. Replace the placeholder values with your actual Firebase config
9. Open in a browser, or run a local server:

```bash
python3 -m http.server 8000
# then visit http://localhost:8000/relationship-crm.html
```

Sign in with Google and you're ready to go.

</details>

## How to Use It

After signing in, you'll see an empty dashboard. Start by adding some contacts.

**Adding contacts:**
Click the + button, fill in their info (only name is required), choose a category (work/friends/family), and set how often you want to stay in touch. The cadence options are daily, weekly, monthly, quarterly, or annually.

**Logging interactions:**
Every time you talk to someone, log it. Click "Log Interaction" from the dashboard or from a contact's page. Pick the type (call, text, email, meeting, meal, video call, activity), add the date, and write a quick note about what you talked about. You can also tag other people who were there.

**The dashboard:**
Shows you who you need to reach out to. Priority contacts (red) are people you're very overdue to contact. "Needs Attention" (orange/yellow) are people getting close. You also see recent activity and upcoming birthdays.

**Keyboard shortcuts:**
| Shortcut | Action |
|----------|--------|
| `Esc` | Close modals |
| `⌘/Ctrl + K` | Search |
| `⌘/Ctrl + N` | New contact |
| `⌘/Ctrl + H` | Dashboard |

**LinkedIn import:**
You can import contacts from LinkedIn. Export your connections as a CSV from LinkedIn, then go to Settings and use the LinkedIn import tool. The app will show you any conflicts with existing contacts and let you decide how to handle them.

## Technical Details

This is a single-page app written in vanilla JavaScript. No React, no Vue, no build tools. Just one HTML file with embedded CSS and JavaScript — about 5,850 lines.

**Stack:**
- Vanilla JavaScript (ES6+)
- Firebase Firestore for the database
- Firebase Authentication (Google sign-in)
- All custom CSS, no frameworks

**Architecture decisions:**
- **Single-file design** — Extremely portable. Deploy anywhere that serves static files.
- **Map-based state** — Uses JavaScript Maps instead of arrays for O(1) contact lookups.
- **Real-time sync** — Firestore `onSnapshot` listeners keep data in sync across devices within milliseconds.
- **Debounced search** — 300ms debounce to avoid excessive re-renders.
- **CSS containment** — Isolates layout calculations for better rendering performance.

**Data model:**
```
users/{userId}/
  contacts/{contactId}
  interactions/{interactionId}
```

Each interaction references a `contactId`. Logging an interaction updates the contact's `lastContactedAt` timestamp, which drives the status colors and sorting.

**Security:**
Firestore rules enforce that users can only read/write their own data by checking `request.auth.uid` against the document path.

## Roadmap

Some features I've thought about but haven't built yet:
- Contact photos
- Push notifications (currently you only see reminders when you open the app)
- Google Calendar integration
- Relationship network visualization
- AI-powered outreach suggestions
- Gmail integration
- Custom tags beyond work/friends/family
- Bulk actions

## Known Issues

- Phone number formatting only works for US numbers
- Birthday reminders require you to open the app
- LinkedIn CSV format varies by region, so import might not work perfectly for everyone
- Performance may slow down with 1000+ contacts

## How This Was Built

I started this project to learn full-stack development. It began as a simple localStorage app in January 2026 and evolved into a Firebase-backed application when I needed multi-device sync. I used [Claude](https://claude.ai) as a development partner throughout the process — for debugging, architecture decisions, and learning JavaScript patterns. The project has been my daily driver for tracking relationships ever since.

## License

MIT License — use it however you want. See the [LICENSE](LICENSE) file for details.
