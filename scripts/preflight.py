#!/usr/bin/env python3
"""Test the candidate using a COPY of the real database, never the original."""
import argparse
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--database',type=Path);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='familj-preflight-') as temp:
        root=Path(temp);(root/'data').mkdir()
        if args.database and args.database.exists():
            with closing(sqlite3.connect(args.database)) as src,closing(sqlite3.connect(root/'data/home_display.db')) as dst:
                src.backup(dst)
        app=create_app(root,start_workers=False,testing=True)
        store=app.extensions['store']
        paths=['/','/health','/admin/login','/api/state','/api/weather']
        paths += ['/admin?tab='+t for t in ['overview','tasks','people','settings']]
        for u in store.users():paths += [f"/user/{u['id']}",f"/user/{u['id']}/badges"]
        with app.test_client() as client:
            # Bypass an existing PIN only in this temporary copy, not in production.
            store.save_settings({'remove_pin':'1'})
            for path in paths:
                response=client.get(path)
                if response.status_code!=200:raise RuntimeError(f'{path}: HTTP {response.status_code}')
            for name in ['app.js','admin.js','style.css','saver.js']:
                if client.get('/static/'+name).status_code!=200:raise RuntimeError('Missing asset: '+name)
        print(f'Preflight OK: {len(paths)} routes and static assets; original data untouched.')

if __name__=='__main__':main()
