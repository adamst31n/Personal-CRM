# Personal Relationship CRM

I built this because I kept losing touch with people I cared about. The problem wasn't that I didn't want to stay connected, it was that I had no system. This is a web app that helps you track your relationships and reminds you when it's been too long since you last reached out to someone.

The whole webpage is a single HTML file using Firebase for the backend. No framework, no build process, just vanilla JavaScript.

![Dashboard view](Screenshots/dashboard.png)

## What it does

You add contacts (friends, family, colleagues) and log interactions whenever you talk to them. Each contact has a "cadence goal" that specifies how often you want to stay in touch. The app shows you who you're overdue to contact and keeps a history of all your interactions.

**Main features:**
- Contact management with notes, birthdays, and custom cadence goals
- Interaction logging (calls, texts, emails, meetings, meals, video calls, activities)
- Dashboard that shows who needs your attention
- Search and filtering
- LinkedIn CSV import
- Dark mode
- Works on your phone
- Syncs across devices via Firebase

**Status system:**
- Green: contacted recently
- Yellow: getting close to being overdue
- Orange: overdue
- Red: very overdue
- Gray: not yet contacted

## Setup

You need a Firebase account to run this. The free tier is all that's required.

### Firebase setup

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

### Getting it running

1. Download `relationship-crm.html`
2. Open it in a text editor
3. Find the Firebase config section (around line 5500) and replace the placeholder values with your actual Firebase config
4. Save the file
5. Open it in a browser, or run a local server:
   ```bash
   python3 -m http.server 8000
   # then visit http://localhost:8000/relationship-crm.html
   ```

That's it. Sign in with Google and you're ready to add contacts.

## How to use it

After signing in, you'll see an empty dashboard. Start by adding some contacts.

**Adding contacts:**
Click the + button, fill in their info (only name is required), choose a category (work/friends/family), and set how often you want to stay in touch. The cadence options are daily, weekly, monthly, quarterly, or annually.

**Logging interactions:**
Every time you talk to someone, log it. Click "Log Interaction" from the dashboard or from a contact's page. Pick the type (call, text, email, meeting, meal, video call, activity), add the date, and write a quick note about what you talked about. You can also tag other people who were there.

**The dashboard:**
Shows you who you need to reach out to. Priority contacts (red) are people you're very overdue to contact. "Needs Attention" (orange/yellow) are people getting close. You also see recent activity and upcoming birthdays.

**Keyboard shortcuts:**
- `Esc` closes modals
- `⌘/Ctrl + K` jumps to search
- `⌘/Ctrl + N` adds a new contact
- `⌘/Ctrl + H` goes back to dashboard

**LinkedIn import:**
You can import contacts from LinkedIn. Export your connections as a CSV from LinkedIn, then go to Settings and use the LinkedIn import tool. The app will show you any conflicts with existing contacts and let you decide how to handle them.

## Technical details

This is a single-page app written in vanilla JavaScript. No React, no Vue, no build tools. Just one HTML file with embedded CSS and JavaScript.

**Why I built it this way:**
I wanted to prove I could build something semi-complex without leaning on frameworks. The whole app is about 5,850 lines of code in one file. It's also extremely portable - you can deploy it anywhere that serves static files.

**Stack:**
- Vanilla JavaScript (ES6+)
- Firebase Firestore for the database
- Firebase Authentication (Google sign-in only)
- No CSS frameworks, all custom styles

**How Firebase sync works:**
The app uses Firestore's `onSnapshot` listeners to keep data in sync across devices. When you make a change on one device, it shows up on your other devices within a few hundred milliseconds. The data structure uses subcollections under each user's ID, so your contacts and interactions are completely isolated from other users.

Data structure:
```
users/{userId}/
  contacts/{contactId}
  interactions/{interactionId}
```

Each interaction references a contactId. When you log an interaction, the app updates that contact's `lastContactedAt` timestamp, which is what drives the status colors and sorting.

**State management:**
I use JavaScript Maps instead of arrays for contacts and interactions. This gives O(1) lookup time instead of O(n), which matters when you have a lot of contacts. The whole app state lives in one object:

```javascript
const AppState = {
  contacts: new Map(),
  interactions: new Map(),
  currentView: 'dashboard',
  searchTerm: '',
  activeFilters: new Set(['all'])
};
```

**Security:**
Firestore security rules enforce that users can only read/write their own data. The rules check that `request.auth.uid` matches the `userId` in the document path. Everything is server-side validated by Firebase.

**Performance notes:**
- Search is debounced to 300ms to avoid excessive re-renders
- Contact list only renders visible items
- Uses CSS containment to isolate layout calculations
- Map-based data structures for fast lookups

The app is about 210KB unminified. It loads Firebase SDK from CDN, which adds another ~100KB on first load (but caches after that).

## What I might add later

Some features I've thought about but haven't built yet:

- Contact photos
- Push notifications (currently you only see reminders when you open the app)
- Google Calendar integration
- A visual map of how contacts connect to each other
- AI suggestions for when to reach out
- Email integration with Gmail
- Custom tags beyond the work/friends/family categories
- Better filtering and search options
- Bulk actions (edit or delete multiple contacts at once)

I also want to add proper tests. Right now everything is manual testing.

## Known issues

A few things that could be better:

- Phone number formatting only works for US numbers
- Birthday reminders require you to actually open the app
- LinkedIn CSV format varies by region, so import might not work perfectly for everyone
- With 1000+ contacts, the UI gets a bit slow (though most people won't hit this)

If you find bugs, open an issue.

## Contributing

This is a personal project, but if you want to use it or modify it, go ahead. The code is all in one file, so it's easy to fork and customize.

If you find issues or have suggestions, feel free to open an issue on GitHub.

## License

MIT License - use it however you want. See the LICENSE file for details.

## Why I built this

I'm learning to code and wanted to build something useful. I also wanted to get better at Firebase and prove to myself that I could build a real app without relying on frameworks.

This started as a simple localStorage-based app in January 2026. I migrated it to Firebase later that month when I wanted multi-device sync. It's been my daily driver for tracking relationships ever since.

If you have questions, you can reach me at adamstein14@gmail.com.
