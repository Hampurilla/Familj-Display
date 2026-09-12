import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

@unittest.skipUnless(importlib.util.find_spec('flask'),'Flask unavailable in this test environment')
class VoiceFlask(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp=tempfile.TemporaryDirectory();self.app=create_app(Path(self.tmp.name),start_workers=False,testing=True);self.c=self.app.test_client();self.store=self.app.extensions['store'];self.voice=self.app.extensions['familj_voice54']['store'];self.uid=self.store.save_user('Viktor')
        self.c.get('/')
        with self.c.session_transaction() as s:self.csrf=s['_csrf']
    def tearDown(self):self.tmp.cleanup()
    def test_new_pages(self):
        for p in ['/admin/speech','/admin/mobile','/mobile.webmanifest']:
            with self.subTest(p=p):self.assertEqual(self.c.get(p).status_code,200)
    def test_manifest_same_origin_admin(self):
        data=self.c.get('/mobile.webmanifest').json;self.assertEqual(data['start_url'],'/admin');self.assertEqual(data['scope'],'/admin')
    def test_voice_admin_pin_guard(self):
        self.store.save_settings({'new_pin':'123456'})
        self.assertEqual(self.c.get('/admin/speech').status_code,302);self.assertEqual(self.c.get('/admin/mobile').status_code,302)
    def test_csrf_guard(self):self.assertEqual(self.c.post(f'/api/voice/profile/{self.uid}/audio',json={'kind':'sample'}).status_code,403)
    def test_save_and_read_profile(self):
        r=self.c.post(f'/admin/speech/{self.uid}',data={'_csrf':self.csrf,'enabled':'on','speed':155,'volume':65});self.assertEqual(r.status_code,303);self.assertTrue(self.c.get(f'/api/voice/profile/{self.uid}').json['settings']['enabled'])
    def test_disabled_audio_rejected(self):self.assertEqual(self.c.post(f'/api/voice/profile/{self.uid}/audio',json={'kind':'sample'},headers={'X-CSRF-Token':self.csrf}).status_code,403)
    def test_valid_audio(self):
        from test_homevoice54 import pcm
        self.voice.save(self.uid,{'enabled':'on'})
        with patch.object(self.app.extensions['familj_voice54']['synth'],'synthesize',return_value=pcm()):r=self.c.post(f'/api/voice/profile/{self.uid}/audio',json={'kind':'sample'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,200);self.assertEqual(r.mimetype,'audio/wav');self.assertEqual(r.headers['Cache-Control'],'no-store')
    def test_health_extension_version(self):self.assertEqual(self.c.get('/health').json['homevoice_version'],'5.4.0')
    def test_invalid_setting_not_500(self):self.assertEqual(self.c.post(f'/admin/speech/{self.uid}',data={'_csrf':self.csrf,'speed':'abc'}).status_code,400)
