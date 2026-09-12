"""Optional Remote 5.3: no database migration, no network mutations in Flask.

Tailscale membership and the existing admin PIN are separate layers. Identity
and forwarding headers are never trusted to bypass the PIN. Status commands
are read-only, time-limited and cached, and run only on the remote-admin page.
"""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

VERSION = '5.3.0'
TARGET = 'http://127.0.0.1:5000'
SETTINGS_FILE = 'remote-access.json'


def dns_name(value):
    """Only accept Tailscale FQDNs, never arbitrary links."""
    if not isinstance(value, str):
        return None
    value = value.rstrip('.').lower()
    if len(value) > 253 or not value.endswith('.ts.net'):
        return None
    labels = value.split('.')
    if len(labels) < 4 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part) for part in labels):
        return None
    return value


def has_funnel(value):
    if not isinstance(value, dict):
        return False
    if 'AllowFunnel' in value:
        flags = value['AllowFunnel']
        if flags and (not isinstance(flags, dict) or any(v is not False for v in flags.values())):
            return True
    return any(has_funnel(v) for v in value.values() if isinstance(v, dict))


def serve_matches(config, host):
    """Require exactly our sole, private, device-level HTTPS proxy.

    Intentionally reject other ports, paths, foreground sessions or Services.
    An unfamiliar configuration must never be overwritten by our installer.
    """
    host = dns_name(host)
    if not host or not isinstance(config, dict) or has_funnel(config):
        return False
    if any(k not in {'TCP', 'Web', 'AllowFunnel'} and v for k, v in config.items()):
        return False
    tcp = config.get('TCP') or {}
    if not isinstance(tcp, dict) or set(tcp) != {'443'} or tcp['443'] != {'HTTPS': True}:
        return False
    web = config.get('Web') or {}
    if not isinstance(web, dict) or set(web) != {host + ':443'}:
        return False
    entry = web[host + ':443']
    return isinstance(entry, dict) and entry in (
        {'Handlers': {'/': {'Proxy': TARGET}}},
        {'Handlers': {'/': {'Proxy': TARGET + '/'}}},
    )


def serve_empty(config):
    return isinstance(config, dict) and not any(bool(v) for v in config.values())


def config_fingerprint(config):
    data = json.dumps(config, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(data).hexdigest()


def local_record(data):
    path = Path(data) / SETTINGS_FILE
    if not path.exists():
        return {}
    try:
        if path.stat().st_size > 16384:
            return {'invalid': True}
        obj = json.loads(path.read_text(encoding='utf-8'))
        return obj if isinstance(obj, dict) else {'invalid': True}
    except (OSError, ValueError):
        return {'invalid': True}


def json_command(args, timeout=3):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=timeout, check=False)
        if result.returncode:
            return None, 'command_failed'
        if len(result.stdout) > 2_000_000:
            return None, 'oversized_response'
        obj = json.loads(result.stdout or '{}')
        return (obj, None) if isinstance(obj, dict) else (None, 'invalid_response')
    except subprocess.TimeoutExpired:
        return None, 'timeout'
    except (OSError, ValueError):
        return None, 'unavailable'


