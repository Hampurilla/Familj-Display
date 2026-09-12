"""Local Swedish TTS. Generates WAV only; the requesting browser plays it.

No arbitrary text/commands/paths accepted from HTTP. No cloud TTS, audio device
control, shell invocation or startup changes. Missing TTS never breaks tasks.
"""
from __future__ import annotations
import hashlib
import io
import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import unicodedata
import wave
from pathlib import Path
from familj.badges import BADGES

VERSION = '5.4.0'
DEFAULT = dict(enabled=False, rewards=False, notes=True, speed=155, volume=65)
MAX_TEXT = 1800
BADGE_MAP = {b['id']: b for b in BADGES}
LOG = logging.getLogger(__name__)

class VoiceError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def clean_text(text):
    # Remove control/markup characters. Text goes to stdin, never an argument.
    value = ''.join(c for c in str(text) if c in '\n\t' or not unicodedata.category(c).startswith('C'))
    return ' '.join(value.replace('<', ' ').replace('>', ' ').split())[:MAX_TEXT]


class VoiceStore:
    def __init__(self, store):
        self.store = store
        with store.db() as c:
            exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='fd_voice_profiles'").fetchone()
        if not exists:
            store.backup('before-voice54')
            with store.db(True) as c:
                c.execute('''CREATE TABLE IF NOT EXISTS fd_voice_profiles(
                    user_id INTEGER PRIMARY KEY REFERENCES users(id),
                    enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
                    rewards INTEGER NOT NULL DEFAULT 0 CHECK(rewards IN (0,1)),
                    notes INTEGER NOT NULL DEFAULT 1 CHECK(notes IN (0,1)),
                    speed INTEGER NOT NULL DEFAULT 155 CHECK(speed BETWEEN 110 AND 210),
                    volume INTEGER NOT NULL DEFAULT 65 CHECK(volume BETWEEN 0 AND 100))''')

    def settings(self, uid):
        with self.store.db() as c:
            u = c.execute('SELECT id,name FROM users WHERE id=? AND active=1', (uid,)).fetchone()
            if not u:
                raise LookupError('Profilen finns inte l\u00e4ngre.')
            r = c.execute('SELECT * FROM fd_voice_profiles WHERE user_id=?', (uid,)).fetchone()
        result = dict(DEFAULT)
        if r:
            result.update({k: bool(r[k]) if k in ('enabled','rewards','notes') else r[k] for k in DEFAULT})
        return dict(result, user_id=uid, name=u['name'])

    def save(self, uid, values):
        self.settings(uid)
        try:
            speed, volume = int(values.get('speed',155)), int(values.get('volume',65))
        except (ValueError, TypeError):
            raise ValueError('Tempo och volym m\u00e5ste vara tal.') from None
        if not 110 <= speed <= 210 or not 0 <= volume <= 100:
            raise ValueError('Tempo ska vara 110\u2013210 och volym 0\u2013100.')
        enabled, rewards, notes = [int(values.get(k) in (True,'1','on')) for k in ('enabled','rewards','notes')]
        with self.store.db(True) as c:
            c.execute('''INSERT INTO fd_voice_profiles(user_id,enabled,rewards,notes,speed,volume)
                VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                enabled=excluded.enabled,rewards=excluded.rewards,notes=excluded.notes,
                speed=excluded.speed,volume=excluded.volume''', (uid,enabled,rewards,notes,speed,volume))
            self.store.bump(c)

    def pending(self, uid):
        self.settings(uid)
        with self.store.db() as c:
            return [r[0] for r in c.execute('''SELECT id FROM tasks WHERE user_id=? AND cancelled=0
                AND completed=0 AND due_date<=? ORDER BY due_date,id''',
                (uid,self.store.now().date().isoformat()))]

    def text(self, uid, kind, tid=None):
        config = self.settings(uid)
        if not config['enabled']:
            raise VoiceError('Uppl\u00e4sning \u00e4r inte aktiverad f\u00f6r den h\u00e4r profilen.',403)
        if kind == 'sample':
            return 'Hej! Nu kan jag l\u00e4sa dina uppgifter. Vi tar en sak i taget.', config
        if kind not in ('task','reward') or type(tid) is not int or tid < 1:
            raise ValueError('Ogiltig uppl\u00e4sning.')
        with self.store.db() as c:
            task = c.execute('SELECT * FROM tasks WHERE id=? AND user_id=? AND cancelled=0', (tid,uid)).fetchone()
            if not task:
                raise LookupError('Uppgiften finns inte p\u00e5 den h\u00e4r profilen.')
            if kind == 'task':
                text = task['title'] + '.'
                if config['notes'] and task['notes']:
                    text += ' ' + task['notes']
            else:
                if not config['rewards']:
                    raise VoiceError('Uppl\u00e4sning av bel\u00f6ningar \u00e4r avst\u00e4ngd.',403)
                reward = c.execute('SELECT badge_id FROM fd_reward_events WHERE task_id=? AND user_id=?',(tid,uid)).fetchone()
                if not task['completed'] or not reward:
                    raise ValueError('Det finns ingen avklarad bel\u00f6ning att l\u00e4sa.')
                badge = BADGE_MAP.get(reward['badge_id'])
                text = 'Bra jobbat! Du klarade ' + task['title'] + '.'
                if badge:
                    text += ' Du fick m\u00e4rket ' + badge['name'] + '.'
        return clean_text(text), config


