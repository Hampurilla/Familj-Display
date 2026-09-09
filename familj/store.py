"""SQLite domain layer. No Flask or network dependency; tested independently.

All multi-statement writes use BEGIN IMMEDIATE. Existing tables/IDs are kept.
Dates are ISO civil dates in Europe/Stockholm, not UTC calendar dates.
"""
from __future__ import annotations
import calendar
import hashlib
import json
import logging
import math
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager, closing
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from .badges import BADGES, RARITIES, MESSAGES

LOG = logging.getLogger(__name__)
TZ = ZoneInfo('Europe/Stockholm')
SCHEMA = 5
RECURRENCES = {'once': 'En g\u00e5ng', 'daily': 'Varje dag', 'weekly': 'Varje vecka',
               'biweekly': 'Varannan vecka', 'monthly': 'Varje m\u00e5nad'}
ACCENTS = ('sage', 'clay', 'blue', 'honey', 'lilac', 'rose')
DEFAULTS = {
    'house_name': 'Familjen', 'house_note': 'En sak i taget. Vi hj\u00e4lps \u00e5t.',
    'weather_name': 'Bor\u00e5s', 'weather_lat': '57.721', 'weather_lon': '12.940',
    'rewards_enabled': '1', 'idle_minutes': '15', 'screensaver_enabled': '1',
    'night_enabled': '1', 'night_start': '22:30', 'night_end': '07:00',
    'family_goal': 'Lite mer tid tillsammans.', 'admin_pin_hash': '',
}


def local_now():
    return datetime.now(TZ)


def iso_date(value: str) -> date:
    try:
        d = date.fromisoformat(value)
        if d.isoformat() != value or not 2000 <= d.year <= 2100:
            raise ValueError
        return d
    except (TypeError, ValueError):
        raise ValueError('V\u00e4lj ett giltigt datum (2000\u20132100).') from None


def due_on(t: dict, target: date) -> bool:
    start = iso_date(t['start_date'])
    if target < start or (t.get('end_date') and target > iso_date(t['end_date'])):
        return False
    r = t['recurrence']
    if r == 'once': return target == start
    if r == 'daily': return True
    if r == 'weekly': return (target - start).days % 7 == 0
    if r == 'biweekly': return (target - start).days % 14 == 0
    if r == 'monthly':
        day = t.get('month_day') or start.day
        return target.day == min(day, calendar.monthrange(target.year, target.month)[1])
    return False


