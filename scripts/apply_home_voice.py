#!/usr/bin/env python3
"""Apply minimal additive hooks to v5, Touch5.2 and optional Remote5.3.

Validate all outputs before writing; backup code OUTSIDE Git; idempotent.
Never edits touch JS/CSS, core store, task templates or deployment scripts.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARK='# FAMILJ_HOMEVOICE_5_4'
BASE_MARK='<!-- FAMILJ_HOMEVOICE_5_4_ASSETS -->'
LINK_MARK='<!-- FAMILJ_HOMEVOICE_5_4_LINKS -->'


def transforms(root):
    spec=importlib.util.spec_from_file_location('apply_remote54',root/'scripts/apply_remote.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    paths=['app.py','templates/admin.html','templates/base.html']
    required=paths+['familj/store.py','familj/voice54.py','familj/mobile54.py','familj/remote_access.py',
        'static/voice54.js','static/voice54.css','static/mobile54.js','static/homevoice-icon-192.png',
        'templates/mobile54.html','templates/speech54.html']
    for rel in required:
        p=root/rel
        if not p.is_file() or p.is_symlink():raise ValueError('Missing or symlinked file: '+rel)
    if 'data/' not in (root/'.gitignore').read_text(encoding='utf-8-sig').splitlines():
        raise ValueError('data/ must be ignored by Git.')
    raw={rel:(root/rel).read_bytes() for rel in paths}
    original={rel:v.decode('utf-8-sig').replace('\r\n','\n') for rel,v in raw.items()}
    app,admin=mod.transform(original['app.py'],original['templates/admin.html'])
    if MARK not in app:
        anchor='    if start_workers:\n'
        if app.count(anchor)!=1:raise ValueError('Unrecognized app worker structure.')
        hook=f'    {MARK}\n    from familj.voice54 import register_voice\n    from familj.mobile54 import register_mobile\n    register_voice(app, store, boot)\n    register_mobile(app, store, boot)\n\n'
        app=app.replace(anchor,hook+anchor,1)
    elif app.count(MARK)!=1 or 'register_voice(app, store, boot)' not in app or 'register_mobile(app, store, boot)' not in app:
        raise ValueError('Incomplete HomeVoice registration. No files changed.')
    if LINK_MARK not in admin:
        anchor='{% for msg in get_flashed_messages() %}'
        if admin.count(anchor)!=1:raise ValueError('Unrecognized admin template.')
        links=LINK_MARK+'\n<nav aria-label="Mobil och ljud"><p><a class="text-button" href="/admin/mobile">Samma app hemma och borta &rarr;</a> &middot; <a class="text-button" href="/admin/speech">Uppl&auml;sning per profil &rarr;</a></p></nav>\n'
        admin=admin.replace(anchor,links+anchor,1)
    base=original['templates/base.html']
    if BASE_MARK not in base:
        if base.count('</head>')!=1 or base.count('</body>')!=1 or 'boot.view' not in base:
            raise ValueError('Unrecognized base template. No files changed.')
        css=BASE_MARK+'''\n<link rel="stylesheet" href="{{ asset('voice54.css') }}">
{% if boot.view in ['admin','login'] %}<link rel="manifest" href="/mobile.webmanifest"><link rel="apple-touch-icon" href="{{ asset('homevoice-icon-192.png') }}"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Hemma">{% endif %}
'''
        js="{% if boot.view in ['user','admin'] %}<script src=\"{{ asset('voice54.js') }}\" defer></script>{% endif %}\n"
        base=base.replace('</head>',css+'</head>',1).replace('</body>',js+'</body>',1)
    elif "asset('voice54.js')" not in base or "asset('voice54.css')" not in base:
        raise ValueError('Incomplete existing assets. No files changed.')
    ast.parse(app)
    for rel in ['familj/voice54.py','familj/mobile54.py']:
        ast.parse((root/rel).read_text())
    return raw,dict(zip(paths,[app,admin,base])),mod.atomic


def apply(root,check=False):
    root=Path(root).resolve();raw,out,atomic=transforms(root)
    changes={r:v for r,v in out.items() if raw[r].decode('utf-8-sig').replace('\r\n','\n')!=v}
    if not changes:
        print('HomeVoice 5.4 already applied. No changes.');return None
    print('Compatible. Minimal changes: '+', '.join(changes))
    if check:return None
    backup=Path.home()/'.familj-code-backups'/('homevoice54-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True)
    for rel in changes:
        p=backup/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw[rel])
    try:
        for rel,value in changes.items():atomic(root/rel,value)
    except BaseException:
        for rel in changes:(root/rel).write_bytes(raw[rel])
        raise
    info={r:dict(before=hashlib.sha256(raw[r]).hexdigest(),after=hashlib.sha256((root/r).read_bytes()).hexdigest()) for r in changes}
    (backup/'manifest.json').write_text(json.dumps(info,indent=2))
    print('HomeVoice 5.4 ready. Backup outside Git: '+str(backup))
    print('Touch, tasks, badges, database and startup files were not replaced.')
    return backup


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    try:apply(args.root,args.check)
    except (OSError,ValueError,SyntaxError) as e:print('STOP: '+str(e),file=sys.stderr);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
