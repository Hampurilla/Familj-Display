from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta
import calendar
import subprocess
import os
import random

app = Flask(__name__)
app.secret_key = os.environ.get("HOME_DISPLAY_SECRET", "change-me-local-only")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "home_display.db"
DB_PATH.parent.mkdir(exist_ok=True)

RECURRENCE_TYPES = {"once", "daily", "weekly", "biweekly", "monthly"}

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn

def bump_version(conn):
    conn.execute("UPDATE system_state SET version = version + 1 WHERE id = 1")

def init_db():
    conn = get_db()
    conn.execute("PRAGMA journal_mode = WAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 3,
            recurrence TEXT NOT NULL DEFAULT 'once',
            weekday INTEGER,
            month_day INTEGER,
            start_date TEXT NOT NULL,
            assignment_mode TEXT NOT NULL DEFAULT 'auto',
            fixed_user_id INTEGER,
            active INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            FOREIGN KEY (fixed_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 3,
            due_date TEXT NOT NULL,
            notes TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (template_id) REFERENCES task_templates(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(template_id, due_date)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            version INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("INSERT OR IGNORE INTO system_state(id, version) VALUES(1, 1)")
    conn.commit()
    conn.close()

def parse_iso(d):
    return datetime.strptime(d, "%Y-%m-%d").date()

def add_months(d, months=1):
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def template_due_on(t, target):
    start = parse_iso(t["start_date"])
    if target < start:
        return False

    r = t["recurrence"]
    if r == "once":
        return target == start
    if r == "daily":
        return True
    if r == "weekly":
        return target.weekday() == t["weekday"]
    if r == "biweekly":
        delta = (target - start).days
        return delta >= 0 and delta % 14 == 0
    if r == "monthly":
        desired = t["month_day"] or start.day
        return target.day == min(desired, calendar.monthrange(target.year, target.month)[1])
    return False

def choose_user_automatically(conn, due_date, difficulty):
    users = conn.execute("SELECT id FROM users WHERE active = 1 ORDER BY id").fetchall()
    if not users:
        return None

    scored = []
    for u in users:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN completed = 0 THEN difficulty ELSE 0 END), 0) AS load,
                COUNT(CASE WHEN completed = 0 THEN 1 END) AS jobs
            FROM tasks
            WHERE user_id = ? AND due_date = ?
        """, (u["id"], due_date)).fetchone()
        scored.append((row["load"], row["jobs"], random.random(), u["id"]))

    scored.sort()
    return scored[0][3]

def create_task_instance(conn, template, due):
    exists = conn.execute("""
        SELECT 1 FROM tasks WHERE template_id = ? AND due_date = ?
    """, (template["id"], due.isoformat())).fetchone()
    if exists:
        return

    if template["assignment_mode"] == "fixed" and template["fixed_user_id"]:
        user_id = template["fixed_user_id"]
    else:
        user_id = choose_user_automatically(conn, due.isoformat(), template["difficulty"])

    if not user_id:
        return

    conn.execute("""
        INSERT OR IGNORE INTO tasks
        (template_id, user_id, title, difficulty, due_date, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        template["id"], user_id, template["title"], template["difficulty"],
        due.isoformat(), template["notes"]
    ))

def generate_tasks(days_ahead=30):
    conn = get_db()
    templates = conn.execute("SELECT * FROM task_templates WHERE active = 1").fetchall()
    today = date.today()
    changed = False

    for offset in range(days_ahead + 1):
        target = today + timedelta(days=offset)
        for t in templates:
            before = conn.total_changes
            if template_due_on(t, target):
                create_task_instance(conn, t, target)
            if conn.total_changes > before:
                changed = True

    if changed:
        bump_version(conn)
    conn.commit()
    conn.close()

@app.before_request
def ensure_generated():
    if request.endpoint not in {"static", "api_version"}:
        generate_tasks(14)

@app.route("/api/version")
def api_version():
    conn = get_db()
    row = conn.execute("SELECT version FROM system_state WHERE id = 1").fetchone()
    conn.close()
    return jsonify(version=row["version"])

@app.route("/")
def home():
    conn = get_db()
    users = conn.execute("""
        SELECT
            u.id, u.name,
            COUNT(t.id) AS total_tasks,
            COALESCE(SUM(CASE WHEN t.completed = 1 THEN 1 ELSE 0 END), 0) AS completed_tasks,
            COALESCE(SUM(CASE WHEN t.completed = 0 THEN t.difficulty ELSE 0 END), 0) AS points_left
        FROM users u
        LEFT JOIN tasks t
          ON t.user_id = u.id
         AND t.due_date <= ?
        WHERE u.active = 1
        GROUP BY u.id
        ORDER BY u.name COLLATE NOCASE
    """, (date.today().isoformat(),)).fetchall()
    conn.close()
    return render_template("home.html", users=users, today=date.today())

