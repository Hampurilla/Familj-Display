from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta
import calendar
import random
import urllib.parse
import urllib.request
import json
import time
import os

app = Flask(__name__)
app.secret_key = os.environ.get("HOME_DISPLAY_SECRET", "familj-display-local")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "home_display.db"
DB_PATH.parent.mkdir(exist_ok=True)

RECURRENCE_TYPES = {"once", "daily", "weekly", "biweekly", "monthly"}

REWARDS = [('🐧', 'Snyggt jobbat!'), ('🦊', 'Yes! Avklarat!'), ('🦦', 'Du fixade det!'), ('🐼', 'Bra momentum!'), ('🐸', 'Grymt!'), ('🦝', 'En grej mindre!'), ('🐢', 'Uppdrag slutfört!'), ('🦄', 'Boom! Klart!'), ('🐈', 'Snyggt jobbat!'), ('🐕', 'Yes! Avklarat!'), ('🦔', 'Du fixade det!'), ('🐙', 'Bra momentum!'), ('🦁', 'Grymt!'), ('🐯', 'En grej mindre!'), ('🐨', 'Uppdrag slutfört!'), ('🐻', 'Boom! Klart!'), ('🐻\u200d❄️', 'Snyggt jobbat!'), ('🐰', 'Yes! Avklarat!'), ('🐹', 'Du fixade det!'), ('🐭', 'Bra momentum!'), ('🐮', 'Grymt!'), ('🐷', 'En grej mindre!'), ('🐵', 'Uppdrag slutfört!'), ('🐺', 'Boom! Klart!'), ('🦓', 'Snyggt jobbat!'), ('🦒', 'Yes! Avklarat!'), ('🦘', 'Du fixade det!'), ('🦬', 'Bra momentum!'), ('🦣', 'Grymt!'), ('🦏', 'En grej mindre!'), ('🦛', 'Uppdrag slutfört!'), ('🐘', 'Boom! Klart!'), ('🦥', 'Snyggt jobbat!'), ('🦨', 'Yes! Avklarat!'), ('🦡', 'Du fixade det!'), ('🐿️', 'Bra momentum!'), ('🦫', 'Grymt!'), ('🦅', 'En grej mindre!'), ('🦉', 'Uppdrag slutfört!'), ('🦜', 'Boom! Klart!'), ('🦚', 'Snyggt jobbat!'), ('🦩', 'Yes! Avklarat!'), ('🕊️', 'Du fixade det!'), ('🐦', 'Bra momentum!'), ('🐤', 'Grymt!'), ('🐥', 'En grej mindre!'), ('🦆', 'Uppdrag slutfört!'), ('🪿', 'Boom! Klart!'), ('🦢', 'Snyggt jobbat!'), ('🐓', 'Yes! Avklarat!'), ('🦃', 'Du fixade det!'), ('🐦\u200d⬛', 'Bra momentum!'), ('🦤', 'Grymt!'), ('🐝', 'En grej mindre!'), ('🦋', 'Uppdrag slutfört!'), ('🐞', 'Boom! Klart!'), ('🪲', 'Snyggt jobbat!'), ('🐛', 'Yes! Avklarat!'), ('🕷️', 'Du fixade det!'), ('🦂', 'Bra momentum!'), ('🐌', 'Grymt!'), ('🐜', 'En grej mindre!'), ('🦗', 'Uppdrag slutfört!'), ('🐢', 'Boom! Klart!'), ('🦎', 'Snyggt jobbat!'), ('🐍', 'Yes! Avklarat!'), ('🐊', 'Du fixade det!'), ('🐲', 'Bra momentum!'), ('🐉', 'Grymt!'), ('🦕', 'En grej mindre!'), ('🦖', 'Uppdrag slutfört!'), ('🐳', 'Boom! Klart!'), ('🐋', 'Snyggt jobbat!'), ('🐬', 'Yes! Avklarat!'), ('🦭', 'Du fixade det!'), ('🦈', 'Bra momentum!'), ('🐟', 'Grymt!'), ('🐠', 'En grej mindre!'), ('🐡', 'Uppdrag slutfört!'), ('🦀', 'Boom! Klart!'), ('🦞', 'Snyggt jobbat!'), ('🦐', 'Yes! Avklarat!'), ('🦑', 'Du fixade det!'), ('🪼', 'Bra momentum!'), ('⭐', 'Grymt!'), ('🌟', 'En grej mindre!'), ('✨', 'Uppdrag slutfört!'), ('💫', 'Boom! Klart!'), ('🌈', 'Snyggt jobbat!'), ('🔥', 'Yes! Avklarat!'), ('⚡', 'Du fixade det!'), ('❄️', 'Bra momentum!'), ('🌊', 'Grymt!'), ('🌙', 'En grej mindre!'), ('☀️', 'Uppdrag slutfört!'), ('🪐', 'Boom! Klart!'), ('☄️', 'Snyggt jobbat!'), ('🚀', 'Yes! Avklarat!'), ('🛸', 'Du fixade det!'), ('✈️', 'Bra momentum!'), ('🏎️', 'Grymt!'), ('🚗', 'En grej mindre!'), ('🏍️', 'Uppdrag slutfört!'), ('🚂', 'Boom! Klart!'), ('⛵', 'Snyggt jobbat!'), ('🚁', 'Yes! Avklarat!'), ('🎈', 'Du fixade det!'), ('🎯', 'Bra momentum!'), ('🏆', 'Grymt!'), ('🥇', 'En grej mindre!'), ('💎', 'Uppdrag slutfört!'), ('👑', 'Boom! Klart!'), ('🎸', 'Snyggt jobbat!'), ('🎹', 'Yes! Avklarat!'), ('🥁', 'Du fixade det!'), ('🎨', 'Bra momentum!'), ('🧩', 'Grymt!'), ('🎲', 'En grej mindre!'), ('🕹️', 'Uppdrag slutfört!'), ('🤖', 'Boom! Klart!'), ('👾', 'Snyggt jobbat!'), ('🧠', 'Yes! Avklarat!'), ('💡', 'Du fixade det!'), ('🔧', 'Bra momentum!'), ('⚙️', 'Grymt!'), ('🛠️', 'En grej mindre!'), ('🔋', 'Uppdrag slutfört!'), ('🔌', 'Boom! Klart!')]

