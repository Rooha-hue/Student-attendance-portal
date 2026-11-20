"""Student Attendance Portal - Streamlit + SQLite.

Teachers log in to mark students present/absent and manage the student list.
Students log in to view only their own attendance and percentage.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import date

import pandas as pd
import streamlit as st

DB_PATH = os.environ.get("ATTENDANCE_DB", "attendance.db")
DEFAULT_TEACHER_USER = os.environ.get("TEACHER_USERNAME", "teacher")
DEFAULT_TEACHER_PASS = os.environ.get("TEACHER_PASSWORD", "teacher123")
MIN_PERCENT = 75  # shows a warning to students below this value

st.set_page_config(page_title="Attendance Portal", page_icon="🎓", layout="centered")

# ---------------------------------------------------------------- styling
st.markdown(
    """
    <style>
    #MainMenu, footer {visibility: hidden;}
    .block-container {padding-top: 2rem; max-width: 820px;}
    h1, h2, h3 {color: #1f3a5f;}
    div[data-testid="stMetric"] {
        background: #f5f8fc; border: 1px solid #dbe4f0;
        border-radius: 10px; padding: 14px 16px;
    }
    .stButton > button, .stFormSubmitButton > button {
        border-radius: 8px; font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------- database
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run(sql, params=()):
    """Execute a write statement."""
    with closing(get_conn()) as conn, conn:
        conn.execute(sql, params)


def fetch(sql, params=()):
    """Run a read query and return a list of rows."""
    with closing(get_conn()) as conn:
        return conn.execute(sql, params).fetchall()


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return digest.hex(), salt


def init_db():
    with closing(get_conn()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS teachers (
                username      TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                salt          TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name       TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL
                           REFERENCES students(student_id) ON DELETE CASCADE,
                date       TEXT NOT NULL,
                status     TEXT NOT NULL CHECK (status IN ('Present', 'Absent')),
                UNIQUE (student_id, date)
            );
            """
        )
        if not conn.execute("SELECT 1 FROM teachers LIMIT 1").fetchone():
            pw_hash, salt = hash_password(DEFAULT_TEACHER_PASS)
            conn.execute(
                "INSERT INTO teachers VALUES (?, ?, ?)",
                (DEFAULT_TEACHER_USER, pw_hash, salt),
            )
        if not conn.execute("SELECT 1 FROM students LIMIT 1").fetchone():
            conn.executemany(
                "INSERT INTO students VALUES (?, ?)",
                [("S001", "Ayesha Khan"), ("S002", "Ali Raza"), ("S003", "Sara Ahmed")],
            )


# ------------------------------------------------------------------- auth
def login_teacher(username, password):
    row = fetch("SELECT * FROM teachers WHERE username = ?", (username.strip(),))
    if not row:
        return False
    expected, _ = hash_password(password, row[0]["salt"])
    return hmac.compare_digest(expected, row[0]["password_hash"])


def login_student(student_id, name):
    row = fetch(
        "SELECT * FROM students WHERE student_id = ? COLLATE NOCASE",
        (student_id.strip(),),
    )
    if not row:
        return None
    if row[0]["name"].strip().lower() != name.strip().lower():
        return None
    return row[0]["student_id"]


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# ------------------------------------------------------------------ stats
def student_stats(student_id):
    row = fetch(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(status = 'Present'), 0) AS present
           FROM attendance WHERE student_id = ?""",
        (student_id,),
    )[0]
    total, present = row["total"], row["present"]
    percent = round(present / total * 100, 1) if total else 0.0
    return total, present, total - present, percent


# ------------------------------------------------------------------ views
def login_page():
    st.title("🎓 Attendance Portal")
    st.caption("Please sign in to continue.")
    student_tab, teacher_tab = st.tabs(["Student", "Teacher"])

    with student_tab:
        with st.form("student_login"):
            sid = st.text_input("Student ID", placeholder="e.g. S001")
            name = st.text_input("Full name")
            if st.form_submit_button("Sign in", use_container_width=True):
                found = login_student(sid, name)
                if found:
                    st.session_state.update(role="student", user=found)
                    st.rerun()
                else:
                    st.error("Invalid Student ID or name.")

    with teacher_tab:
        with st.form("teacher_login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", use_container_width=True):
                if login_teacher(username, password):
                    st.session_state.update(role="teacher", user=username.strip())
                    st.rerun()
                else:
                    st.error("Invalid username or password.")


def teacher_mark_tab():
    st.subheader("Mark attendance")
    day = st.date_input("Date", value=date.today(), max_value=date.today())
    students = fetch("SELECT student_id, name FROM students ORDER BY name")
    if not students:
        st.info("No students yet. Add some in the 'Students' tab.")
        return

    saved = {
        r["student_id"]: r["status"]
        for r in fetch("SELECT student_id, status FROM attendance WHERE date = ?", (day.isoformat(),))
    }
    if saved:
        st.caption("Attendance already recorded for this date - saving will update it.")

    with st.form("mark_form"):
        for s in students:
            col_name, col_status = st.columns([3, 2])
            col_name.markdown(f"**{s['name']}**  \n`{s['student_id']}`")
            col_status.radio(
                "Status",
                ["Present", "Absent"],
                index=1 if saved.get(s["student_id"]) == "Absent" else 0,
                key=f"status_{day}_{s['student_id']}",
                horizontal=True,
                label_visibility="collapsed",
            )
        submitted = st.form_submit_button("Save attendance", type="primary", use_container_width=True)

    if submitted:
        with closing(get_conn()) as conn, conn:
            conn.executemany(
                """INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)
                   ON CONFLICT(student_id, date) DO UPDATE SET status = excluded.status""",
                [
                    (s["student_id"], day.isoformat(), st.session_state[f"status_{day}_{s['student_id']}"])
                    for s in students
                ],
            )
        st.success(f"Attendance saved for {day.strftime('%d %b %Y')}.")


def teacher_report_tab():
    st.subheader("Attendance summary")
    rows = fetch(
        """SELECT s.student_id, s.name,
                  COUNT(a.id) AS total,
                  COALESCE(SUM(a.status = 'Present'), 0) AS present
           FROM students s LEFT JOIN attendance a ON a.student_id = s.student_id
           GROUP BY s.student_id ORDER BY s.name"""
    )
    if not rows:
        st.info("No students yet.")
        return
    df = pd.DataFrame([dict(r) for r in rows])
    df["Absent"] = df["total"] - df["present"]
    df["Attendance %"] = (df["present"] / df["total"].where(df["total"] > 0) * 100).round(1).fillna(0)
    df.columns = ["Student ID", "Name", "Total classes", "Present", "Absent", "Attendance %"]
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Attendance %": st.column_config.ProgressColumn(
                "Attendance %", min_value=0, max_value=100, format="%.1f%%"
            )
        },
    )