@app.route("/user/<int:user_id>")
def user_page(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,)).fetchone()
    if not user:
        conn.close()
        return "Användaren finns inte", 404

    tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ? AND due_date <= ?
        ORDER BY completed ASC, due_date ASC, difficulty DESC, id DESC
    """, (user_id, date.today().isoformat())).fetchall()

    future = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ? AND due_date > ?
        ORDER BY due_date ASC, difficulty DESC
        LIMIT 10
    """, (user_id, date.today().isoformat())).fetchall()

    conn.close()
    return render_template("user.html", user=user, tasks=tasks, future=future, today=date.today().isoformat())

@app.post("/task/<int:task_id>/toggle")
def toggle_task(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return "Uppgiften finns inte", 404

    new_state = 0 if task["completed"] else 1
    conn.execute("""
        UPDATE tasks
        SET completed = ?, completed_at = ?
        WHERE id = ?
    """, (new_state, datetime.now().isoformat(timespec="seconds") if new_state else None, task_id))
    bump_version(conn)
    conn.commit()
    user_id = task["user_id"]
    conn.close()
    return redirect(url_for("user_page", user_id=user_id))

@app.route("/admin")
def admin():
    conn = get_db()
    users = conn.execute("SELECT * FROM users WHERE active = 1 ORDER BY name COLLATE NOCASE").fetchall()
    templates = conn.execute("""
        SELECT tt.*, u.name AS fixed_user_name
        FROM task_templates tt
        LEFT JOIN users u ON u.id = tt.fixed_user_id
        WHERE tt.active = 1
        ORDER BY tt.id DESC
    """).fetchall()
    conn.close()
    return render_template("admin.html", users=users, templates=templates, today=date.today().isoformat())

@app.post("/admin/user/add")
def add_user():
    name = request.form.get("name", "").strip()
    if name:
        conn = get_db()
        conn.execute("INSERT INTO users(name) VALUES(?)", (name,))
        bump_version(conn)
        conn.commit()
        conn.close()
    return redirect(url_for("admin"))

@app.post("/admin/user/<int:user_id>/delete")
def delete_user(user_id):
    conn = get_db()
    conn.execute("UPDATE users SET active = 0 WHERE id = ?", (user_id,))
    bump_version(conn)
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.post("/admin/template/add")
def add_template():
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("admin"))

    recurrence = request.form.get("recurrence", "once")
    if recurrence not in RECURRENCE_TYPES:
        recurrence = "once"

    try:
        difficulty = max(1, min(10, int(request.form.get("difficulty", 3))))
    except ValueError:
        difficulty = 3

    start_date = request.form.get("start_date") or date.today().isoformat()
    assignment_mode = request.form.get("assignment_mode", "auto")
    fixed_user_id = request.form.get("fixed_user_id")
    fixed_user_id = int(fixed_user_id) if fixed_user_id and fixed_user_id.isdigit() else None
    notes = request.form.get("notes", "").strip() or None

    start = parse_iso(start_date)
    weekday = start.weekday() if recurrence == "weekly" else None
    month_day = start.day if recurrence == "monthly" else None

    conn = get_db()
    conn.execute("""
        INSERT INTO task_templates
        (title, difficulty, recurrence, weekday, month_day, start_date,
         assignment_mode, fixed_user_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title, difficulty, recurrence, weekday, month_day, start_date,
        assignment_mode, fixed_user_id if assignment_mode == "fixed" else None, notes
    ))
    bump_version(conn)
    conn.commit()
    conn.close()

    generate_tasks(30)
    return redirect(url_for("admin"))

@app.post("/admin/template/<int:template_id>/delete")
def delete_template(template_id):
    conn = get_db()
    conn.execute("UPDATE task_templates SET active = 0 WHERE id = ?", (template_id,))
    bump_version(conn)
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.post("/admin/regenerate")
def regenerate():
    generate_tasks(60)
    return redirect(url_for("admin"))

@app.route("/health")
def health():
    return jsonify(ok=True, time=datetime.now().isoformat(timespec="seconds"))

if __name__ == "__main__":
    init_db()
    generate_tasks(30)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