def pin_hash(pin: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', pin.encode(), salt.encode(), 260000).hex()
    return f'260000${salt}${digest}'


def pin_matches(pin: str, saved: str) -> bool:
    try:
        rounds, salt, digest = saved.split('$')
        got = hashlib.pbkdf2_hmac('sha256', pin.encode(), salt.encode(), int(rounds)).hex()
        return secrets.compare_digest(digest, got)
    except (ValueError, TypeError): return False


class Store:
    def __init__(self, root: Path, now=local_now):
        self.root = Path(root)
        self.data = self.root / 'data'
        self.data.mkdir(parents=True, exist_ok=True)
        self.path = self.data / 'home_display.db'
        self.now = now
        self.lock = threading.Lock()
        self.last_schedule_day = None
        # Original prototypes stored the database in the project root.
        old = self.root / 'home_display.db'
        if not self.path.exists() and old.exists():
            with closing(sqlite3.connect(old)) as src, closing(sqlite3.connect(self.path)) as dst:
                src.backup(dst)
            LOG.info('Copied legacy root database; original preserved.')
        self.migrate()

    def connect(self):
        c = sqlite3.connect(self.path, timeout=8, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA busy_timeout=8000')
        return c

    @contextmanager
    def db(self, write=False):
        c = self.connect()
        try:
            c.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def backup(self, label='manual') -> Path:
        folder = self.data / 'backups'
        folder.mkdir(exist_ok=True)
        stamp = self.now().strftime('%Y%m%d-%H%M%S-%f')
        dest = folder / f'{stamp}-{label}.sqlite3'
        with closing(self.connect()) as src, closing(sqlite3.connect(dest)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed; refusing migration.')
        return dest

    @staticmethod
    def columns(c, table):
        return {r['name'] for r in c.execute(f'PRAGMA table_info({table})')}

    def migrate(self):
        with closing(self.connect()) as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Database is damaged. Original preserved; restore a backup.')
            c.execute('PRAGMA journal_mode=WAL')
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            done = c.execute('SELECT MAX(version) FROM fd_migrations').fetchone()[0] if 'fd_migrations' in tables else 0
        if done and done > SCHEMA:
            raise RuntimeError('Database is newer than this app. Do not downgrade without a backup.')
        if done == SCHEMA:
            return
        if tables:
            self.backup('before-v5')
        today = self.now().date().isoformat()
        with self.db(True) as c:
            c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1)')
            if 'people' in tables and 'users' not in tables:
                c.execute('INSERT INTO users(id,name) SELECT id,name FROM people')
            c.execute("CREATE TABLE IF NOT EXISTS task_templates(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL)")
            additions = {
                'users': {'active': 'INTEGER NOT NULL DEFAULT 1', 'accent': "TEXT NOT NULL DEFAULT 'sage'", 'share_weight': 'REAL NOT NULL DEFAULT 1'},
                'task_templates': {
                    'difficulty': 'INTEGER NOT NULL DEFAULT 3', 'recurrence': "TEXT NOT NULL DEFAULT 'once'",
                    'weekday': 'INTEGER', 'month_day': 'INTEGER', 'start_date': 'TEXT', 'end_date': 'TEXT',
                    'assignment_mode': "TEXT NOT NULL DEFAULT 'auto'", 'fixed_user_id': 'INTEGER',
                    'active': 'INTEGER NOT NULL DEFAULT 1', 'notes': 'TEXT', 'eligible_ids': "TEXT NOT NULL DEFAULT '[]'"},
                'tasks': {'template_id': 'INTEGER', 'user_id': 'INTEGER', 'difficulty': 'INTEGER NOT NULL DEFAULT 3',
                    'due_date': 'TEXT', 'notes': 'TEXT', 'completed': 'INTEGER NOT NULL DEFAULT 0',
                    'created_at': 'TEXT', 'completed_at': 'TEXT', 'cancelled': 'INTEGER NOT NULL DEFAULT 0',
                    'assignment_mode': "TEXT NOT NULL DEFAULT 'fixed'", 'reward_claimed': 'INTEGER NOT NULL DEFAULT 0'},
            }
            for table, fields in additions.items():
                existing = self.columns(c, table)
                for field, declaration in fields.items():
                    if field not in existing:
                        c.execute(f'ALTER TABLE {table} ADD COLUMN {field} {declaration}')
            if 'person_id' in self.columns(c, 'tasks'):
                c.execute('UPDATE tasks SET user_id=person_id WHERE user_id IS NULL')
            for i, row in enumerate(c.execute('SELECT id FROM users ORDER BY id').fetchall()):
                c.execute('UPDATE users SET accent=? WHERE id=?', (ACCENTS[i % len(ACCENTS)], row['id']))
            c.execute("UPDATE task_templates SET start_date=? WHERE start_date IS NULL OR start_date=''", (today,))
            c.execute("UPDATE tasks SET due_date=? WHERE due_date IS NULL OR due_date=''", (today,))
            c.execute('UPDATE tasks SET created_at=CURRENT_TIMESTAMP WHERE created_at IS NULL')
            c.execute('UPDATE tasks SET reward_claimed=1 WHERE completed=1')
            c.execute("UPDATE tasks SET assignment_mode=COALESCE((SELECT CASE WHEN assignment_mode='auto' THEN 'auto' ELSE 'fixed' END FROM task_templates t WHERE t.id=tasks.template_id),'fixed')")
            c.execute('CREATE TABLE IF NOT EXISTS system_state(id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL DEFAULT 1)')
            c.execute('INSERT OR IGNORE INTO system_state(id,version) VALUES(1,1)')
            c.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            for key, value in DEFAULTS.items():
                c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)', (key, value))
            c.execute('CREATE TABLE IF NOT EXISTS fd_migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS fd_occurrences(template_id INTEGER NOT NULL,due_date TEXT NOT NULL,task_id INTEGER NOT NULL,PRIMARY KEY(template_id,due_date))')
            c.execute('INSERT OR IGNORE INTO fd_occurrences SELECT template_id,due_date,MIN(id) FROM tasks WHERE template_id IS NOT NULL GROUP BY template_id,due_date')
            c.execute('CREATE TABLE IF NOT EXISTS user_badges(user_id INTEGER NOT NULL,badge_id INTEGER NOT NULL,unlock_count INTEGER NOT NULL DEFAULT 1,first_unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,last_unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,badge_id))')
            c.execute('CREATE TABLE IF NOT EXISTS fd_reward_events(task_id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,badge_id INTEGER NOT NULL,earned_at TEXT NOT NULL)')
            c.execute('CREATE INDEX IF NOT EXISTS fd_tasks_user_date ON tasks(user_id,due_date,cancelled,completed)')
            c.execute('CREATE INDEX IF NOT EXISTS fd_tasks_template ON tasks(template_id,due_date)')
            c.execute('INSERT INTO fd_migrations VALUES(?,?)', (SCHEMA, self.now().isoformat()))
            self.bump(c)

    @staticmethod
    def bump(c):
        c.execute('UPDATE system_state SET version=version+1 WHERE id=1')

    def version(self):
        with self.db() as c:
            return c.execute('SELECT version FROM system_state WHERE id=1').fetchone()[0]

    def settings(self, private=False):
        with self.db() as c:
            result = dict(DEFAULTS)
            result.update({r['key']: r['value'] for r in c.execute('SELECT key,value FROM settings')})
        result['pin_enabled'] = bool(result.get('admin_pin_hash'))
        if not private: result.pop('admin_pin_hash', None)
        return result

    def save_settings(self, values):
        cleaned = {}
        for key, value in values.items():
            if key not in DEFAULTS or key == 'admin_pin_hash': continue
            value = str(value).strip()
            if key in ('weather_lat', 'weather_lon'):
                try: number = float(value.replace(',', '.'))
                except ValueError: raise ValueError('Koordinaterna m\u00e5ste vara tal.') from None
                limit = 90 if key == 'weather_lat' else 180
                if not math.isfinite(number) or abs(number) > limit: raise ValueError('Ogiltiga koordinater.')
                value = str(number)
            elif key == 'idle_minutes':
                if not value.isdigit() or not 1 <= int(value) <= 120: raise ValueError('V\u00e4lj 1\u2013120 minuter.')
            elif key in ('night_start', 'night_end'):
                try:
                    if datetime.strptime(value, '%H:%M').strftime('%H:%M') != value: raise ValueError
                except ValueError: raise ValueError('Ange nattider som HH:MM.') from None
            elif key.endswith('_enabled'):
                if value not in ('0', '1'): raise ValueError('Ogiltig inst\u00e4llning.')
            elif len(value) > (240 if key in ('house_note', 'family_goal') else 50):
                raise ValueError('Texten \u00e4r f\u00f6r l\u00e5ng.')
            if key in ('house_name', 'weather_name') and not value: raise ValueError('Namn saknas.')
            cleaned[key] = value
        merged = self.settings() | cleaned
        if merged['night_start'] == merged['night_end']:
            raise ValueError('Nattens start och slut f\u00e5r inte vara samma tid.')
        if values.get('new_pin'):
            pin = values['new_pin']
            if not pin.isdigit() or not 6 <= len(pin) <= 12: raise ValueError('PIN ska ha 6\u201312 siffror.')
            cleaned['admin_pin_hash'] = pin_hash(pin)
        elif values.get('remove_pin') == '1':
            cleaned['admin_pin_hash'] = ''
        with self.db(True) as c:
            for key, value in cleaned.items():
                c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key,value))
            self.bump(c)

    def users(self, active=True):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT * FROM users '+('WHERE active=1 ' if active else '')+'ORDER BY id')]

    def save_user(self, name, accent='sage', share_weight=1, user_id=None):
        name = name.strip()
        try: weight = float(share_weight)
        except (ValueError,TypeError): raise ValueError('Ogiltig arbetsandel.') from None
        if not name or len(name) > 40: raise ValueError('Namn beh\u00f6ver vara 1\u201340 tecken.')
        if accent not in ACCENTS or weight not in (0.5, 1.0, 1.5, 2.0): raise ValueError('Ogiltig profilinst\u00e4llning.')
        with self.db(True) as c:
            if user_id:
                if not c.execute('SELECT 1 FROM users WHERE id=?', (user_id,)).fetchone(): raise LookupError('Profilen finns inte.')
                c.execute('UPDATE users SET name=?,accent=?,share_weight=? WHERE id=?',(name,accent,weight,user_id))
            else:
                user_id = c.execute('INSERT INTO users(name,accent,share_weight) VALUES(?,?,?)',(name,accent,weight)).lastrowid
            self.bump(c)
        self.generate(force=True)
        return user_id

    @staticmethod
    def candidates(c, template):
        allowed = json.loads(template.get('eligible_ids') or '[]')
        return [dict(r) for r in c.execute('SELECT * FROM users WHERE active=1 ORDER BY id') if not allowed or r['id'] in allowed]

    def choose_user(self, c, template, target, exclude_task=None):
        people = self.candidates(c, template)
        if not people: return None
        start = target - timedelta(days=target.weekday())
        end = start + timedelta(days=7)
        previous = c.execute('SELECT user_id FROM tasks WHERE template_id=? AND cancelled=0 AND due_date<? ORDER BY due_date DESC,id DESC LIMIT 1',(template.get('id'),target.isoformat())).fetchone()
        scores = []
        for p in people:
            rows = c.execute('SELECT due_date,difficulty,completed FROM tasks WHERE user_id=? AND cancelled=0 AND id!=? AND due_date<? AND (due_date>=? OR completed=0)',(p['id'],exclude_task or -1,end.isoformat(),start.isoformat())).fetchall()
            weekly = sum(r['difficulty'] for r in rows if r['due_date'] >= start.isoformat() or not r['completed'])
            daily = sum(r['difficulty'] for r in rows if r['due_date'] == target.isoformat())
            # Completed work still counts: finishing quickly must not attract more chores.
            scores.append((weekly / p['share_weight'], daily / p['share_weight'],
                           int(bool(previous and previous['user_id']==p['id'])), p['id']))
        return min(scores)[-1]

    def validate_template(self, values):
        title = str(values.get('title','')).strip()
        notes = str(values.get('notes','')).strip()
        if not title or len(title) > 120 or len(notes) > 600: raise ValueError('Ange en rubrik (max 120 tecken) och en kort beskrivning.')
        try: points = int(values.get('difficulty',3))
        except (ValueError,TypeError): raise ValueError('Po\u00e4ng ska vara 1\u201310.') from None
        if not 1 <= points <= 10: raise ValueError('Po\u00e4ng ska vara 1\u201310.')
        start = iso_date(str(values.get('start_date','')))
        end = str(values.get('end_date','') or '')
        if end and iso_date(end) < start: raise ValueError('Slutdatum ligger f\u00f6re startdatum.')
        recurrence = values.get('recurrence','once')
        mode = values.get('assignment_mode','auto')
        if recurrence not in RECURRENCES or mode not in ('auto','fixed'): raise ValueError('Ogiltigt schema.')
        active_ids = {u['id'] for u in self.users()}
        try:
            fixed = int(values.get('fixed_user_id') or 0) or None
            allowed = sorted({int(v) for v in values.get('eligible_ids',[])})
        except (TypeError,ValueError): raise ValueError('Ogiltigt profilval.') from None
        if not active_ids: raise ValueError('Skapa en profil f\u00f6rst.')
        if not set(allowed).issubset(active_ids): raise ValueError('En vald profil \u00e4r inte aktiv.')
        if mode == 'fixed' and fixed not in active_ids: raise ValueError('V\u00e4lj en aktiv person.')
        return dict(title=title, notes=notes, difficulty=points, recurrence=recurrence, start_date=start.isoformat(),
                    end_date=end or None, weekday=start.weekday(), month_day=start.day,
                    assignment_mode=mode,fixed_user_id=fixed if mode=='fixed' else None,eligible_ids=json.dumps(allowed))

    def save_template(self, values, template_id=None):
        data = self.validate_template(values)
        today = self.now().date()
        with self.db(True) as c:
            if template_id:
                if not c.execute('SELECT 1 FROM task_templates WHERE id=?', (template_id,)).fetchone(): raise LookupError('Schemat finns inte.')
                c.execute('UPDATE task_templates SET '+','.join(k+'=?' for k in data)+' WHERE id=?',(*data.values(),template_id))
                # Preserve completed/history. Reconcile only today/future uncompleted occurrences.
                for row in c.execute('SELECT * FROM tasks WHERE template_id=? AND completed=0 AND due_date>=?',(template_id,today.isoformat())).fetchall():
                    t = data | {'id':template_id}
                    due = iso_date(row['due_date'])
                    cancel = not due_on(t,due)
                    eligible = {p['id'] for p in self.candidates(c,t)}
                    uid = data['fixed_user_id'] if data['assignment_mode']=='fixed' else row['user_id']
                    if data['assignment_mode']=='auto' and uid not in eligible:
                        uid = self.choose_user(c,t,due,row['id'])
                    c.execute('UPDATE tasks SET title=?,notes=?,difficulty=?,assignment_mode=?,user_id=?,cancelled=? WHERE id=?',
                              (data['title'],data['notes'],data['difficulty'],data['assignment_mode'],uid or row['user_id'],int(cancel or not uid),row['id']))
            else:
                template_id = c.execute('INSERT INTO task_templates('+','.join(data)+') VALUES('+','.join('?' for _ in data)+')',tuple(data.values())).lastrowid
            self.bump(c)
        self.generate(force=True)
        return template_id

    def generate(self, force=False):
        today = self.now().date()
        if not force and self.last_schedule_day == today: return
        with self.lock:
            if not force and self.last_schedule_day == today: return
            with self.db(True) as c:
                ts = [dict(r) for r in c.execute("SELECT * FROM task_templates WHERE active=1 ORDER BY CASE assignment_mode WHEN 'fixed' THEN 0 ELSE 1 END,difficulty DESC,id")]
                saved = c.execute("SELECT value FROM settings WHERE key='_last_generation'").fetchone()
                first = max(today-timedelta(days=31), iso_date(saved[0])) if saved else today
                if first > today: first = today
                targets = {first + timedelta(days=n) for n in range((today-first).days+15)}
                for t in ts:
                    if t['recurrence']=='once':
                        try:
                            start = iso_date(t['start_date'])
                            if start <= today+timedelta(days=14): targets.add(start)
                        except ValueError: LOG.warning('Invalid legacy date on template %s; preserved.',t['id'])
                changed=False
                for target in sorted(targets):
                    for t in ts:
                        if target < first and t['recurrence'] != 'once': continue
                        try: scheduled = due_on(t,target)
                        except ValueError:
                            LOG.warning('Invalid legacy schedule %s; preserved for correction.',t['id']); continue
                        if not scheduled: continue
                        if c.execute('SELECT 1 FROM fd_occurrences WHERE template_id=? AND due_date=?',(t['id'],target.isoformat())).fetchone(): continue
                        if t['assignment_mode']=='fixed':
                            uid = t['fixed_user_id']
                            if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(uid,)).fetchone(): continue
                        else: uid = self.choose_user(c,t,target)
                        if not uid: continue
                        values = dict(template_id=t['id'],user_id=uid,title=t['title'],difficulty=t['difficulty'],
                                      due_date=target.isoformat(),notes=t['notes'],created_at=self.now().isoformat(),assignment_mode=t['assignment_mode'])
                        if 'person_id' in self.columns(c,'tasks'): values['person_id']=uid
                        task_id = c.execute('INSERT INTO tasks('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values())).lastrowid
                        c.execute('INSERT INTO fd_occurrences VALUES(?,?,?)',(t['id'],target.isoformat(),task_id))
                        changed=True
                c.execute("INSERT INTO settings(key,value) VALUES('_last_generation',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(today.isoformat(),))
                if changed or not saved or saved[0] != today.isoformat(): self.bump(c)
            self.last_schedule_day=today

    def set_completed(self, task_id, completed: bool):
        if not isinstance(completed,bool): raise ValueError('completed ska vara true eller false.')
        with self.db(True) as c:
            row = c.execute('SELECT t.* FROM tasks t JOIN users u ON u.id=t.user_id WHERE t.id=? AND t.cancelled=0 AND u.active=1',(task_id,)).fetchone()
            if not row: raise LookupError('Uppgiften finns inte l\u00e4ngre.')
            if row['due_date'] > self.now().date().isoformat(): raise ValueError('Uppgiften ligger fram\u00e5t i tiden.')
            changed = bool(row['completed']) != completed
            reward = None
            if changed:
                c.execute('UPDATE tasks SET completed=?,completed_at=? WHERE id=?',(int(completed),self.now().isoformat() if completed else None,task_id))
                enabled = c.execute("SELECT value FROM settings WHERE key='rewards_enabled'").fetchone()[0]=='1'
                if completed and not row['reward_claimed']:
                    c.execute('UPDATE tasks SET reward_claimed=1 WHERE id=?',(task_id,))
                    if enabled:
                        rarity = secrets.choice(['common']*60+['uncommon']*28+['rare']*10+['legendary']*2)
                        badge = dict(secrets.choice([b for b in BADGES if b['rarity']==rarity]))
                        existing = c.execute('SELECT unlock_count FROM user_badges WHERE user_id=? AND badge_id=?',(row['user_id'],badge['id'])).fetchone()
                        count = existing[0]+1 if existing else 1
                        c.execute('INSERT INTO user_badges(user_id,badge_id,unlock_count) VALUES(?,?,1) ON CONFLICT(user_id,badge_id) DO UPDATE SET unlock_count=unlock_count+1,last_unlocked_at=CURRENT_TIMESTAMP',(row['user_id'],badge['id']))
                        c.execute('INSERT INTO fd_reward_events VALUES(?,?,?,?)',(task_id,row['user_id'],badge['id'],self.now().isoformat()))
                        reward = badge | dict(new=not bool(existing),count=count,message=secrets.choice(MESSAGES),points=row['difficulty'])
                self.bump(c)
            version = c.execute('SELECT version FROM system_state WHERE id=1').fetchone()[0]
        return dict(ok=True,completed=completed,changed=changed,reward=reward,version=version,user_id=row['user_id'])

    def archive_user(self, user_id):
        with self.db(True) as c:
            if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(user_id,)).fetchone(): raise LookupError('Profilen finns inte.')
            c.execute('UPDATE users SET active=0 WHERE id=?',(user_id,))
            c.execute("UPDATE task_templates SET active=0 WHERE fixed_user_id=? AND assignment_mode='fixed'",(user_id,))
            rows = c.execute('SELECT * FROM tasks WHERE user_id=? AND completed=0 AND cancelled=0',(user_id,)).fetchall()
            for row in rows:
                t = c.execute('SELECT * FROM task_templates WHERE id=?',(row['template_id'],)).fetchone()
                uid = self.choose_user(c,dict(t),iso_date(row['due_date']),row['id']) if t and row['assignment_mode']=='auto' else None
                if uid: c.execute('UPDATE tasks SET user_id=? WHERE id=?',(uid,row['id']))
                else: c.execute('UPDATE tasks SET cancelled=1 WHERE id=?',(row['id'],))
            self.bump(c)

    def pause_template(self, template_id):
        with self.db(True) as c:
            c.execute('UPDATE task_templates SET active=0 WHERE id=?',(template_id,))
            c.execute('UPDATE tasks SET cancelled=1 WHERE template_id=? AND completed=0',(template_id,))
            self.bump(c)

    def templates(self):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT t.*,u.name AS fixed_user_name FROM task_templates t LEFT JOIN users u ON u.id=t.fixed_user_id WHERE t.active=1 ORDER BY t.id DESC')]

    def dashboard(self):
        today = self.now().date().isoformat()
        with self.db() as c:
            people = [dict(r) for r in c.execute('SELECT * FROM users WHERE active=1 ORDER BY id')]
            tasks = [dict(r) for r in c.execute('SELECT t.* FROM tasks t JOIN users u ON u.id=t.user_id WHERE u.active=1 AND t.cancelled=0 AND t.due_date<=? AND (t.due_date=? OR t.completed=0 OR substr(t.completed_at,1,10)=?) ORDER BY t.due_date,t.id',(today,today,today))]
            for p in people:
                own = [t for t in tasks if t['user_id']==p['id']]
                p.update(self.summarize(own))
                p['next_task'] = next((t['title'] for t in own if not t['completed']),None)
        return dict(users=people,summary=self.summarize(tasks),today=today)

    @staticmethod
    def summarize(tasks):
        total=len(tasks); done=sum(t['completed']==1 for t in tasks)
        total_points=sum(t['difficulty'] for t in tasks)
        done_points=sum(t['difficulty'] for t in tasks if t['completed'])
        return dict(total=total,done=done,left=total-done,total_points=total_points,done_points=done_points,
                    points_left=total_points-done_points,percent=round(100*done_points/total_points) if total_points else 0)

    def profile(self, user_id):
        today = self.now().date().isoformat()
        with self.db() as c:
            p=c.execute('SELECT * FROM users WHERE id=? AND active=1',(user_id,)).fetchone()
            if not p: raise LookupError('Profilen finns inte.')
            rows=[dict(r) for r in c.execute('SELECT * FROM tasks WHERE user_id=? AND cancelled=0 AND (due_date>=? OR completed=0 OR substr(completed_at,1,10)=?) ORDER BY due_date,id',(user_id,today,today))]
            owned=c.execute('SELECT COUNT(*) FROM user_badges WHERE user_id=?',(user_id,)).fetchone()[0]
        pending=[t for t in rows if not t['completed'] and t['due_date']<=today]
        done=[t for t in rows if t['completed'] and (t['due_date']==today or (t['completed_at'] or '')[:10]==today)]
        future=[t for t in rows if t['due_date']>today][:40]
        return dict(person=dict(p),pending=pending,done=done,future=future,summary=self.summarize(pending+done),owned=owned,total_badges=len(BADGES),today=today)

    def collection(self, user_id):
        data=self.profile(user_id)
        with self.db() as c:
            owned={r['badge_id']:dict(r) for r in c.execute('SELECT * FROM user_badges WHERE user_id=?',(user_id,))}
        data['badges']=[b | dict(owned=b['id'] in owned,count=owned.get(b['id'],{}).get('unlock_count',0)) for b in BADGES]
        return data
