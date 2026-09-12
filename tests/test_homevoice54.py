import hashlib
import importlib.util
import io
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from familj.store import Store
from familj.voice54 import VoiceStore,Synthesizer,VoiceError,clean_text,DEFAULT
from familj.remote_access import status_from


def pcm():
    b=io.BytesIO()
    with wave.open(b,'wb') as w:
        w.setparams((1,2,22050,0,'NONE','not compressed'));w.writeframes(b'\0\0'*2205)
    return b.getvalue()

class VoiceCore(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name));self.uid=self.s.save_user('Viktor');self.other=self.s.save_user('Hampus');self.v=VoiceStore(self.s)
        self.s.save_template(dict(title='L\u00e4gg leksakerna i l\u00e5dan',difficulty=2,recurrence='once',start_date=self.s.now().date().isoformat(),assignment_mode='fixed',fixed_user_id=self.uid,eligible_ids=[],notes='B\u00f6rja med bilarna.'))
        with self.s.db() as c:self.tid=c.execute('SELECT id FROM tasks WHERE user_id=? ORDER BY id',(self.uid,)).fetchone()[0]
    def tearDown(self):self.tmp.cleanup()
    def enable(self,**extra):self.v.save(self.uid,dict(enabled='on',notes='on',rewards='on',speed=155,volume=65,**extra))
    def test_disabled_by_default(self):self.assertFalse(self.v.settings(self.uid)['enabled'])
    def test_other_profile_stays_silent(self):self.enable();self.assertFalse(self.v.settings(self.other)['enabled'])
    def test_disabled_audio_forbidden(self):
        with self.assertRaises(VoiceError) as e:self.v.text(self.uid,'task',self.tid)
        self.assertEqual(e.exception.status,403)
    def test_saved_flags(self):self.enable();self.assertTrue(self.v.settings(self.uid)['rewards'])
    def test_notes_read(self):self.enable();self.assertIn('bilarna',self.v.text(self.uid,'task',self.tid)[0])
    def test_notes_disabled(self):
        self.v.save(self.uid,dict(enabled='on',notes='',speed=155,volume=65));self.assertNotIn('bilarna',self.v.text(self.uid,'task',self.tid)[0])
    def test_wrong_owner_rejected(self):
        self.v.save(self.other,dict(enabled='on'))
        with self.assertRaises(LookupError):self.v.text(self.other,'task',self.tid)
    def test_no_arbitrary_kind(self):
        self.enable()
        with self.assertRaises(ValueError):self.v.text(self.uid,'../../etc/passwd',self.tid)
    def test_string_task_id_rejected(self):
        self.enable()
        with self.assertRaises(ValueError):self.v.text(self.uid,'task','1; rm -rf /')
    def test_pending_respects_completion(self):
        self.assertIn(self.tid,self.v.pending(self.uid));self.s.set_completed(self.tid,True);self.assertNotIn(self.tid,self.v.pending(self.uid))
    def test_reward_is_earned(self):
        self.enable()
        with self.assertRaises(ValueError):self.v.text(self.uid,'reward',self.tid)
        self.s.set_completed(self.tid,True);text,_=self.v.text(self.uid,'reward',self.tid);self.assertIn('Bra jobbat',text);self.assertIn('m\u00e4rket',text)
    def test_reward_option_off(self):
        self.v.save(self.uid,dict(enabled='on'));self.s.set_completed(self.tid,True)
        with self.assertRaises(VoiceError):self.v.text(self.uid,'reward',self.tid)
    def test_archived_profile_rejected(self):
        self.s.archive_user(self.uid)
        with self.assertRaises(LookupError):self.v.settings(self.uid)
    def test_invalid_speed_rejected(self):
        for value in [-1,0,999,'a']:
            with self.subTest(value=value),self.assertRaises(ValueError):self.v.save(self.uid,dict(enabled='on',speed=value))
    def test_invalid_volume_rejected(self):
        for value in [-1,101,'a']:
            with self.subTest(value=value),self.assertRaises(ValueError):self.v.save(self.uid,dict(volume=value))
    def test_migration_preserves_tasks(self):
        with self.s.db() as c:before=[tuple(r) for r in c.execute('SELECT * FROM tasks')]
        VoiceStore(self.s)
        with self.s.db() as c:after=[tuple(r) for r in c.execute('SELECT * FROM tasks')]
        self.assertEqual(before,after)
    def test_backup_made(self):self.assertTrue(list((self.s.data/'backups').glob('*voice54*')))
    def test_migration_is_idempotent(self):
        count=len(list((self.s.data/'backups').glob('*voice54*')));VoiceStore(self.s);self.assertEqual(count,len(list((self.s.data/'backups').glob('*voice54*'))))
    def test_restart_persists_settings(self):self.enable();self.assertTrue(VoiceStore(Store(self.s.root)).settings(self.uid)['enabled'])
    def test_version_bumped_on_settings(self):old=self.s.version();self.enable();self.assertGreater(self.s.version(),old)
    def test_invalid_does_not_modify(self):
        before=self.v.settings(self.uid)
        with self.assertRaises(ValueError):self.v.save(self.uid,dict(speed='not speed',volume=25))
        self.assertEqual(before,self.v.settings(self.uid))
    def test_no_extra_reward_for_tts(self):
        self.enable();self.s.set_completed(self.tid,True)
        with self.s.db() as c:before=[tuple(r) for r in c.execute('SELECT * FROM user_badges')]
        self.v.text(self.uid,'reward',self.tid);self.v.text(self.uid,'reward',self.tid)
        with self.s.db() as c:after=[tuple(r) for r in c.execute('SELECT * FROM user_badges')]
        self.assertEqual(before,after)

class SynthesisTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.s=Synthesizer(Path(self.tmp.name))
    def tearDown(self):self.tmp.cleanup()
    def test_sanitizes_and_limits_text(self):self.assertNotIn('\x00',clean_text('a\x00b'));self.assertLessEqual(len(clean_text('x'*5000)),1800)
    def test_invalid_wav_rejected(self):
        with self.assertRaises(VoiceError):self.s.verify(b'not audio')
    def test_valid_wav_accepted(self):self.s.verify(pcm())
    def test_engine_missing(self):
        with patch('familj.voice54.shutil.which',return_value=None):
            self.assertFalse(self.s.status()['ready'])
            with self.assertRaises(VoiceError):self.s.synthesize(1,'Hej',155)
    def test_busy_returns_instead_of_blocking(self):
        self.s.gate.acquire()
        try:
            with patch.object(self.s,'status',return_value=dict(ready=True,binary='/mock/espeak')):
                with self.assertRaises(VoiceError) as e:self.s.synthesize(1,'Hej',155)
                self.assertEqual(e.exception.status,429)
        finally:self.s.gate.release()
    def test_cache_reused_and_command_not_shell(self):
        calls=[]
        def run(args,**kw):
            calls.append((args,kw));Path(args[args.index('-w')+1]).write_bytes(pcm());return subprocess.CompletedProcess(args,0)
        with patch.object(self.s,'status',return_value=dict(ready=True,binary='/mock/espeak')),patch('familj.voice54.subprocess.run',side_effect=run):
            a=self.s.synthesize(1,'Hej; $(evil)',155);b=self.s.synthesize(1,'Hej; $(evil)',155)
        self.assertEqual(a,b);self.assertEqual(len(calls),1);self.assertNotIn('shell',calls[0][1]);self.assertIn(b'$(evil)',calls[0][1]['input']);self.assertNotIn('$(evil)',calls[0][0])
    def test_cache_count_bounded(self):
        self.s.cache.mkdir()
        for i in range(125):(self.s.cache/f'{i}.wav').write_bytes(pcm())
        self.s.prune();self.assertLessEqual(len(list(self.s.cache.glob('*.wav'))),120)
    def test_timeout_releases_lock(self):
        with patch.object(self.s,'status',return_value=dict(ready=True,binary='/mock/espeak')),patch('familj.voice54.subprocess.run',side_effect=subprocess.TimeoutExpired('espeak',20)):
            with self.assertRaises(VoiceError):self.s.synthesize(1,'Hej',155)
        self.assertTrue(self.s.gate.acquire(False));self.s.gate.release()
    @unittest.skipUnless(shutil.which('espeak-ng') or shutil.which('espeak'),'No local TTS engine')
    def test_real_swedish_wav(self):
        data=self.s.synthesize(1,'Hej! Nu l\u00e4ser jag dina uppgifter.',155);self.s.verify(data);self.assertGreater(len(data),1000)

class MobileURLTests(unittest.TestCase):
    def test_only_verified_actual_address(self):
        host='familj.example.ts.net';ts=dict(BackendState='Running',Self=dict(DNSName=host+'.'));config={'TCP':{'443':{'HTTPS':True}},'Web':{host+':443':{'Handlers':{'/':{'Proxy':'http://127.0.0.1:5000'}}}}}
        d=status_from(ts,config,{},True);self.assertEqual(d['url'],'https://familj.example.ts.net/admin')
    def test_unknown_never_invents_url(self):self.assertIsNone(status_from(None,None,{},True)['url'])
    def test_funnel_not_accepted(self):self.assertIsNone(status_from(dict(BackendState='Running'),{'AllowFunnel':{'a':True}},{},True)['url'])

class PatchTests(unittest.TestCase):
    def test_patch_idempotent_and_touch_unchanged(self):
        spec=importlib.util.spec_from_file_location('apply54',ROOT/'scripts/apply_home_voice.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        before={p.name:p.read_bytes() for p in (ROOT/'static').glob('touch-*')}
        raw,out,_=m.transforms(ROOT)
        self.assertEqual(out['app.py'].count('# FAMILJ_HOMEVOICE_5_4'),1)
        self.assertEqual(raw['templates/base.html'].decode(),out['templates/base.html'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in (ROOT/'static').glob('touch-*')})

if __name__=='__main__':unittest.main()