def status_from(ts, serve, record, pin_enabled, *, ts_error=None, serve_error=None):
    """Pure status adapter. Never return raw peer data, identities or auth URLs."""
    result = {
        'extension_version': VERSION,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'state': 'not_installed', 'title': 'Inte aktiverat \u00e4n',
        'detail': 'Aktivera Tailscale en g\u00e5ng p\u00e5 Raspberryn.',
        'pin_enabled': bool(pin_enabled), 'configured': False, 'url': None,
        'external_tested': False, 'funnel_detected': False,
    }
    if ts_error:
        result.update(state='unavailable', title='Status kunde inte l\u00e4sas',
            detail='Tailscale svarade inte i tid eller saknas. Den lokala appen p\u00e5verkas inte.')
        return result
    if not ts:
        return result
    state = ts.get('BackendState', 'Unknown')
    if state != 'Running':
        labels = {'NeedsLogin': 'Logga in i Tailscale',
                  'NeedsMachineAuth': 'Godk\u00e4nn Raspberryn i Tailscale',
                  'Stopped': 'Tailscale \u00e4r fr\u00e5nkopplat', 'NoState': 'Tailscale startar'}
        result.update(state='disconnected', title=labels.get(state, 'Tailscale \u00e4r inte redo'),
            detail='K\u00f6r installationsguiden p\u00e5 Raspberryn. Den lokala appen kan forts\u00e4tta k\u00f6ra.')
        return result
    identity = ts.get('Self') or {}
    host = dns_name(identity.get('DNSName')) if isinstance(identity, dict) else None
    if has_funnel(serve):
        result.update(state='warning', title='Offentlig Funnel uppt\u00e4ckt', funnel_detected=True,
            detail='Den h\u00e4r guiden anv\u00e4nder bara privat Serve. Kontrollera Tailscale innan du delar n\u00e5gon adress.')
        return result
    if not pin_enabled:
        result.update(state='pin_required', title='S\u00e4tt en admin-PIN f\u00f6rst',
            detail='V\u00e4lj 6\u201312 siffror under Inst\u00e4llningar. Dela inte PIN eller inloggningskoder i chatten.')
        return result
    if serve_error:
        result.update(state='unavailable', title='Tailscale k\u00f6r, Serve-status saknas',
            detail='K\u00f6r python3 scripts/setup_remote.py status via SSH f\u00f6r att kontrollera.')
        return result
    if host and serve_matches(serve, host):
        result.update(state='ready', title='Privat fj\u00e4rradress konfigurerad', configured=True,
            url='https://' + host + '/admin',
            detail='Pi:n \u00e4r inloggad och HTTPS-proxyn \u00e4r r\u00e4tt inst\u00e4lld. Prova adressen med mobildata f\u00f6r att kontrollera hela anslutningen.')
    else:
        result.update(state='setup_needed', title='Tailscale k\u00f6r \u2013 HTTPS \u00e5terst\u00e5r',
            detail='K\u00f6r python3 scripts/setup_remote.py enable p\u00e5 Raspberryn. Andra Serve-inst\u00e4llningar skrivs inte \u00f6ver.')
    result['managed_by_extension'] = bool(record.get('managed'))
    return result


class StatusReader:
    def __init__(self, data):
        self.data = Path(data)
        self.lock = threading.Lock()
        self.cached = None
        self.at = 0

    def get(self, pin_enabled):
        with self.lock:
            now = time.monotonic()
            if self.cached is None or now - self.at > 12:
                binary = shutil.which('tailscale')
                if not binary:
                    self.cached = (None, None, local_record(self.data), None, None)
                else:
                    ts, error = json_command([binary, 'status', '--json'])
                    serve, se = json_command([binary, 'serve', 'status', '--json']) if not error else (None, error)
                    self.cached = (ts, serve, local_record(self.data), error, se)
                self.at = now
            ts, serve, record, error, se = self.cached
            return status_from(ts, serve, record, pin_enabled, ts_error=error, serve_error=se)


def register_remote(app, store, boot):
    # Import Flask only here: status parsing can be tested without Flask/network.
    from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for
    if 'familj_remote' in app.extensions:
        return
    reader = StatusReader(store.data)
    app.extensions['familj_remote'] = reader
    bp = Blueprint('familj_remote', __name__)

    def locked():
        saved = store.settings(private=True).get('admin_pin_hash', '')
        return bool(saved) and session.get('admin_key') != hashlib.sha256(saved.encode()).hexdigest()

    @bp.get('/admin/remote')
    def page():
        if locked():
            return redirect(url_for('login'))
        return render_template('remote.html', boot=boot('admin'),
                               remote=reader.get(store.settings()['pin_enabled']))

    @bp.get('/admin/remote/status')
    def status():
        if locked():
            return jsonify(ok=False, error='Logga in i admin f\u00f6rst.'), 401
        return jsonify(reader.get(store.settings()['pin_enabled']))

    @app.before_request
    def keep_pin_for_remote():
        if request.method == 'POST' and request.path == '/admin/settings':
            record = local_record(store.data)
            if (record.get('managed') or record.get('invalid')) and 'remove_pin' in request.form and not request.form.get('new_pin'):
                raise ValueError('St\u00e4ng av fj\u00e4rr\u00e5tkomsten innan du tar bort admin-PIN. Du kan byta PIN som vanligt.')

    app.register_blueprint(bp)