_weather_cache = {"key": None, "at": 0, "data": None}


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def column_names(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_column(conn, table, name, definition):
    if name not in column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def bump_version(conn):
    conn.execute("UPDATE system_state SET version = version + 1 WHERE id = 1")


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute("""
        INSERT INTO settings(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))


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
            start_date TEXT NOT NULL DEFAULT CURRENT_DATE,
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
            due_date TEXT NOT NULL DEFAULT CURRENT_DATE,
            notes TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (template_id) REFERENCES task_templates(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    ensure_column(conn, "users", "active", "INTEGER NOT NULL DEFAULT 1")

    for name, definition in {
        "difficulty": "INTEGER NOT NULL DEFAULT 3",
        "recurrence": "TEXT NOT NULL DEFAULT 'once'",
        "weekday": "INTEGER",
        "month_day": "INTEGER",
        "start_date": "TEXT",
        "assignment_mode": "TEXT NOT NULL DEFAULT 'auto'",
        "fixed_user_id": "INTEGER",
        "active": "INTEGER NOT NULL DEFAULT 1",
        "notes": "TEXT",
    }.items():
        ensure_column(conn, "task_templates", name, definition)

    for name, definition in {
        "template_id": "INTEGER",
        "difficulty": "INTEGER NOT NULL DEFAULT 3",
        "due_date": "TEXT",
        "notes": "TEXT",
        "completed": "INTEGER NOT NULL DEFAULT 0",
        "created_at": "TEXT",
        "completed_at": "TEXT",
    }.items():
        ensure_column(conn, "tasks", name, definition)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            version INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("INSERT OR IGNORE INTO system_state(id, version) VALUES(1, 1)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    for k, v in {
        "weather_name": "Borås",
        "weather_lat": "57.721",
        "weather_lon": "12.940",
        "rewards_enabled": "1",
        "idle_minutes": "15",
        "screensaver_enabled": "1",
        "night_enabled": "1",
        "night_start": "22:30",
        "night_end": "07:00",
    }.items():
        conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, v))

    today = date.today().isoformat()
    conn.execute("UPDATE task_templates SET start_date = ? WHERE start_date IS NULL OR start_date = ''", (today,))
    conn.execute("UPDATE tasks SET due_date = ? WHERE due_date IS NULL OR due_date = ''", (today,))
    conn.execute("UPDATE tasks SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    try:
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_template_due
            ON tasks(template_id, due_date)
            WHERE template_id IS NOT NULL
        """)
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()


def parse_iso(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def template_due_on(t, target):
    start = parse_iso(t["start_date"])
    if target < start:
        return False
    recurrence = t["recurrence"]
    if recurrence == "once":
        return target == start
    if recurrence == "daily":
        return True
    if recurrence == "weekly":
        wanted = t["weekday"] if t["weekday"] is not None else start.weekday()
        return target.weekday() == wanted
    if recurrence == "biweekly":
        return (target - start).days % 14 == 0
    if recurrence == "monthly":
        wanted = t["month_day"] or start.day
        return target.day == min(wanted, calendar.monthrange(target.year, target.month)[1])
    return False


def choose_user_automatically(conn, due_date):
    users = conn.execute("SELECT id FROM users WHERE active = 1 ORDER BY id").fetchall()
    if not users:
        return None

    scores = []
    for user in users:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN completed = 0 THEN difficulty ELSE 0 END), 0) AS load,
                COUNT(CASE WHEN completed = 0 THEN 1 END) AS jobs
            FROM tasks
            WHERE user_id = ? AND due_date = ?
        """, (user["id"], due_date)).fetchone()
        scores.append((row["load"], row["jobs"], random.random(), user["id"]))

    scores.sort()
    return scores[0][3]


def create_task_instance(conn, template, due):
    exists = conn.execute(
        "SELECT 1 FROM tasks WHERE template_id = ? AND due_date = ?",
        (template["id"], due.isoformat())
    ).fetchone()
    if exists:
        return False

    if template["assignment_mode"] == "fixed" and template["fixed_user_id"]:
        user_id = template["fixed_user_id"]
    else:
        user_id = choose_user_automatically(conn, due.isoformat())

    if not user_id:
        return False

    conn.execute("""
        INSERT INTO tasks(template_id, user_id, title, difficulty, due_date, notes)
        VALUES(?, ?, ?, ?, ?, ?)
    """, (
        template["id"], user_id, template["title"], template["difficulty"],
        due.isoformat(), template["notes"]
    ))
    return True


def generate_tasks(days_ahead=30):
    conn = get_db()
    templates = conn.execute("SELECT * FROM task_templates WHERE active = 1").fetchall()
    today = date.today()
    changed = False

    for offset in range(days_ahead + 1):
        target = today + timedelta(days=offset)
        for template in templates:
            if template_due_on(template, target):
                try:
                    if create_task_instance(conn, template, target):
                        changed = True
                except sqlite3.IntegrityError:
                    pass

    if changed:
        bump_version(conn)
    conn.commit()
    conn.close()


def dashboard_data(conn):
    today = date.today().isoformat()
    row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END), 0) AS done,
            COALESCE(SUM(difficulty), 0) AS total_points,
            COALESCE(SUM(CASE WHEN completed = 1 THEN difficulty ELSE 0 END), 0) AS done_points
        FROM tasks
        WHERE due_date = ?
    """, (today,)).fetchone()

    total = row["total"] or 0
    done = row["done"] or 0
    percent = round((done / total) * 100) if total else 100
    return {
        "total": total,
        "done": done,
        "percent": percent,
        "total_points": row["total_points"] or 0,
        "done_points": row["done_points"] or 0,
    }


