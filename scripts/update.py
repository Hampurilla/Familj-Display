#!/usr/bin/env python3
"""Staged fast-forward updater. Run as the normal Pi user, never as root.

Dependencies are installed in a separate environment. Candidate routes and a
copied database are tested before promotion. Nothing deletes production data.
--boot: app starts afterward through systemd; do not restart it from this unit.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from contextlib import closing
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
ENV=os.environ|{'GIT_TERMINAL_PROMPT':'0','PIP_DISABLE_PIP_VERSION_CHECK':'1','PIP_NO_INPUT':'1'}

def run(args,cwd=ROOT,timeout=30,check=True):
    result=subprocess.run([str(x) for x in args],cwd=cwd,env=ENV,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    if result.stdout.strip():print(result.stdout.strip(),flush=True)
    if check and result.returncode:raise RuntimeError('Command failed: '+str(args[0]))
    return result

def capture(args):
    return subprocess.check_output(args,cwd=ROOT,env=ENV,text=True,timeout=20).strip()

def backup_db(source):
    if not source.exists():return
    folder=ROOT/'data/backups';folder.mkdir(parents=True,exist_ok=True)
    target=folder/(time.strftime('%Y%m%d-%H%M%S')+'-before-update.sqlite3')
    with closing(sqlite3.connect(source)) as src,closing(sqlite3.connect(target)) as dst:src.backup(dst)
    print('Database backup:',target,flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--boot',action='store_true');args=parser.parse_args()
    if os.geteuid()==0:raise RuntimeError('Run this updater as the normal user, not root.')
    data=ROOT/'data';data.mkdir(exist_ok=True)
    lock=(data/'update.lock').open('w')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:print('An update is already running.');return
    if not (ROOT/'.git').exists():print('No Git checkout. Keeping local app.');return
    old=capture(['git','rev-parse','HEAD'])
    try:run(['git','fetch','--no-tags','origin','main'],timeout=20)
    except (RuntimeError,subprocess.TimeoutExpired):print('GitHub unavailable. Keeping local app and environment.');return
    new=capture(['git','rev-parse','FETCH_HEAD'])
    if new==old:print('Already current:',old[:8]);return
    if capture(['git','status','--porcelain','--untracked-files=no']):
        print('Tracked local changes detected. Refusing to overwrite them.');return
    if run(['git','merge-base','--is-ancestor',old,new],check=False).returncode:
        print('Not a fast-forward. Keeping current version.');return
    names=capture(['git','ls-tree','-r','--name-only',new]).splitlines()
    if any(n.startswith(('data/','venv/','.venv/')) or n=='.env' or n.endswith(('.db','.sqlite3')) for n in names):
        raise RuntimeError('Repository contains private data/environment paths. Update refused.')
    if shutil.disk_usage(ROOT).free<200*1024*1024:raise RuntimeError('Less than 200 MB free. Update refused.')
    env_dir=data/'environments'/new
    source=data/'home_display.db'
    if not source.exists():source=ROOT/'home_display.db'
    with tempfile.TemporaryDirectory(prefix='.familj-candidate-',dir=ROOT.parent) as temp:
        candidate=Path(temp)
        archive=candidate/'source.tar'
        with archive.open('wb') as out:
            subprocess.run(['git','archive',new],cwd=ROOT,stdout=out,check=True,timeout=30)
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                if member.issym() or member.islnk() or member.name.startswith('/') or '..' in Path(member.name).parts:
                    raise RuntimeError('Unsafe archive entry.')
            tar.extractall(candidate,filter='data')
        archive.unlink()
        if not (env_dir/'bin/python').exists():
            run(['/usr/bin/python3','-m','venv',env_dir],timeout=90)
        python=env_dir/'bin/python'
        run([python,'-m','pip','install','--timeout','12','--retries','1','-r',candidate/'requirements.txt'],timeout=180)
        run([python,candidate/'app.py','--check'],cwd=candidate,timeout=60)
        run([python,candidate/'scripts/preflight.py','--database',source],cwd=candidate,timeout=90)
        # Check again: do not promote over a user's concurrent edits.
        if capture(['git','status','--porcelain','--untracked-files=no']):raise RuntimeError('Local files changed during staging.')
        if not args.boot:run(['sudo','-n','systemctl','stop','home-display.service'])
        current_env=ROOT/'venv';old_env_link=os.readlink(current_env) if current_env.is_symlink() else None
        old_env_dir=None;promoted=False
        try:
            backup_db(source)
            run(['git','merge','--ff-only',new])
            if current_env.exists() and not current_env.is_symlink():
                old_env_dir=data/'environments'/('legacy-'+str(int(time.time())))
                old_env_dir.parent.mkdir(parents=True,exist_ok=True);current_env.rename(old_env_dir)
            temp_link=ROOT/'.venv-next'
            if temp_link.is_symlink():temp_link.unlink()
            temp_link.symlink_to(env_dir,target_is_directory=True);os.replace(temp_link,current_env)
            promoted=True
            if not args.boot:
                run(['sudo','-n','systemctl','start','home-display.service'])
                healthy=False
                for _ in range(35):
                    try:
                        with urlopen('http://127.0.0.1:5000/health',timeout=2) as r:
                            if r.status==200 and json.load(r).get('ok'):healthy=True;break
                    except OSError:pass
                    time.sleep(1)
                if not healthy:raise RuntimeError('Updated app did not become healthy.')
            print('Update promoted:',new[:8],flush=True)
            print('The database was not replaced. Keep the backup until verified.',flush=True)
        except BaseException:
            print('Promotion failed. Restoring old CODE and environment; preserving database and backup.',flush=True)
            if not args.boot:run(['sudo','-n','systemctl','stop','home-display.service'],check=False)
            run(['git','reset','--hard',old])
            if promoted and current_env.is_symlink():current_env.unlink()
            if old_env_link:
                if current_env.is_symlink():current_env.unlink()
                current_env.symlink_to(old_env_link,target_is_directory=True)
            elif old_env_dir and old_env_dir.exists():
                if current_env.is_symlink():current_env.unlink()
                old_env_dir.rename(current_env)
            if not args.boot:run(['sudo','-n','systemctl','start','home-display.service'],check=False)
            raise

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Update not completed:',error,flush=True)
        # A failed updater must not prevent the existing app from starting at boot.
        sys.exit(0 if '--boot' in sys.argv else 1)
