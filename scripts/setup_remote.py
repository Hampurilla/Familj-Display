#!/usr/bin/env python3
"""Opt-in Tailscale Serve setup for Familj Display. Python standard library only.

Does not modify app code, systemd units, kiosk settings, Git, firewall rules,
subnet/exit-node settings or the database. Only the official Tailscale installer
and explicitly confirmed Tailscale operations need sudo.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from familj.remote_access import (TARGET, SETTINGS_FILE, dns_name, has_funnel,
    serve_matches, serve_empty, config_fingerprint, local_record, status_from)


class SetupError(Exception):
    pass


def run(args, *, capture=False, timeout=30):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None, timeout=timeout, check=False)
    if result.returncode:
        # Do not print stderr, which can include login URLs or raw status data.
        raise SetupError('Kommandot misslyckades: ' + ' '.join(args[:3]) + '. Se meddelandet ovan eller prova igen.')
    return result.stdout if capture else ''


def ts_json(binary, args, privileged=False):
    command = (['sudo'] if privileged else []) + [binary] + args
    try:
        data = json.loads(run(command, capture=True) or '{}')
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (ValueError, subprocess.TimeoutExpired):
        raise SetupError('Kunde inte tolka Tailscale-status. Inget annat har skrivits \u00f6ver.') from None


def pin_exists(root):
    db = root / 'data/home_display.db'
    if not db.is_file():
        raise SetupError('Databasen saknas i data/. Starta appen f\u00f6rst. Ingen databas skapas av guiden.')
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=5)) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='admin_pin_hash'").fetchone()
    return bool(row and row[0])


def confirm(message):
    print('\n' + message)
    try:
        answer = input('Forts\u00e4tta? [j/N] ').strip().lower()
    except EOFError:
        return False
    return answer in ('j', 'ja', 'y', 'yes')


def write_record(root, record):
    path = root / 'data' / SETTINGS_FILE
    path.parent.mkdir(exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.remote-', dir=path.parent)
    try:
        os.chmod(name, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def verify_app(root):
    if '# FAMILJ_REMOTE_5_3' not in (root / 'app.py').read_text(encoding='utf-8-sig'):
        raise SetupError('F\u00f6rbered koden med scripts/apply_remote.py och starta om appen f\u00f6rst.')
    try:
        # Localhost only. No auth data or server state is sent anywhere.
        with urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=6) as response:
            if response.status != 200 or json.load(response).get('ok') is not True:
                raise ValueError
        with urllib.request.urlopen('http://127.0.0.1:5000/admin/remote', timeout=8) as response:
            if response.status != 200:
                raise ValueError
    except Exception:
        raise SetupError('Appen eller /admin/remote svarar inte lokalt. Kontrollera home-display-tj\u00e4nsten innan n\u00e4tverket \u00e4ndras.') from None


def backup_configuration(root, config):
    folder = root / 'data/backups'
    folder.mkdir(parents=True, exist_ok=True)
    name = folder / ('remote-serve-before-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    with name.open('x', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    name.chmod(0o600)
    return name


def install_client():
    if not shutil.which('curl'):
        raise SetupError('curl saknas. Installera med: sudo apt install curl')
    print('H\u00e4mtar Tailscales officiella installationsscript via HTTPS ...')
    with tempfile.TemporaryDirectory(prefix='familj-tailscale-') as tmp:
        installer = str(Path(tmp) / 'install.sh')
        run(['curl', '--fail', '--show-error', '--location', '--proto', '=https',
             '--proto-redir', '=https', '--connect-timeout', '15', '--max-time', '60',
             '--output', installer, 'https://tailscale.com/install.sh'], timeout=70)
        # Interactive package installation. Let apt finish; do not kill apt on a short timer.
        run(['sudo', 'sh', installer], timeout=None)
    binary = shutil.which('tailscale')
    if not binary:
        raise SetupError('Installationen avslutades men tailscale hittades inte. Lokal app \u00e4r of\u00f6r\u00e4ndrad.')
    return binary


def enable(root):
    verify_app(root)
    if not pin_exists(root):
        raise SetupError('S\u00e4tt f\u00f6rst en admin-PIN (6\u201312 siffror) i /admin -> Inst\u00e4llningar. K\u00f6r sedan guiden igen.')
    if not confirm('Detta aktiverar privat Tailscale-\u00e5tkomst. Tailscale installeras vid behov.\n'
                   'Ingen port i routern \u00f6ppnas av guiden och ingen Funnel aktiveras.\n'
                   'HTTPS-certifikatets enhets-/dom\u00e4nnamn registreras offentligt; appen blir inte offentlig.\n'
                   'Befintlig Serve-konfiguration kontrolleras innan n\u00e5got \u00e4ndras.'):
        print('Avbrutet. Ingen \u00e4ndring gjord.')
        return
    binary = shutil.which('tailscale') or install_client()
    run(['sudo', 'systemctl', 'enable', '--now', 'tailscaled'], timeout=45)
    status = ts_json(binary, ['status', '--json'], True)
    if status.get('BackendState') != 'Running':
        print('Logga in genom den officiella l\u00e4nken som Tailscale skriver ut. Dela inte inloggningsl\u00e4nken i chatten.')
        run(['sudo', binary, 'up'], timeout=None)
        status = ts_json(binary, ['status', '--json'], True)
    if status.get('BackendState') != 'Running':
        raise SetupError('Tailscale \u00e4r inte inloggat/godk\u00e4nt \u00e4n. K\u00f6r enable igen efter godk\u00e4nnande.')
    host = dns_name((status.get('Self') or {}).get('DNSName'))
    if not host:
        raise SetupError('Inget giltigt .ts.net-namn hittades. Aktivera MagicDNS i Tailscales DNS-inst\u00e4llningar.')
    config = ts_json(binary, ['serve', 'status', '--json'], True)
    if has_funnel(config):
        raise SetupError('Funnel \u00e4r redan aktiverat. Guiden \u00e4ndrar inte en offentlig delning automatiskt.')
    if not serve_empty(config) and not serve_matches(config, host):
        raise SetupError('Annan Serve-konfiguration finns. Den l\u00e4mnas or\u00f6rd; granska med sudo tailscale serve status.')
    backup = backup_configuration(root, config)
    if not serve_matches(config, host):
        print('Aktiverar privat HTTPS. Godk\u00e4nn eventuellt MagicDNS/HTTPS via Tailscales l\u00e4nk.')
        run(['sudo', binary, 'serve', '--bg', '--https=443', TARGET], timeout=None)
    current = ts_json(binary, ['serve', 'status', '--json'], True)
    if not serve_matches(current, host):
        raise SetupError('Serve kunde inte verifieras. Ingen annan konfiguration \u00e5terst\u00e4lls automatiskt. Kontrollera sudo tailscale serve status.')
    write_record(root, {'format': 1, 'managed': True, 'host': host,
        'serve_sha256': config_fingerprint(current), 'activated_at': datetime.now(timezone.utc).isoformat(),
        'backup': str(backup)})
    print('\nKLART: privat HTTPS-konfiguration verifierad p\u00e5 Raspberryn.')
    print('Mobilens adress: https://' + host + '/admin')
    print('Installera/anslut Tailscale i mobilen och prova adressen med Wi-Fi av.')
    print('Det verkliga testet utifr\u00e5n kan bara du g\u00f6ra. Serve --bg sparas \u00f6ver omstart.')
    print('Bjud in mamma med eget konto. Samma app, PIN, uppgifter och databas anv\u00e4nds.')
    print('Appen forts\u00e4tter lokalt utan Tailscale/internet. Inga kiosk-/GitHub-script har \u00e4ndrats.')


def disable(root):
    binary = shutil.which('tailscale')
    record = local_record(root / 'data')
    if not binary or not record.get('managed'):
        raise SetupError('Ingen hanterad Serve-delning hittades. Inget \u00e4ndras.')
    host = dns_name(record.get('host'))
    config = ts_json(binary, ['serve', 'status', '--json'], True)
    if not serve_empty(config) and (not serve_matches(config, host) or config_fingerprint(config) != record.get('serve_sha256')):
        raise SetupError('Serve-konfigurationen har \u00e4ndrats sedan installationen. Inget tas bort automatiskt.')
    if not confirm('St\u00e4ng av denna HTTPS-delning? Den lokala familjeappen forts\u00e4tter.\n'
                   'Tailscale i sig kopplas inte bort; direkt IP-\u00e5tkomst kan finnas kvar.\n'
                   'Ta bort delning/beh\u00f6righet i Tailscale f\u00f6r att \u00e5terkalla all fj\u00e4rr\u00e5tkomst.'):
        return
    if not serve_empty(config):
        run(['sudo', binary, 'serve', '--bg', '--https=443', 'off'], timeout=30)
    current = ts_json(binary, ['serve', 'status', '--json'], True)
    if not serve_empty(current):
        raise SetupError('HTTPS-delningen kunde inte bekr\u00e4ftas avst\u00e4ngd. Inget mer har rensats.')
    write_record(root, {'format': 1, 'managed': False, 'disabled_at': datetime.now(timezone.utc).isoformat()})
    print('Den hanterade HTTPS-delningen \u00e4r avst\u00e4ngd. Appen och Tailscale-klienten \u00e4r kvar.')


def report(root):
    binary = shutil.which('tailscale')
    if not binary:
        print('Tailscale \u00e4r inte installerat. Den lokala appen fungerar oberoende av detta.')
        return
    ts = ts_json(binary, ['status', '--json'])
    config = ts_json(binary, ['serve', 'status', '--json'])
    data = status_from(ts, config, local_record(root / 'data'), pin_exists(root))
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['enable', 'status', 'disable'])
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.action != 'status':
            if sys.platform != 'linux':
                raise SetupError('enable/disable k\u00f6rs p\u00e5 Raspberryn via SSH, inte p\u00e5 Windows.')
            if os.geteuid() == 0:
                raise SetupError('K\u00f6r som admin utan sudo framf\u00f6r python3. Guiden ber om sudo d\u00e4r det beh\u00f6vs.')
        {'enable': enable, 'disable': disable, 'status': report}[args.action](root)
        return 0
    except KeyboardInterrupt:
        print('\nAvbrutet. Den lokala appen har inte stoppats. K\u00f6r status f\u00f6r att se hur l\u00e5ngt guiden hann.')
        return 130
    except (SetupError, OSError, ValueError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        print('STOPP: ' + str(error), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