def weather_code_text(code):
    mapping = {
        0: ("☀️", "Klart"),
        1: ("🌤️", "Mestadels klart"),
        2: ("⛅", "Delvis molnigt"),
        3: ("☁️", "Mulet"),
        45: ("🌫️", "Dimma"),
        48: ("🌫️", "Rimfrost/dimma"),
        51: ("🌦️", "Lätt duggregn"),
        53: ("🌦️", "Duggregn"),
        55: ("🌧️", "Kraftigt duggregn"),
        61: ("🌦️", "Lätt regn"),
        63: ("🌧️", "Regn"),
        65: ("🌧️", "Kraftigt regn"),
        71: ("🌨️", "Lätt snö"),
        73: ("🌨️", "Snö"),
        75: ("❄️", "Kraftig snö"),
        80: ("🌦️", "Regnskurar"),
        81: ("🌧️", "Regnskurar"),
        82: ("⛈️", "Kraftiga skurar"),
        95: ("⛈️", "Åska"),
        96: ("⛈️", "Åska och hagel"),
        99: ("⛈️", "Kraftig åska"),
    }
    return mapping.get(code, ("🌡️", "Väder"))


def fetch_weather():
    global _weather_cache
    conn = get_db()
    name = get_setting(conn, "weather_name", "Borås")
    lat = get_setting(conn, "weather_lat", "57.721")
    lon = get_setting(conn, "weather_lon", "12.940")
    conn.close()

    key = (name, lat, lon)
    now = time.time()
    if _weather_cache["key"] == key and now - _weather_cache["at"] < 900:
        return _weather_cache["data"]

    try:
        params = urllib.parse.urlencode({
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,weather_code",
            "timezone": "auto",
            "forecast_days": 3,
        })
        with urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?" + params, timeout=5) as response:
            raw = json.loads(response.read().decode("utf-8"))

        current = raw["current"]
        daily = raw["daily"]
        icon, text = weather_code_text(int(current["weather_code"]))

        days = []
        sv = {"Mon":"Mån","Tue":"Tis","Wed":"Ons","Thu":"Tor","Fri":"Fre","Sat":"Lör","Sun":"Sön"}
        for i in range(min(3, len(daily["time"]))):
            d = parse_iso(daily["time"][i])
            d_icon, _ = weather_code_text(int(daily["weather_code"][i]))
            label = "Idag" if i == 0 else sv.get(d.strftime("%a"), d.strftime("%a"))
            days.append({
                "label": label,
                "icon": d_icon,
                "max": round(daily["temperature_2m_max"][i]),
                "min": round(daily["temperature_2m_min"][i]),
            })

        data = {
            "ok": True,
            "name": name,
            "icon": icon,
            "text": text,
            "temp": round(current["temperature_2m"]),
            "feels": round(current["apparent_temperature"]),
            "wind": round(current["wind_speed_10m"]),
            "days": days,
        }
    except Exception:
        data = {"ok": False, "name": name}

    _weather_cache = {"key": key, "at": now, "data": data}
    return data


