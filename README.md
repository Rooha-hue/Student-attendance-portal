# Student-attendance-portal
# 🎓 Student Attendance Portal

A simple, clean attendance system built with **Streamlit** and **SQLite**.

## Features

- **Teacher login** (username + password, stored as a salted PBKDF2 hash)
- **Student login** (Student ID + full name)
- **Only teachers can mark** students Present or Absent (editable per date)
- **Students can only view** their own records, total classes and attendance percentage
- Teacher summary table with attendance % for every student
- Add / remove students from the dashboard
- Logout button in the sidebar
- All data stored in a local SQLite file (`attendance.db`, created automatically)

## Project structure

```
attendance-portal/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
└── .streamlit/
    └── config.toml
```

## Run locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Default login (first run only)

| Role    | Credentials                                  |
|---------|----------------------------------------------|
| Teacher | username `teacher` / password `teacher123`   |
| Student | `S001` / `Ayesha Khan` (demo student)        |

Demo students (S001-S003) are added on first run so you can try the app. Delete them from the **Students** tab.

**Change the teacher password before real use.** Delete `attendance.db` and set these environment variables before the first launch:

```bash
export TEACHER_USERNAME="your_username"
export TEACHER_PASSWORD="a-strong-password"
```

On Streamlit Community Cloud, set the same values under **App settings → Secrets / Environment variables**.

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app from the repo.
3. Set the main file to `app.py`.

> **Note:** Streamlit Cloud's file system is not permanent, so `attendance.db` can reset when the app restarts. For real, long-term use, host on a server or VPS with persistent storage (set `ATTENDANCE_DB` to a path on that disk).

## How attendance % is calculated

`Attendance % = Present days ÷ Total recorded days × 100`
