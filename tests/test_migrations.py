"""Migration fixtures are taken from the original delivered v1/v2/v3 sources."""
from contextlib import closing
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sqlite3,tempfile,unittest
from familj.store import Store
FIXTURES=Path(__file__).parent/'fixtures'
NOW=datetime(2026,9,9,18,30,tzinfo=ZoneInfo('Europe/Stockholm'))

class MigrationTests(unittest.TestCase):
    def migrate_fixture(self,version):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir();db=root/'data/home_display.db'
            with closing(sqlite3.connect(db)) as c:
                c.executescript((FIXTURES/f'legacy_v{version}.sql').read_text())
                c.execute('INSERT INTO users(id,name,active) VALUES(11,?,1)',('Existing name',))
                c.execute("INSERT INTO task_templates(id,title,start_date,recurrence,assignment_mode,fixed_user_id,notes) VALUES(24,'Keep schedule','2026-09-09','daily','fixed',11,'Keep notes')")
                c.execute("INSERT INTO tasks(id,template_id,user_id,title,difficulty,due_date,completed,completed_at) VALUES(51,24,11,'Keep finished',4,'2026-09-09',1,'2026-09-09T17:00:00')")
                c.execute("INSERT INTO tasks(id,template_id,user_id,title,difficulty,due_date,completed) VALUES(52,24,11,'Keep pending',2,'2026-09-10',0)")
                if version>1:
                    c.execute("INSERT INTO settings(key,value) VALUES('night_start','23:20') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
                c.commit()
            s=Store(root,now=lambda:NOW)
            s.generate(force=True)
            with s.db() as c:
                self.assertEqual(c.execute('SELECT name FROM users WHERE id=11').fetchone()[0],'Existing name')
                old=c.execute('SELECT * FROM tasks WHERE id=51').fetchone()
                self.assertEqual((old['title'],old['completed'],old['difficulty'],old['completed_at']),('Keep finished',1,4,'2026-09-09T17:00:00'))
                self.assertEqual(c.execute('SELECT title FROM tasks WHERE id=52').fetchone()[0],'Keep pending')
                self.assertEqual(c.execute("SELECT COUNT(*) FROM tasks WHERE template_id=24 AND due_date='2026-09-09'").fetchone()[0],1)
                self.assertEqual(c.execute('SELECT notes FROM task_templates WHERE id=24').fetchone()[0],'Keep notes')
            if version>1:self.assertEqual(s.settings()['night_start'],'23:20')
            self.assertTrue(list((root/'data/backups').glob('*before-v5.sqlite3')))
            # Reopening or undoing an old completion must not fabricate a retroactive badge.
            s.set_completed(51,False);self.assertIsNone(s.set_completed(51,True)['reward'])
            self.assertEqual(s.collection(11)['owned'],0)
    def test_v1_existing_users_tasks(self):self.migrate_fixture(1)
    def test_v2_existing_users_tasks_settings(self):self.migrate_fixture(2)
    def test_v3_existing_users_tasks_night_settings(self):self.migrate_fixture(3)
    def test_existing_collection_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            with closing(sqlite3.connect(root/'data/home_display.db')) as c:
                c.executescript((FIXTURES/'legacy_v3.sql').read_text())
                c.execute("INSERT INTO users(id,name,active) VALUES(1,'Old',1)")
                c.execute('CREATE TABLE user_badges(user_id INTEGER,badge_id INTEGER,unlock_count INTEGER,first_unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,last_unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,badge_id))')
                c.execute('INSERT INTO user_badges(user_id,badge_id,unlock_count) VALUES(1,1,3)');c.commit()
            s=Store(root,now=lambda:NOW);data=s.collection(1)
            self.assertEqual(data['owned'],1)
            self.assertEqual(next(b for b in data['badges'] if b['id']==1)['count'],3)
    def test_newer_schema_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);s=Store(root,now=lambda:NOW)
            with s.db(True) as c:c.execute("INSERT INTO fd_migrations VALUES(99,'2099')")
            with self.assertRaises(RuntimeError):Store(root,now=lambda:NOW)
