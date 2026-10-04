# Daily Task Observer

A simple, clean website to manage your **daily tasks** and your **daily progress `.txt` files**, with a dashboard, history, calendar and statistics — everything stored locally in **SQLite**.

---

## Quick start (Windows / VS Code)

```powershell
# 1. Create and activate the virtual environment (first time only)
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies (first time only)
pip install -r requirements.txt

# 3. Start the backend
python Backend/app.py
```

Then open **http://127.0.0.1:5000** in your browser — the frontend is served automatically by the backend.

> The frontend also works on its own: open `frontend/index.html` directly (file://) or with VS Code Live Server. It calls the backend at `http://127.0.0.1:5000`; change `API_BASE` at the top of `frontend/script.js` if you run the backend on a different host/port.

---

## Project structure

```text
Daily Task Observer/
├── README.md
├── requirements.txt
├── .gitignore
├── Backend/
│   ├── app.py            # Flask REST API + static frontend server
│   ├── database.py       # SQLite setup, tables, safe connections
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── database/
│   └── progress.db       # created automatically
└── uploads/              # uploaded .txt progress files
```

---

## How it works

### SQLite database

- `database/progress.db` is **created automatically** on first start — the `database/` and `uploads/` folders are created too, you never create them by hand.
- Tables: `progress` (daily uploads) and `tasks` (daily tasks).
- All dashboard and statistics numbers are calculated from this database — nothing is hardcoded.

### Daily tasks

- On the **Dashboard**, add tasks for any date, tick the checkbox to mark them **Completed**, use **×** to delete.
- The dashboard shows today's completed / pending counts and the completion percentage.

### Uploading a daily progress file

1. Open **Upload Progress**.
2. Choose a `.txt` file, select the date, enter a title, optionally add comma-separated tags.
3. Click **Save Progress** — the file is stored in `uploads/`, its information in SQLite, and it instantly appears on the Dashboard, History, Calendar and Statistics pages.
- Invalid files (not `.txt`, empty, wrong encoding) are rejected with a clear message.

---

## API overview

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/dashboard` | Dashboard numbers, recent progress, today's tasks |
| GET | `/api/progress` | List entries (`search`, `tag`, `date`, `sort` params) |
| POST | `/api/progress` | Upload a `.txt` file (multipart: `file`, `date`, `title`, `tags`) |
| GET | `/api/progress/<id>` | Read one entry including its text |
| PUT | `/api/progress/<id>` | Edit entry (updates the DB **and** the `.txt` file) |
| DELETE | `/api/progress/<id>` | Delete entry (DB record + file in `uploads/`) |
| GET | `/api/progress/tags` | All existing tags |
| GET | `/api/tasks?date=YYYY-MM-DD` | Tasks for a date |
| POST | `/api/tasks` | Add a task |
| PUT | `/api/tasks/<id>` | Update title / mark pending or completed |
| DELETE | `/api/tasks/<id>` | Delete a task |
| GET | `/api/calendar` | Days with uploads and their counts |
| GET | `/api/statistics` | Current/longest streak, weekly/monthly, task statistics |

All errors come back as JSON, e.g. `{"error": "Title is required."}`.

---

## Troubleshooting

- **“Cannot reach the backend…”** → start `python Backend/app.py` first and check the URL/port in `API_BASE`.
- **Port 5000 already in use** → start the backend with `set PORT=5001 && python Backend/app.py` (Command Prompt) or `$env:PORT = "5001"; python Backend/app.py` (PowerShell), then update `API_BASE` in `frontend/script.js` to `http://127.0.0.1:5001`.
- **Missing packages** → re-run `pip install -r requirements.txt` inside the activated virtual environment.

---

# Daily Progress Tracker — Original Requirements

## Project Goal

Build a simple, clean, and functional website where I can upload, manage, view, edit, and track my daily progress `.txt` files.

The website must be easy to use and should focus on daily progress tracking without adding unnecessary features.

---

## Required Technology Stack

Use exactly this stack unless there is a strong technical reason otherwise:

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python
- **Database:** SQLite

Keep the frontend and backend separated.

---

## Project Structure

Create the project using this structure:

```text
daily-progress-tracker/
│
├── README.md
├── requirements.txt
├── .gitignore
│
├── Backend/
│   ├── app.py
│   ├── database.py
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── database/
│   └── progress.db
│
└── uploads/
    └── (uploaded .txt progress files)
```

If additional files are genuinely required, create them only when necessary and keep the project structure simple.

---

# Main Features

## 1. Dashboard

Create a dashboard that clearly displays:

- Total days tracked
- Current streak
- Total files
- Recent progress

The dashboard should be the main/home page of the website.

### Dashboard requirements

- Use clean cards/stat boxes for important numbers.
- Show recent progress entries.
- Keep the layout simple and readable.
- Dashboard data must come from the SQLite database.
- Do not use hardcoded statistics.

---

## 2. Upload Progress

Create an upload section where the user can add daily progress.

Required fields:

- `.txt` progress file
- Date
- Title
- Tags

Required actions:

- Select a `.txt` file
- Select the date
- Enter a title
- Add tags
- Save progress

### Upload rules

- Accept `.txt` files.
- Store uploaded files inside the `uploads/` folder.
- Store file information in SQLite.
- Do not store the entire website data only in JavaScript.
- Validate the uploaded file before saving it.
- Show a clear success or error message.

---

## 3. Progress History

Create a page/section showing all uploaded progress files.

It must provide:

- All uploaded files
- Sort by date
- Search progress
- Filter by tags

Each progress entry should show useful information such as:

- Date
- Title
- Tags
- File name
- Actions

The history should load its data from SQLite.

---

## 4. Progress Viewer

When the user opens a progress entry, allow them to:

- Read the uploaded `.txt` file
- Edit the progress
- Delete the progress

### Viewer requirements

The selected progress should open in a clean viewer.

The user must be able to edit the text and save the changes.

When deleting progress:

- Delete the database record.
- Delete the corresponding `.txt` file from the `uploads/` folder.
- Ask for confirmation before deletion.

---

## 5. Calendar

Create a calendar section.

The calendar must:

- Show days where progress has been uploaded.
- Clearly indicate dates containing progress.
- Allow the user to click a date.
- Show the progress associated with that date.

Calendar information must come from the database.

Do not create fake/static progress dates.

---

## 6. Statistics

Create a statistics section showing:

- Current streak
- Longest streak
- Weekly progress
- Monthly progress
- Total uploads

Statistics must be calculated from the actual stored progress data.

### Streak calculation

A streak means consecutive days on which progress was uploaded.

For example:

```text
Monday     ✓
Tuesday    ✓
Wednesday  ✓
Thursday   ✓
```

This represents a 4-day streak.

Do not count duplicate uploads on the same date as multiple streak days.

---

# Database

Use **SQLite**.

Create a database file:

```text
database/progress.db
```

Create a table for progress records.

A suitable structure is:

```text
progress
--------
id
date
title
tags
filename
created_at
updated_at
```

The database should store the information required to find and manage every uploaded progress file.

The actual `.txt` file should remain inside:

```text
uploads/
```

The database should store the filename/path needed to locate it.

---

# Backend

Use Python for the backend.

The backend should:

- Start the web server.
- Connect to SQLite.
- Create the database/table if it does not exist.
- Handle `.txt` uploads.
- Save progress metadata.
- Read progress files.
- Update progress files.
- Delete progress.
- Return dashboard statistics.
- Return history data.
- Provide calendar data.
- Provide statistics.

Create API endpoints where appropriate.

Example endpoint design:

```text
GET    /api/dashboard
GET    /api/progress
GET    /api/progress/<id>
POST   /api/progress
PUT    /api/progress/<id>
DELETE /api/progress/<id>
GET    /api/calendar
GET    /api/statistics
```

The exact implementation can be changed if needed, but all required functionality must be available.

---

# Frontend

Use:

- HTML
- CSS
- JavaScript

Do not use React, Angular, Vue, or another frontend framework unless specifically requested later.

The JavaScript frontend should communicate with the Python backend using API requests.

Example:

```javascript
fetch('/api/progress')
```

Do not hardcode database information into the frontend.

---

# UI Requirements

The website should have a clean and simple dashboard-style design.

Main navigation should provide access to:

```text
Dashboard
Upload Progress
Progress History
Calendar
Statistics
```

The UI should be:

- Simple
- Clean
- Responsive
- Easy to understand
- Suitable for a student/personal productivity website

Use cards, tables/lists, buttons, forms, and clear spacing.

Avoid unnecessary animations and unnecessary UI elements.

---

# Error Handling

Handle common errors properly.

Examples:

- Invalid file type
- Missing title
- Missing date
- Empty progress file
- File not found
- Database error
- Invalid progress ID
- Failed upload
- Failed update
- Failed deletion

Show a simple understandable error message to the user.

Do not show raw Python errors to the user.

---

# Security and Validation

At minimum:

- Only allow `.txt` uploads.
- Validate filenames.
- Do not allow uploaded filenames to escape the `uploads/` directory.
- Validate IDs received from the frontend.
- Validate required form fields.
- Prevent accidental deletion with confirmation.

---

# Important Development Rules

## 1. Make the website functional

Do not create only a visual mockup.

Every important button must perform its actual function.

For example:

```text
Upload → saves file + database record
Edit → updates file + database
Delete → deletes file + database record
Search → searches actual records
Calendar → displays actual dates
Statistics → calculates actual statistics
```

## 2. Use real database data

Do not use placeholder statistics such as:

```text
Total Days: 25
Current Streak: 7
Total Files: 40
```

unless those numbers actually come from the database.

## 3. Keep code simple

Write beginner-friendly code.

Avoid unnecessary architecture and unnecessary dependencies.

## 4. Preserve existing work

If modifying an existing project:

- Do not delete working functionality.
- Do not rewrite unrelated files unnecessarily.
- Modify only what is required.
- Keep the existing project structure unless there is a real reason to change it.

## 5. Test every feature

Before considering the project complete, test:

- Upload
- View
- Edit
- Delete
- Search
- Sort
- Tag filtering
- Calendar
- Dashboard statistics
- Weekly statistics
- Monthly statistics
- Current streak
- Longest streak

---

# Requirements File

Keep dependencies minimal.

The Python dependencies should contain only the packages actually required by the backend.

For example, if Flask is used:

```text
Flask
```

Do not install unnecessary packages.

---

# Expected User Flow

The normal user flow should be:

```text
Open Website
      ↓
Dashboard
      ↓
Upload Progress
      ↓
Select .txt file
      ↓
Select Date
      ↓
Enter Title
      ↓
Add Tags
      ↓
Save
      ↓
Database + uploads folder updated
      ↓
Dashboard updated
      ↓
Progress appears in History
      ↓
Progress appears on Calendar
      ↓
Statistics updated
```

---

# Final Completion Checklist

Before finishing the website, verify that all of these work:

### Dashboard
- [ ] Total days tracked
- [ ] Current streak
- [ ] Total files
- [ ] Recent progress

### Upload
- [ ] Upload `.txt`
- [ ] Select date
- [ ] Add title
- [ ] Add tags
- [ ] Save progress

### History
- [ ] Show all files
- [ ] Sort by date
- [ ] Search
- [ ] Filter by tags

### Viewer
- [ ] Read progress
- [ ] Edit progress
- [ ] Delete progress

### Calendar
- [ ] Show uploaded days
- [ ] Click date
- [ ] View date's progress

### Statistics
- [ ] Current streak
- [ ] Longest streak
- [ ] Weekly progress
- [ ] Monthly progress
- [ ] Total uploads

### Backend
- [ ] Python server works
- [ ] API works
- [ ] SQLite works
- [ ] File storage works

### Final testing
- [ ] No broken buttons
- [ ] No fake data
- [ ] No console errors
- [ ] No unnecessary dependencies
- [ ] Website works from a fresh start
