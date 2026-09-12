"""Run with `python app.py`. Existing home-display.service remains compatible."""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import os
import secrets
import sqlite3
import tempfile
import threading
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash, send_file
from familj import VERSION
from familj.store import Store, RECURRENCES, ACCENTS, pin_matches
from familj.badges import BADGES, RARITIES
from familj.weather import Weather, locations

SOURCE = Path(__file__).resolve().parent


def build_id():
    h=hashlib.sha256()
    for pattern in ('*.py','familj/*.py','templates/**/*.html','static/*'):
        for p in sorted(SOURCE.glob(pattern)):
            if p.is_file(): h.update(p.relative_to(SOURCE).as_posix().encode()); h.update(p.read_bytes())
    return h.hexdigest()[:12]


def create_app(root=None, start_workers=True, testing=False):
    root=Path(root or os.environ.get('FAMILJ_ROOT',SOURCE))
    store=Store(root)
    secret_path=store.data/'session-secret'
    if not secret_path.exists():
        try:
            with secret_path.open('x',encoding='ascii') as f: f.write(secrets.token_hex(32))
            secret_path.chmod(0o600)
        except FileExistsError: pass
    app=Flask(__name__,template_folder=str(SOURCE/'templates'),static_folder=str(SOURCE/'static'))
    app.config.update(SECRET_KEY=secret_path.read_text().strip(),TESTING=testing,
        MAX_CONTENT_LENGTH=128*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(days=7))
    app.extensions['store']=store
    weather=Weather(store); app.extensions['weather']=weather
    release=build_id()
    login_attempts={}
    login_lock=threading.Lock()
    store.generate()

    def csrf():
        if '_csrf' not in session: session['_csrf']=secrets.token_urlsafe(32)
        return session['_csrf']

    def boot(view,uid=None):
        return dict(view=view,user_id=uid,release=release,version=store.version(),now=store.now().isoformat(),
                    settings=store.settings(),csrf=csrf(),poll_ms=3000)

    @app.context_processor
    def common():
        return dict(csrf=csrf,asset=lambda filename:url_for('static',filename=filename,v=release),
                    settings=store.settings(),version=VERSION,release=release,rarities=RARITIES,
                    recurrences=RECURRENCES,accents=ACCENTS,badge_total=len(BADGES),server_now=store.now())

    @app.template_filter('svdate')
    def svdate(value):
        if not value: return ''
        from datetime import date
        d=date.fromisoformat(value[:10]); today=store.now().date()
        if d==today:return 'Idag'
        if d==today+timedelta(days=1):return 'Imorgon'
        months=['jan','feb','mars','apr','maj','juni','juli','aug','sep','okt','nov','dec']
        return f'{d.day} {months[d.month-1]}'

    @app.before_request
    def guard():
        if request.method=='POST':
            origin=request.headers.get('Origin')
            if origin and urlparse(origin).netloc!=request.host:
                return jsonify(ok=False,error='Ogiltigt ursprung.'),403
            got=request.headers.get('X-CSRF-Token') or request.form.get('_csrf','')
            expected=session.get('_csrf','')
            if not expected or not secrets.compare_digest(got,expected):
                if request.path.startswith('/api/'):
                    return jsonify(ok=False,error='Sessionen beh\u00f6ver uppdateras. Ladda om sidan och prova igen.'),403
                return render_template('error.html',message='Sidan har blivit gammal. G\u00e5 tillbaka, ladda om och prova igen.',boot=boot('error')),403
        if request.path.startswith('/admin') and request.endpoint not in ('login','static'):
            saved=store.settings(private=True)['admin_pin_hash']
            if saved and session.get('admin_key')!=hashlib.sha256(saved.encode()).hexdigest():
                return redirect(url_for('login'))
        if request.endpoint!='static': store.generate()

    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='public, max-age=31536000, immutable' if request.endpoint=='static' and request.args.get('v')==release else 'no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.get('/')
    def home():
        return render_template('home.html',**store.dashboard(),boot=boot('home'))

    @app.get('/user/<int:user_id>')
    def user_page(user_id):
        return render_template('user.html',**store.profile(user_id),boot=boot('user',user_id))

    @app.get('/user/<int:user_id>/badges')
    def badge_page(user_id):
        return render_template('badges.html',**store.collection(user_id),boot=boot('badges',user_id))

    @app.get('/health')
    def health():
        with store.db() as c: c.execute('SELECT 1 FROM users').fetchone()
        return jsonify(ok=True,version=VERSION,build=release,schema=5,time=store.now().isoformat())

    @app.get('/api/version')
    def api_version():
        return jsonify(version=store.version(),release=release,now=store.now().isoformat())

    @app.get('/api/state')
    def state():
        view=request.args.get('view','home')
        uid=request.args.get('user_id',type=int)
        v=store.version()
        data=dict(version=v,release=release,now=store.now().isoformat(),settings=store.settings())
        if str(v)!=request.args.get('since') or request.args.get('release')!=release:
            if view=='home': html=render_template('partials/home_content.html',**store.dashboard())
            elif view=='user' and uid: html=render_template('partials/user_content.html',**store.profile(uid))
            elif view=='badges' and uid: html=render_template('partials/badges_content.html',**store.collection(uid))
            else: html=None
            data['html']=html
        return jsonify(data)

    @app.get('/api/display-settings')
    def display_settings():
        s=store.settings()
        return jsonify({k:s[k] for k in ('idle_minutes','screensaver_enabled','night_enabled','night_start','night_end')})

    @app.get('/api/weather')
    def api_weather():
        return jsonify(weather.snapshot(refresh=start_workers))

    @app.get('/api/locations')
    def api_locations():
        try: return jsonify(results=locations(request.args.get('q','').strip()))
        except Exception: return jsonify(error='Plats\u00f6kningen beh\u00f6ver internet. Du kan skriva koordinater manuellt.'),503

    @app.post('/api/tasks/<int:task_id>/complete')
    @app.post('/api/task/<int:task_id>/toggle')
    def complete(task_id):
        payload=request.get_json(silent=True) or {}
        if 'completed' not in payload: return jsonify(ok=False,error='Uppdatera sidan innan du bockar av.'),409
        return jsonify(store.set_completed(task_id,payload['completed']))

    @app.post('/task/<int:task_id>/toggle')
    def complete_form(task_id):
        if request.form.get('completed') not in ('0','1'): raise ValueError('Ladda om sidan f\u00f6rst.')
        result=store.set_completed(task_id,request.form['completed']=='1')
        return redirect(url_for('user_page',user_id=result['user_id']),code=303)

    def admin_context(tab=None,error=None,draft=None):
        ts=store.templates()
        edit_id=request.args.get('edit',type=int)
        edit_id = edit_id or (request.view_args or {}).get('template_id')
        edit=next((t for t in ts if t['id']==edit_id),None)
        form=dict(title='',notes='',difficulty=3,recurrence='once',start_date=store.now().date().isoformat(),end_date='',assignment_mode='auto',fixed_user_id='',eligible_ids='[]')
        form.update(edit or {})
        form.update(draft or {})
        allowed=form.get('eligible_ids') or '[]'
        form['allowed']=json.loads(allowed) if isinstance(allowed,str) and allowed.startswith('[') else request.form.getlist('eligible_ids')
        return dict(users=store.users(),all_users=store.users(False),templates=ts,today=store.now().date().isoformat(),
                    active_tab=tab or request.args.get('tab','overview'),overview=store.dashboard(),
                    edit=edit,form=form,draft=draft or {},error=error,boot=boot('admin'))

    @app.get('/admin')
    def admin():
        return render_template('admin.html',**admin_context())

    @app.route('/admin/login',methods=['GET','POST'])
    def login():
        error=None
        if request.method=='POST':
            key=request.remote_addr or 'local'
            with login_lock:
                attempts=[x for x in login_attempts.get(key,[]) if x>time.time()-300]
                if len(attempts)>=8:
                    return render_template('login.html',error='F\u00f6r m\u00e5nga f\u00f6rs\u00f6k. V\u00e4nta fem minuter.',boot=boot('login')),429
                attempts.append(time.time()); login_attempts[key]=attempts
                if len(login_attempts)>256: login_attempts.clear()
            saved=store.settings(private=True)['admin_pin_hash']
            if not saved or pin_matches(request.form.get('pin',''),saved):
                session['admin_key']=hashlib.sha256(saved.encode()).hexdigest(); session.permanent=True
                with login_lock: login_attempts.pop(key,None)
                return redirect(url_for('admin'),code=303)
            error='Fel PIN. Prova igen.'
        return render_template('login.html',error=error,boot=boot('login'))

    @app.post('/admin/logout')
    def logout():
        session.pop('admin_key',None)
        return redirect(url_for('login'),code=303)

    @app.post('/admin/user/add')
    @app.post('/admin/user/<int:user_id>/edit')
    def save_user(user_id=None):
        store.save_user(request.form.get('name',''),request.form.get('accent','sage'),request.form.get('share_weight','1'),user_id)
        flash('Profilen \u00e4r sparad.'); return redirect(url_for('admin',tab='people'),code=303)

    @app.post('/admin/user/<int:user_id>/delete')
    def delete_user(user_id):
        store.archive_user(user_id)
        flash('Profilen \u00e4r arkiverad. Historik och m\u00e4rken finns kvar.')
        return redirect(url_for('admin',tab='people'),code=303)

    @app.post('/admin/template/add')
    @app.post('/admin/template/<int:template_id>/edit')
    def save_template(template_id=None):
        values=request.form.to_dict();values['eligible_ids']=request.form.getlist('eligible_ids')
        store.save_template(values,template_id)
        flash('Schemat \u00e4r sparat. Displayen uppdateras automatiskt.')
        return redirect(url_for('admin',tab='tasks'),code=303)

    @app.post('/admin/template/<int:template_id>/delete')
    def delete_template(template_id):
        store.pause_template(template_id)
        flash('Schemat avslutat. Avklarade uppgifter sparas i historiken.')
        return redirect(url_for('admin',tab='tasks'),code=303)

    @app.post('/admin/regenerate')
    def regenerate():
        store.generate(force=True)
        flash('Schemat kontrollerat. Inga dubbletter har skapats.')
        return redirect(url_for('admin',tab='tasks'),code=303)

    @app.post('/admin/settings')
    def save_settings():
        values=request.form.to_dict()
        for key in ('rewards_enabled','screensaver_enabled','night_enabled'):
            if request.form.get('section')=='settings':values[key]='1' if key in request.form else '0'
        if 'remove_pin' in values: values['remove_pin']='1'
        store.save_settings(values)
        saved=store.settings(private=True)['admin_pin_hash']
        session['admin_key']=hashlib.sha256(saved.encode()).hexdigest()
        flash('Inst\u00e4llningarna \u00e4r sparade.')
        return redirect(url_for('admin',tab='settings'),code=303)

    @app.post('/admin/backup')
    def download_backup():
        backup=store.backup('download')
        return send_file(backup,as_attachment=True,download_name=backup.name,mimetype='application/vnd.sqlite3')

    @app.errorhandler(ValueError)
    def bad_request(error):
        if request.path.startswith('/api/'):return jsonify(ok=False,error=str(error)),400
        if request.path.startswith('/admin/'):
            tab='tasks' if '/template' in request.path else 'people' if '/user' in request.path else 'settings'
            return render_template('admin.html',**admin_context(tab,error=str(error),draft=request.form.to_dict())),400
        return render_template('error.html',message=str(error),boot=boot('error')),400

    @app.errorhandler(LookupError)
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):return jsonify(ok=False,error='Det du s\u00f6kte finns inte l\u00e4ngre.'),404
        return render_template('error.html',message='Det du s\u00f6kte finns inte l\u00e4ngre.',boot=boot('error')),404

    @app.errorhandler(sqlite3.OperationalError)
    def database_busy(error):
        app.logger.exception('Database error')
        if request.path.startswith('/api/'):return jsonify(ok=False,error='Databasen \u00e4r upptagen. Prova igen om en stund.'),503
        return render_template('error.html',message='Det gick inte att spara just nu. Prova igen om en stund.',boot=boot('error')),503

    @app.errorhandler(500)
    def server_error(error):
        return render_template('error.html',message='N\u00e5got gick fel. Dina data finns kvar. Kontrollera tj\u00e4nstens logg.',boot=boot('error')),500

    # FAMILJ_REMOTE_5_3
    from familj.remote_access import register_remote
    register_remote(app, store, boot)

    # FAMILJ_HOMEVOICE_5_4
    from familj.voice54 import register_voice
    from familj.mobile54 import register_mobile
    register_voice(app, store, boot)
    register_mobile(app, store, boot)

    if start_workers:
        def worker():
            while True:
                try:store.generate(); weather.snapshot()
                except Exception:app.logger.exception('Background maintenance failed')
                time.sleep(30)
        threading.Thread(target=worker,name='household-maintenance',daemon=True).start()
    return app


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true',help='Smoke-test routes in a temporary empty database, without network.')
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','5000')))
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(Path(tmp),start_workers=False,testing=True)
            with app.test_client() as c:
                for path in ('/','/admin','/health','/api/state','/api/weather','/admin/login'):
                    response=c.get(path)
                    if response.status_code!=200:raise RuntimeError(f'{path}: {response.status_code}')
            print('Flask routes/templates OK; production data untouched.')
        return
    from waitress import serve
    app=create_app()
    logging.info('Familj Display %s on 0.0.0.0:%s',VERSION,args.port)
    serve(app,host='0.0.0.0',port=args.port,threads=4,channel_timeout=30,ident='FamiljDisplay')


if __name__=='__main__': main()
