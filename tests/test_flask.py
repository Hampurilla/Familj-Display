import importlib.util
import tempfile
import unittest
from pathlib import Path

@unittest.skipUnless(importlib.util.find_spec('flask'),'Flask is not installed in this environment')
class FlaskTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp=tempfile.TemporaryDirectory();self.app=create_app(Path(self.tmp.name),start_workers=False,testing=True)
        self.c=self.app.test_client();self.s=self.app.extensions['store']
        self.c.get('/')
        with self.c.session_transaction() as session:self.csrf=session['_csrf']
    def tearDown(self):self.tmp.cleanup()
    def test_pages(self):
        for p in ('/','/admin','/admin?tab=tasks','/admin?tab=people','/admin?tab=settings','/health','/api/state','/api/weather','/admin/login'):
            with self.subTest(p=p):self.assertEqual(self.c.get(p).status_code,200)
    def test_create_profile_and_task(self):
        r=self.c.post('/admin/user/add',data={'name':'Test','accent':'sage','share_weight':'1','_csrf':self.csrf})
        self.assertEqual(r.status_code,303)
        r=self.c.post('/admin/template/add',data={'title':'Test task','difficulty':'3','start_date':self.s.now().date().isoformat(),'recurrence':'once','assignment_mode':'auto','_csrf':self.csrf})
        self.assertEqual(r.status_code,303)
        self.assertEqual(self.c.get('/user/1').status_code,200);self.assertEqual(self.c.get('/user/1/badges').status_code,200)
    def test_csrf_rejects_untrusted_posts(self):
        self.assertEqual(self.c.post('/admin/user/add',data={'name':'Bad'}).status_code,403)
    def test_idempotent_complete(self):
        uid=self.s.save_user('Test');self.s.save_template(dict(title='Test',start_date=self.s.now().date().isoformat(),difficulty=2,recurrence='once',assignment_mode='auto',eligible_ids=[]))
        with self.s.db() as c:tid=c.execute('SELECT id FROM tasks').fetchone()[0]
        for i in range(2):
            r=self.c.post(f'/api/tasks/{tid}/complete',json={'completed':True},headers={'X-CSRF-Token':self.csrf})
            self.assertEqual(r.status_code,200)
            if i:self.assertIsNone(r.json['reward'])
    def test_no_api_cache(self):
        self.assertEqual(self.c.get('/api/state').headers['Cache-Control'],'no-store')
    def test_admin_pin(self):
        self.s.save_settings({'new_pin':'123456'})
        self.assertEqual(self.c.get('/admin').status_code,302)
        self.assertEqual(self.c.post('/admin/login',data={'pin':'123456','_csrf':self.csrf}).status_code,303)
        self.assertEqual(self.c.get('/admin').status_code,200)
    def test_xss_escaped(self):
        self.s.save_user('<script>alert(1)</script>')
        text=self.c.get('/').text
        self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>alert(1)</script>',text)
    def test_invalid_input_shows_error_not_500(self):
        self.s.save_user('Test')
        r=self.c.post('/admin/template/add',data={'_csrf':self.csrf,'title':'Thing','start_date':'invalid'})
        self.assertEqual(r.status_code,400)
    def test_backup(self):
        r=self.c.post('/admin/backup',data={'_csrf':self.csrf})
        self.assertEqual(r.status_code,200);self.assertTrue(r.data.startswith(b'SQLite format 3'))