class Synthesizer:
    """One local synth at a time; bounded cache. No browser task is executed here."""
    def __init__(self, data):
        self.cache = Path(data)/'voice-cache'
        self.gate = threading.Lock()
        self.probe_lock = threading.Lock()
        self.probe_at = -1000
        self.probe_value = None

    def status(self):
        with self.probe_lock:
            if self.probe_value is not None and time.monotonic()-self.probe_at < 20:
                return dict(self.probe_value)
            binary = shutil.which('espeak-ng') or shutil.which('espeak')
            ok = False
            if binary:
                try:
                    p = subprocess.run([binary,'--voices=sv'],capture_output=True,text=True,timeout=3,check=False)
                    ok = p.returncode == 0 and any('sv' in line.split() for line in p.stdout.splitlines()[1:])
                except (OSError, subprocess.TimeoutExpired):
                    pass
            self.probe_value = dict(ready=ok,engine='eSpeak NG' if binary and Path(binary).name=='espeak-ng' else 'eSpeak' if binary else None,
                binary=binary if ok else None,
                message='Svensk lokal r\u00f6st \u00e4r klar.' if ok else 'Installera r\u00f6sten p\u00e5 Pi:n: python3 scripts/setup_home_voice.py voice')
            self.probe_at = time.monotonic()
            return dict(self.probe_value)

    @staticmethod
    def verify(data):
        try:
            with wave.open(io.BytesIO(data),'rb') as w:
                if w.getnframes() < 1 or w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getnframes()/w.getframerate()>180:
                    raise ValueError('audio shape')
        except (wave.Error,EOFError,ValueError,ZeroDivisionError):
            raise VoiceError('R\u00f6sten gav en ogiltig ljudfil.') from None

    def synthesize(self, uid, text, speed):
        info = self.status()
        if not info['ready']:
            raise VoiceError(info['message'])
        if not self.gate.acquire(timeout=0.1):
            raise VoiceError('R\u00f6sten arbetar. Prova igen om en liten stund.',429)
        name = None
        try:
            self.cache.mkdir(parents=True,exist_ok=True,mode=0o700)
            self.cache.chmod(0o700)
            text = clean_text(text)
            if not text:
                raise ValueError('Ingen text att l\u00e4sa.')
            key = hashlib.sha256(f'{VERSION}|{uid}|{info["binary"]}|sv|{speed}|{text}'.encode()).hexdigest()
            output = self.cache/(key+'.wav')
            if output.exists() and not output.is_symlink() and output.stat().st_size < 12_000_000:
                data=output.read_bytes()
                try:
                    self.verify(data)
                    os.utime(output,None)
                    return data
                except VoiceError:
                    output.unlink()
            fd,name = tempfile.mkstemp(suffix='.wav',prefix='render-',dir=self.cache)
            os.close(fd)
            try:
                p = subprocess.run([info['binary'],'-v','sv','-s',str(speed),'-a','100','-w',name,'--stdin'],
                    input=text.encode('utf-8'),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                    timeout=20,check=False)
                if p.returncode:
                    raise VoiceError('R\u00f6sten kunde inte skapa ljud. Prova igen.')
            except subprocess.TimeoutExpired:
                raise VoiceError('Uppl\u00e4sningen tog f\u00f6r l\u00e5ng tid. Prova en kortare uppgift.') from None
            except OSError:
                raise VoiceError('R\u00f6stprogrammet kunde inte startas.') from None
            data = Path(name).read_bytes()
            self.verify(data)
            os.replace(name,output);name=None
            self.prune()
            return data
        finally:
            if name:
                Path(name).unlink(missing_ok=True)
            self.gate.release()

    def prune(self):
        entries=sorted((p for p in self.cache.glob('*.wav') if not p.is_symlink()),key=lambda p:p.stat().st_mtime,reverse=True)
        total=0
        for i,p in enumerate(entries):
            total += p.stat().st_size
            if i>=120 or total>32*1024*1024:
                p.unlink(missing_ok=True)


def register_voice(app, store, boot):
    from flask import Blueprint,jsonify,render_template,request,redirect,url_for,flash,Response
    if 'familj_voice54' in app.extensions:
        return
    voice=VoiceStore(store);synth=Synthesizer(store.data)
    app.extensions['familj_voice54'] = dict(store=voice,synth=synth)
    bp=Blueprint('familj_voice54',__name__)

    @bp.get('/admin/speech')
    def page():
        return render_template('speech54.html',boot=boot('admin'),voice_users=[voice.settings(u['id']) for u in store.users()],voice_engine=synth.status())

    @bp.post('/admin/speech/<int:uid>')
    def save(uid):
        try:
            voice.save(uid,request.form)
        except (ValueError,LookupError) as e:
            return render_template('speech54.html',boot=boot('admin'),voice_users=[voice.settings(u['id']) for u in store.users()],voice_engine=synth.status(),voice_error=str(e)),400
        flash('Uppl\u00e4sningen \u00e4r sparad. Profilsidan uppdateras automatiskt.')
        return redirect(url_for('familj_voice54.page'),code=303)

    @bp.get('/api/voice/profile/<int:uid>')
    def config(uid):
        settings=voice.settings(uid)
        info=synth.status()
        return jsonify(ok=True,settings=settings,pending_ids=voice.pending(uid) if settings['enabled'] else [],
            engine=dict(ready=info['ready'],name=info['engine'],message=info['message']),version=store.version())

    @bp.post('/api/voice/profile/<int:uid>/audio')
    def audio(uid):
        payload=request.get_json(silent=True)
        if not isinstance(payload,dict):
            raise ValueError('Ogiltig f\u00f6rfr\u00e5gan.')
        try:
            text,settings=voice.text(uid,payload.get('kind'),payload.get('task_id'))
            data=synth.synthesize(uid,text,settings['speed'])
        except VoiceError as error:
            return jsonify(ok=False,error=str(error)),error.status
        return Response(data,mimetype='audio/wav',headers={'Cache-Control':'no-store','Content-Disposition':'inline; filename="speech.wav"'})

    app.register_blueprint(bp)