def teacher_students_tab():
    st.subheader("Manage students")
    with st.form("add_student", clear_on_submit=True):
        c1, c2 = st.columns(2)
        sid = c1.text_input("Student ID")
        name = c2.text_input("Full name")
        if st.form_submit_button("Add student", use_container_width=True):
            if not sid.strip() or not name.strip():
                st.error("Both Student ID and name are required.")
            else:
                try:
                    run("INSERT INTO students VALUES (?, ?)", (sid.strip(), name.strip()))
                    st.success(f"Added {name.strip()}.")
                except sqlite3.IntegrityError:
                    st.error("That Student ID already exists.")

    students = fetch("SELECT student_id, name FROM students ORDER BY name")
    if students:
        st.dataframe(
            pd.DataFrame([dict(s) for s in students]).rename(
                columns={"student_id": "Student ID", "name": "Name"}
            ),
            hide_index=True,
            use_container_width=True,
        )
        with st.expander("Remove a student"):
            options = {f"{s['name']} ({s['student_id']})": s["student_id"] for s in students}
            choice = st.selectbox("Student", list(options))
            if st.button("Delete student and their records"):
                run("DELETE FROM students WHERE student_id = ?", (options[choice],))
                st.rerun()


def teacher_page():
    st.title("Teacher Dashboard")
    tab_mark, tab_report, tab_students = st.tabs(["Mark attendance", "Summary", "Students"])
    with tab_mark:
        teacher_mark_tab()
    with tab_report:
        teacher_report_tab()
    with tab_students:
        teacher_students_tab()


def student_page(student_id):
    student = fetch("SELECT * FROM students WHERE student_id = ?", (student_id,))
    if not student:  # removed by teacher while logged in
        logout()
        st.rerun()
    st.title(f"Welcome, {student[0]['name']}")
    total, present, absent, percent = student_stats(student_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total classes", total)
    c2.metric("Present", present)
    c3.metric("Absent", absent)
    c4.metric("Attendance", f"{percent}%")

    if total:
        st.progress(min(percent / 100, 1.0))
        if percent < MIN_PERCENT:
            st.warning(f"Your attendance is below the required {MIN_PERCENT}%.")
    else:
        st.info("No attendance has been recorded for you yet.")

    records = fetch(
        "SELECT date, status FROM attendance WHERE student_id = ? ORDER BY date DESC",
        (student_id,),
    )
    if records:
        st.subheader("Attendance history")
        st.dataframe(
            pd.DataFrame([dict(r) for r in records]).rename(columns={"date": "Date", "status": "Status"}),
            hide_index=True,
            use_container_width=True,
        )


# ------------------------------------------------------------------- main
def main():
    init_db()
    role = st.session_state.get("role")

    if not role:
        login_page()
        return

    with st.sidebar:
        st.markdown("### 🎓 Attendance Portal")
        st.write(f"Signed in as **{st.session_state['user']}**")
        st.caption(role.capitalize())
        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()

    if role == "teacher":
        teacher_page()
    else:
        student_page(st.session_state["user"])


main()
