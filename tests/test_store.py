"""Run with python -m unittest discover -s tests -v. No network calls."""
import json
from contextlib import closing
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,date,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from familj.store import Store,due_on,pin_hash,pin_matches
from familj.badges import BADGES

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.clock=datetime(2026,9,9,18,30,tzinfo=ZoneInfo('Europe/Stockholm'))
        self.s=Store(self.root,now=lambda:self.clock)
    def tearDown(self):self.tmp.cleanup()
    def user(self,name='Anna',weight=1):return self.s.save_user(name,'sage',weight)
    def template(self,**kwargs):
        data=dict(title='Plocka undan',notes='',difficulty=3,start_date='2026-09-09',end_date='',recurrence='once',assignment_mode='auto',eligible_ids=[])
        data.update(kwargs);return self.s.save_template(data)
    def tasks(self):
        with self.s.db() as c:return [dict(r) for r in c.execute('SELECT * FROM tasks ORDER BY due_date,id')]
    def test_fresh_database(self):
        self.assertEqual(self.s.users(),[]);self.assertEqual(len(BADGES),144);self.assertEqual(len({b['emoji'] for b in BADGES}),144)
    def test_daily_generation_is_idempotent(self):
        self.user();self.template(recurrence='daily')
        count=len(self.tasks());self.assertEqual(count,15)
        for _ in range(4):self.s.generate(force=True)
        self.assertEqual(len(self.tasks()),count)
    def test_month_end_no_drift(self):
        t=dict(start_date='2026-01-31',end_date=None,recurrence='monthly',month_day=31)
        self.assertTrue(due_on(t,date(2026,2,28)));self.assertTrue(due_on(t,date(2026,3,31)))
        self.assertFalse(due_on(t,date(2026,3,28)))
        t['start_date']='2028-01-31';self.assertTrue(due_on(t,date(2028,2,29)))
    def test_biweekly_calendar_anchor(self):
        t=dict(start_date='2026-10-18',end_date=None,recurrence='biweekly')
        self.assertTrue(due_on(t,date(2026,11,1)));self.assertFalse(due_on(t,date(2026,10,25)))
    def test_weekly_date(self):
        t=dict(start_date='2026-09-09',end_date=None,recurrence='weekly')
        self.assertTrue(due_on(t,date(2026,9,16)));self.assertFalse(due_on(t,date(2026,9,17)))
    def test_end_date(self):
        t=dict(start_date='2026-09-09',end_date='2026-09-11',recurrence='daily')
        self.assertTrue(due_on(t,date(2026,9,11)));self.assertFalse(due_on(t,date(2026,9,12)))
    def test_invalid_dates_and_points(self):
        self.user()
        for kw in [dict(start_date='2026-02-30'),dict(difficulty=0),dict(difficulty=100),dict(title=''),dict(assignment_mode='unknown')]:
            with self.assertRaises(ValueError):self.template(**kw)
        self.assertEqual(self.tasks(),[])
    def test_user_validation(self):
        for name,w in [('',1),('a'*41,1),('OK',float('nan')),('OK',99)]:
            with self.assertRaises(ValueError):self.s.save_user(name,'sage',w)
    def test_future_cannot_be_completed(self):
        self.user();self.template(start_date='2026-09-10')
        with self.assertRaises(ValueError):self.s.set_completed(self.tasks()[0]['id'],True)
    def test_complete_is_idempotent(self):
        self.user();self.template();tid=self.tasks()[0]['id']
        a=self.s.set_completed(tid,True);b=self.s.set_completed(tid,True)
        self.assertTrue(a['changed']);self.assertFalse(b['changed']);self.assertIsNone(b['reward'])
        with self.s.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM fd_reward_events').fetchone()[0],1)
    def test_undo_does_not_farm_rewards(self):
        self.user();self.template();tid=self.tasks()[0]['id']
        self.s.set_completed(tid,True);self.s.set_completed(tid,False)
        self.assertIsNone(self.s.set_completed(tid,True)['reward'])
        with self.s.db() as c:self.assertEqual(c.execute('SELECT SUM(unlock_count) FROM user_badges').fetchone()[0],1)
    def test_concurrent_completions_one_reward(self):
        self.user();self.template();tid=self.tasks()[0]['id']
        with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(lambda _:self.s.set_completed(tid,True),range(12)))
        self.assertEqual(sum(r['changed'] for r in results),1)
        with self.s.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM fd_reward_events').fetchone()[0],1)
    def test_completed_work_counts_for_fairness(self):
        a=self.user('A');b=self.user('B')
        self.template(assignment_mode='fixed',fixed_user_id=a,difficulty=8)
        self.s.set_completed(self.tasks()[0]['id'],True)
        self.template(difficulty=4)
        self.assertEqual(self.tasks()[-1]['user_id'],b)
    def test_allowed_people(self):
        a=self.user('A');b=self.user('B');self.template(eligible_ids=[b])
        self.assertEqual(self.tasks()[0]['user_id'],b)
    def test_share_weights(self):
        a=self.user('A',1);b=self.user('B',0.5)
        for i in range(12):self.template(title=str(i),difficulty=1)
        ta=sum(t['user_id']==a for t in self.tasks());tb=sum(t['user_id']==b for t in self.tasks())
        self.assertEqual((ta,tb),(8,4))
    def test_pause_preserves_history(self):
        self.user();tid=self.template(recurrence='daily');first=self.tasks()[0]['id']
        self.s.set_completed(first,True);self.s.pause_template(tid)
        self.assertEqual(len(self.tasks()),15)
        self.assertEqual(sum(t['cancelled'] for t in self.tasks()),14)
        self.assertEqual(self.tasks()[0]['completed'],1)
    def test_edit_does_not_rewrite_completed(self):
        self.user();template_id=self.template(recurrence='daily');first=self.tasks()[0]['id']
        self.s.set_completed(first,True)
        self.s.save_template(dict(title='Nytt',notes='Tips',difficulty=5,start_date='2026-09-09',recurrence='daily',assignment_mode='auto',eligible_ids=[]),template_id)
        self.assertEqual(self.tasks()[0]['title'],'Plocka undan');self.assertEqual(self.tasks()[1]['title'],'Nytt')
    def test_archive_reassigns_auto_work(self):
        a=self.user('A');b=self.user('B');self.template()
        old=self.tasks()[0]['user_id'];other=b if old==a else a
        self.s.archive_user(old)
        self.assertEqual(self.tasks()[0]['user_id'],other);self.assertEqual(self.tasks()[0]['cancelled'],0)
    def test_archive_fixed_work_pauses(self):
        a=self.user();tid=self.template(assignment_mode='fixed',fixed_user_id=a)
        self.s.archive_user(a);self.assertEqual(self.tasks()[0]['cancelled'],1);self.assertEqual(self.s.templates(),[])
    def test_midnight_scheduler(self):
        self.user();self.template(recurrence='daily');self.clock+=timedelta(days=1)
        self.s.generate();self.assertEqual(len(self.tasks()),16);self.assertEqual(self.s.dashboard()['today'],'2026-09-10')
    def test_history_not_counted_forever(self):
        self.user();self.template();self.s.set_completed(self.tasks()[0]['id'],True)
        self.clock+=timedelta(days=1)
        self.assertEqual(self.s.dashboard()['summary']['total'],0)
    def test_unfinished_overdue_visible(self):
        uid=self.user();self.template();self.clock+=timedelta(days=1)
        self.assertEqual(self.s.profile(uid)['summary']['left'],1)
    def test_overdue_completed_today_counts_today(self):
        uid=self.user();self.template();tid=self.tasks()[0]['id'];self.clock+=timedelta(days=1)
        self.s.set_completed(tid,True)
        self.assertEqual(self.s.profile(uid)['summary']['done'],1)
        self.assertEqual(self.s.dashboard()['summary']['done_points'],3)
        self.clock+=timedelta(days=1)
        self.assertEqual(self.s.dashboard()['summary']['done'],0)
    def test_partial_settings_preserve_night(self):
        self.s.save_settings({'night_start':'23:45'});self.s.save_settings({'house_note':'Hej'})
        self.assertEqual(self.s.settings()['night_start'],'23:45')
    def test_invalid_settings_rejected(self):
        for values in ({'idle_minutes':'0'},{'night_start':'99:99'},{'weather_lat':'nan'},{'weather_lon':'181'},{'night_start':'07:00','night_end':'07:00'}):
            with self.assertRaises(ValueError):self.s.save_settings(values)
    def test_pin_hash_not_public(self):
        self.s.save_settings({'new_pin':'123456'})
        s=self.s.settings();self.assertTrue(s['pin_enabled']);self.assertNotIn('admin_pin_hash',s)
        private=self.s.settings(True)['admin_pin_hash'];self.assertTrue(pin_matches('123456',private));self.assertFalse(pin_matches('654321',private))
    def test_backup_contains_committed_data(self):
        self.user('Test');dest=self.s.backup()
        with closing(sqlite3.connect(dest)) as c:self.assertEqual(c.execute('SELECT name FROM users').fetchone()[0],'Test')
    def test_reopen_preserves_data_and_badges(self):
        uid=self.user();self.template();self.s.set_completed(self.tasks()[0]['id'],True)
        old_count=self.s.collection(uid)['owned'];s2=Store(self.root,now=lambda:self.clock)
        self.assertEqual(s2.collection(uid)['owned'],old_count);self.assertEqual(s2.profile(uid)['summary']['done'],1)
    def test_root_legacy_people_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'home_display.db'
            with closing(sqlite3.connect(path)) as c:
                c.executescript('CREATE TABLE people(id INTEGER PRIMARY KEY,name TEXT NOT NULL); CREATE TABLE tasks(id INTEGER PRIMARY KEY,person_id INTEGER NOT NULL,title TEXT NOT NULL,completed INTEGER NOT NULL DEFAULT 0); INSERT INTO people VALUES(7,"Anna"); INSERT INTO tasks VALUES(19,7,"Old task",1);')
            original=path.read_bytes();s=Store(root,now=lambda:self.clock)
            self.assertEqual(s.users()[0]['id'],7)
            with s.db() as c:
                row=c.execute('SELECT * FROM tasks WHERE id=19').fetchone();self.assertEqual(row['user_id'],7);self.assertEqual(row['completed'],1)
            self.assertEqual(path.read_bytes(),original)
            self.assertTrue(list((root/'data/backups').glob('*.sqlite3')))
            s.save_template(dict(title='New',difficulty=2,start_date='2026-09-09',recurrence='once',assignment_mode='fixed',fixed_user_id=7,eligible_ids=[]))
            with s.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],2)
    def test_bad_database_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir();p=root/'data/home_display.db';p.write_bytes(b'not a database')
            with self.assertRaises(sqlite3.DatabaseError):Store(root)
            self.assertEqual(p.read_bytes(),b'not a database')