@app.before_request
def before_every_request():
    if request.endpoint not in {"static", "api_version", "api_weather", "api_display_settings", "health"}:
        generate_tasks(30)


@app.route("/api/version")
def api_version():
    conn = get_db()
    row = conn.execute("SELECT version FROM system_state WHERE id = 1").fetchone()
    conn.close()
    return jsonify(version=row["version"])


@app.route("/api/weather")
def api_weather():
    return jsonify(fetch_weather())


@app.route("/api/display-settings")
def api_display_settings():
    conn = get_db()
    data = {
        "idle_minutes": get_setting(conn, "idle_minutes", "15"),
        "screensaver_enabled": get_setting(conn, "screensaver_enabled", "1"),
        "night_enabled": get_setting(conn, "night_enabled", "1"),
        "night_start": get_setting(conn, "night_start", "22:30"),
        "night_end": get_setting(conn, "night_end", "07:00"),
    }
    conn.close()
    return jsonify(data)


@app.route("/health")
def health():
    return jsonify(ok=True, time=datetime.now().isoformat(timespec="seconds"))


@app.route("/")
def home():
    conn = get_db()
    today = date.today().isoformat()

    users = conn.execute("""
        SELECT
            u.id, u.name,
            COUNT(t.id) AS total_tasks,
            COALESCE(SUM(CASE WHEN t.completed = 1 THEN 1 ELSE 0 END), 0) AS completed_tasks,
            COALESCE(SUM(CASE WHEN t.completed = 0 THEN t.difficulty ELSE 0 END), 0) AS points_left
        FROM users u
        LEFT JOIN tasks t ON t.user_id = u.id AND t.due_date <= ?
        WHERE u.active = 1
        GROUP BY u.id
        ORDER BY u.name COLLATE NOCASE
    """, (today,)).fetchall()

    dash = dashboard_data(conn)
    conn.close()
    return render_template("home.html", users=users, dash=dash)


