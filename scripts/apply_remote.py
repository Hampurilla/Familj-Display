#!/usr/bin/env python3
"""Add Remote 5.3 hooks without replacing the installed app or touch files."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
APP_MARK = '# FAMILJ_REMOTE_5_3'
HTML_MARK = '<!-- FAMILJ_REMOTE_5_3 -->'
HOOK = '    # FAMILJ_REMOTE_5_3\n    from familj.remote_access import register_remote\n    register_remote(app, store, boot)\n\n'
LINK = '<!-- FAMILJ_REMOTE_5_3 -->\n<p><a class="text-button" href="/admin/remote">Fj&auml;rr&aring;tkomst &middot; anslut mobil utanf&ouml;r hemmet &rarr;</a></p>\n'


def transform(app_text, admin_text):
    if APP_MARK in app_text:
        if app_text.count(APP_MARK) != 1 or 'register_remote(app, store, boot)' not in app_text:
            raise ValueError('Unexpected existing Remote hook. No file changed.')
        updated_app = app_text
    else:
        anchors = ['def create_app(', "request.path.startswith('/admin')", 'def boot(',
                   'def login()', '    if start_workers:\n']
        if not all(a in app_text for a in anchors) or app_text.count('    if start_workers:\n') != 1:
            raise ValueError('App structure is unfamiliar. No file changed. Send app.py for review.')
        updated_app = app_text.replace('    if start_workers:\n', HOOK + '    if start_workers:\n', 1)
    ast.parse(updated_app)
    if HTML_MARK in admin_text:
        if admin_text.count(HTML_MARK) != 1:
            raise ValueError('Multiple Remote links; no file changed.')
        updated_admin = admin_text
    else:
        anchor = '{% for msg in get_flashed_messages() %}'
        if admin_text.count(anchor) != 1 or 'class="admin-tabs"' not in admin_text:
            raise ValueError('Admin template structure is unfamiliar. No file changed.')
        updated_admin = admin_text.replace(anchor, LINK + anchor, 1)
    return updated_app, updated_admin


def atomic(path, content):
    fd, name = tempfile.mkstemp(prefix='.remote-write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def apply(root, check=False):
    root = Path(root).resolve()
    for rel in ('app.py', 'templates/admin.html', 'familj/store.py', 'familj/remote_access.py',
                'templates/remote.html', 'static/remote.css', 'static/remote.js'):
        if not (root / rel).is_file() or (root / rel).is_symlink():
            raise ValueError('Missing or symlinked file: ' + rel)
    ignore = root / '.gitignore'
    if not ignore.is_file() or 'data/' not in [s.strip() for s in ignore.read_text(encoding='utf-8-sig').splitlines()]:
        raise ValueError('data/ must be in .gitignore before enabling remote access.')
    paths = [root / 'app.py', root / 'templates/admin.html']
    original = [p.read_bytes() for p in paths]
    text = [b.decode('utf-8-sig').replace('\r\n', '\n') for b in original]
    output = transform(*text)
    if output == tuple(text):
        print('Remote 5.3 already prepared. No changes.')
        return None
    if check:
        print('Compatible: only app.py hook and admin link would change.')
        return None
    backup = Path.home() / '.familj-code-backups' / ('remote53-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True)
    for p, raw in zip(paths, original):
        target = backup / p.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    try:
        for p, content in zip(paths, output):
            atomic(p, content)
    except BaseException:
        for p, raw in zip(paths, original):
            p.write_bytes(raw)
        raise
    manifest = {'root': str(root), 'files': {
        p.relative_to(root).as_posix(): {
            'before_sha256': hashlib.sha256(raw).hexdigest(),
            'after_sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        for p, raw in zip(paths, original)}}
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Remote 5.3 prepared. Existing database/touch/kiosk files were not replaced.')
    print('Changed: app.py (registration hook), templates/admin.html (link).')
    print('Code backup outside Git: ' + str(backup))
    return backup


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', nargs='?', default=str(Path(__file__).resolve().parents[1]))
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    try:
        apply(args.root, args.check)
    except (OSError, ValueError, SyntaxError) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
