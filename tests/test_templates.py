import tempfile
import unittest
from pathlib import Path
from jinja2 import TemplateError
from familj.store import Store
from render_support import seed,environment,context,NOW

class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name),now=lambda:NOW)
        self.ids=seed(self.s);self.env=environment(self.s)
    def tearDown(self):self.tmp.cleanup()
    def test_full_pages_strict_undefined(self):
        for view in ['home','user','badges','login','error']:
            with self.subTest(view=view):
                result=self.env.get_template(view+'.html').render(**context(self.s,view,self.ids[0]))
                self.assertIn('<!doctype html>',result.lower());self.assertIn('style.css?v=preview',result)
    def test_admin_tabs(self):
        for tab in ['overview','people','tasks','settings']:
            with self.subTest(tab=tab):self.assertIn('Kontrollpanel',self.env.get_template('admin.html').render(**context(self.s,'admin',tab=tab)))
    def test_empty_state_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(Path(tmp),now=lambda:NOW);env=environment(s)
            self.assertIn('Skapa',env.get_template('home.html').render(**context(s,'home')))
            for tab in ['overview','people','tasks','settings']:
                env.get_template('admin.html').render(**context(s,'admin',tab=tab))
    def test_partials_have_no_duplicate_document(self):
        for view in ['home','user','badges']:
            text=self.env.get_template('partials/'+view+'_content.html').render(**context(self.s,view,self.ids[0]))
            self.assertNotIn('<html',text)
    def test_escapes_profile_and_note(self):
        uid=self.s.save_user('<b>Person</b>')
        self.s.save_settings({'house_note':'<script>bad()</script>'})
        env=environment(self.s)
        text=env.get_template('home.html').render(**context(self.s,'home'))
        self.assertIn('&lt;b&gt;',text);self.assertNotIn('<script>bad()',text)
    def test_references_screensaver_on_display_only(self):
        a=self.env.get_template('home.html').render(**context(self.s,'home'))
        b=self.env.get_template('admin.html').render(**context(self.s,'admin'))
        self.assertIn('id="screensaver"',a);self.assertNotIn('id="screensaver"',b)
    def test_edit_template(self):
        data=context(self.s,'admin',tab='tasks');edit=self.s.templates()[0];data['edit']=edit;data['form'].update(edit);data['form']['allowed']=[]
        text=self.env.get_template('admin.html').render(**data)
        self.assertIn('/admin/template/'+str(edit['id'])+'/edit',text)