@app.route("/user/<int:user_id>")
def user_page(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,)).fetchone()
    if not user:
        conn.close()
        return "Användaren finns inte", 404

    today = date.today().isoformat()
    tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ? AND due_date <= ?
        ORDER BY completed ASC, due_date ASC, difficulty DESC, id DESC
    """, (user_id, today)).fetchall()

    future = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ? AND due_date > ?
        ORDER BY due_date ASC, difficulty DESC
        LIMIT 12
    """, (user_id, today)).fetchall()

    stats = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN due_date = ? THEN difficulty ELSE 0 END), 0) AS today_total,
            COALESCE(SUM(CASE WHEN due_date = ? AND completed = 1 THEN difficulty ELSE 0 END), 0) AS today_done
        FROM tasks WHERE user_id = ?
    """, (today, today, user_id)).fetchone()

    conn.close()
    return render_template("user.html", user=user, tasks=tasks, future=future, stats=stats, today=today)


@app.post("/api/task/<int:task_id>/toggle")
def api_toggle_task(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify(ok=False), 404

    new_state = 0 if task["completed"] else 1
    conn.execute("""
        UPDATE tasks
        SET completed = ?, completed_at = ?
        WHERE id = ?
    """, (
        new_state,
        datetime.now().isoformat(timespec="seconds") if new_state else None,
        task_id
    ))
    bump_version(conn)

    rewards_enabled = get_setting(conn, "rewards_enabled", "1") == "1"
    conn.commit()
    conn.close()

    reward = None
    if new_state and rewards_enabled:
        emoji, message = random.choice(REWARDS)
        reward = {"emoji": emoji, "message": message, "points": task["difficulty"]}

    return jsonify(ok=True, completed=bool(new_state), reward=reward)


@app.post("/task/<int:task_id>/toggle")
def toggle_task_fallback(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return "Uppgiften finns inte", 404

    new_state = 0 if task["completed"] else 1
    conn.execute("""
        UPDATE tasks SET completed = ?, completed_at = ? WHERE id = ?
    """, (
        new_state,
        datetime.now().isoformat(timespec="seconds") if new_state else None,
        task_id
    ))
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

    settings = {
        "weather_name": get_setting(conn, "weather_name", "Borås"),
        "weather_lat": get_setting(conn, "weather_lat", "57.721"),
        "weather_lon": get_setting(conn, "weather_lon", "12.940"),
        "rewards_enabled": get_setting(conn, "rewards_enabled", "1"),
        "idle_minutes": get_setting(conn, "idle_minutes", "15"),
        "screensaver_enabled": get_setting(conn, "screensaver_enabled", "1"),
        "night_enabled": get_setting(conn, "night_enabled", "1"),
        "night_start": get_setting(conn, "night_start", "22:30"),
        "night_end": get_setting(conn, "night_end", "07:00"),
    }
    conn.close()
    return render_template("admin.html", users=users, templates=templates, settings=settings, today=date.today().isoformat())


@app.post("/admin/settings")
def save_settings():
    global _weather_cache
    conn = get_db()
    set_setting(conn, "weather_name", request.form.get("weather_name", "Borås").strip() or "Borås")
    set_setting(conn, "weather_lat", request.form.get("weather_lat", "57.721").strip() or "57.721")
    set_setting(conn, "weather_lon", request.form.get("weather_lon", "12.940").strip() or "12.940")
    set_setting(conn, "rewards_enabled", "1" if request.form.get("rewards_enabled") == "on" else "0")
    set_setting(conn, "idle_minutes", request.form.get("idle_minutes", "15").strip() or "15")
    set_setting(conn, "screensaver_enabled", "1" if request.form.get("screensaver_enabled") == "on" else "0")
    set_setting(conn, "night_enabled", "1" if request.form.get("night_enabled") == "on" else "0")
    set_setting(conn, "night_start", request.form.get("night_start", "22:30").strip() or "22:30")
    set_setting(conn, "night_end", request.form.get("night_end", "07:00").strip() or "07:00")
    bump_version(conn)
    conn.commit()
    conn.close()
    _weather_cache = {"key": None, "at": 0, "data": None}
    return redirect(url_for("admin"))


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
         assignment_mode, fixed_user_id, active, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
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


if __name__ == "__main__":
    init_db()
    generate_tasks(30)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
