"""Template/UI fixture, never imported by the production application."""
import json
from datetime import date,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from jinja2 import Environment,FileSystemLoader,StrictUndefined
from familj.store import Store,RECURRENCES,ACCENTS
from familj.badges import BADGES,RARITIES
ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,9,9,18,41,tzinfo=ZoneInfo('Europe/Stockholm'))

def seed(store):
    people=[('Mamma','sage',1),('Hampus','clay',1),('Pappa','blue',1),('Viktor','honey',.5)]
    ids=[store.save_user(n,c,w) for n,c,w in people]
    jobs=[(ids[0],'Plocka undan i k\u00f6ket',3,False),(ids[0],'Vika handdukar',2,True),
          (ids[1],'L\u00e4gg undan verktygen',3,False),(ids[1],'T\u00f6m diskmaskinen',2,True),(ids[1],'Vattna v\u00e4xterna',2,True),
          (ids[2],'Ta ut \u00e5tervinningen',3,False),(ids[2],'Dammsug hallen',4,False),
          (ids[3],'L\u00e4gg leksaker i l\u00e5dan',1,False),(ids[3],'Duka bordet',2,True)]
    for uid,title,points,completed in jobs:
        tid=store.save_template(dict(title=title,difficulty=points,start_date='2026-09-09',recurrence='daily',assignment_mode='fixed',fixed_user_id=uid,eligible_ids=[],notes='B\u00f6rja med en liten del.'))
        if completed:
            with store.db() as c:task=c.execute('SELECT id FROM tasks WHERE template_id=? ORDER BY due_date LIMIT 1',(tid,)).fetchone()[0]
            store.set_completed(task,True)
    store.save_settings({'house_note':'Ikv\u00e4ll tar vi det lugnt. Middag tillsammans klockan 19.','family_goal':'P\u00e5 fredag blir det filmkv\u00e4ll.'})
    with store.db(True) as c:
        for bid in [1,2,3,8,10,17,40,85,98,108,121]:
            c.execute('INSERT OR IGNORE INTO user_badges(user_id,badge_id,unlock_count) VALUES(1,?,1)',(bid,))
    return ids


def weather_fixture():
    return dict(ok=True,name='Bor\u00e5s',temp=18,feels=17,wind=2.4,icon='partly',text='L\u00e4tt molnighet',stale=False,fetched_at=NOW.timestamp(),
        days=[dict(date='2026-09-09',label='Idag',icon='partly',high=19,low=12),dict(date='2026-09-10',label='Tor',icon='sun',high=21,low=11),dict(date='2026-09-11',label='Fre',icon='rain',high=17,low=12),dict(date='2026-09-12',label='L\u00f6r',icon='partly',high=19,low=10)])


def environment(store):
    env=Environment(loader=FileSystemLoader(ROOT/'templates'),autoescape=True,undefined=StrictUndefined)
    def svdate(v):
        if not v:return ''
        d=date.fromisoformat(v[:10]);today=store.now().date()
        if d==today:return 'Idag'
        if d==today+timedelta(days=1):return 'Imorgon'
        return f'{d.day} '+['jan','feb','mars','apr','maj','juni','juli','aug','sep','okt','nov','dec'][d.month-1]
    env.filters['svdate']=svdate
    env.globals.update(asset=lambda s:'/static/'+s+'?v=preview',csrf=lambda:'preview-token',
        settings=store.settings(),version='5.0.0',release='preview',rarities=RARITIES,recurrences=RECURRENCES,
        accents=ACCENTS,badge_total=len(BADGES),server_now=store.now(),get_flashed_messages=lambda:[])
    return env


def context(store,view,uid=None,tab='overview'):
    boot=dict(view=view,user_id=uid,release='preview',version=store.version(),now=store.now().isoformat(),settings=store.settings(),csrf='preview-token',poll_ms=3000)
    if view=='home':data=store.dashboard()
    elif view=='user':data=store.profile(uid)
    elif view=='badges':data=store.collection(uid)
    elif view=='admin':
        data=dict(users=store.users(),all_users=store.users(False),templates=store.templates(),today=store.now().date().isoformat(),
            active_tab=tab,overview=store.dashboard(),edit=None,error=None,draft={},
            form=dict(title='',notes='',difficulty=3,recurrence='once',start_date=store.now().date().isoformat(),end_date='',assignment_mode='auto',fixed_user_id='',eligible_ids='[]',allowed=[]))
    elif view=='login':data=dict(error=None)
    else:data=dict(message='Testsida')
    return data|dict(boot=boot)
