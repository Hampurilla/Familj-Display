"""Non-blocking weather cache. The dashboard never waits on an external API."""
from __future__ import annotations
import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LOG = logging.getLogger(__name__)
WEEKDAYS = ['M\u00e5n','Tis','Ons','Tor','Fre','L\u00f6r','S\u00f6n']


def condition(code, day=True):
    if code == 0: return ('sun' if day else 'moon', 'Klart')
    if code in (1, 2): return ('partly', 'L\u00e4tt molnighet')
    if code == 3: return ('cloud', 'Molnigt')
    if code in (45,48): return ('fog', 'Dimma')
    if code in (51,53,55,56,57): return ('rain', 'Duggregn')
    if code in (61,63,65,66,67,80,81,82): return ('rain', 'Regn')
    if code in (71,73,75,77,85,86): return ('snow', 'Sn\u00f6')
    if code in (95,96,99): return ('storm', '\u00c5ska')
    return ('cloud', 'V\u00e4der')


def get_json(url):
    request = Request(url, headers={'User-Agent':'FamiljDisplay/5.0 (personal home dashboard)'})
    with urlopen(request, timeout=4) as response:
        if response.status != 200: raise OSError('Weather service error')
        return json.loads(response.read(1024 * 1024))


class Weather:
    def __init__(self, store):
        self.store=store
        self.lock=threading.Lock()
        self.file=store.data/'weather-cache.json'
        self.data=None
        self.key=None
        self.fetched=0
        self.attempt=0
        self.busy=False
        self.failed=False
        try:
            saved=json.loads(self.file.read_text('utf-8'))
            self.key=tuple(saved['key']); self.data=saved['data']; self.fetched=saved['fetched']
        except (OSError,ValueError,KeyError,TypeError): pass

    def snapshot(self, refresh=True):
        settings=self.store.settings()
        key=(settings['weather_name'],settings['weather_lat'],settings['weather_lon'])
        with self.lock:
            if refresh and not self.busy and (time.time()-self.attempt>60) and (key!=self.key or time.time()-self.fetched>900):
                self.busy=True; self.attempt=time.time()
                threading.Thread(target=self._refresh,args=(key,),daemon=True,name='weather-cache').start()
            if self.data and self.key==key:
                return self.data | dict(ok=True,stale=self.failed or time.time()-self.fetched>1800,fetched_at=self.fetched)
            return dict(ok=False,name=key[0],loading=self.busy,stale=False)

    def _refresh(self,key):
        try:
            params=urlencode(dict(latitude=key[1],longitude=key[2],timezone='Europe/Stockholm',
                current='temperature_2m,apparent_temperature,weather_code,wind_speed_10m,is_day',
                daily='temperature_2m_max,temperature_2m_min,weather_code',wind_speed_unit='ms',forecast_days=4))
            raw=get_json('https://api.open-meteo.com/v1/forecast?'+params)
            c=raw['current']; daily=raw['daily']; icon,text=condition(c['weather_code'],bool(c.get('is_day',1)))
            days=[]
            for i,day in enumerate(daily['time'][:4]):
                d=datetime.strptime(day,'%Y-%m-%d').date()
                kind,_=condition(daily['weather_code'][i])
                days.append(dict(date=day,label='Idag' if i==0 else WEEKDAYS[d.weekday()],icon=kind,
                                 high=round(daily['temperature_2m_max'][i]),low=round(daily['temperature_2m_min'][i])))
            data=dict(name=key[0],temp=round(c['temperature_2m']),feels=round(c['apparent_temperature']),
                      wind=round(c['wind_speed_10m'],1),icon=icon,text=text,days=days,observed=c['time'])
            fetched=time.time()
            temp=self.file.with_suffix('.tmp')
            temp.write_text(json.dumps(dict(key=key,data=data,fetched=fetched)),encoding='utf-8')
            temp.replace(self.file)
            with self.lock: self.data=data; self.key=key; self.fetched=fetched; self.failed=False
        except Exception:
            LOG.warning('Weather unavailable; serving the last saved forecast, if any.')
            with self.lock: self.failed=True
        finally:
            with self.lock: self.busy=False


def locations(query):
    if not 2<=len(query)<=80: return []
    params=urlencode(dict(name=query,count=6,language='sv',format='json'))
    raw=get_json('https://geocoding-api.open-meteo.com/v1/search?'+params)
    return [dict(name=r['name'],region=r.get('admin1',''),country=r.get('country',''),
                 lat=r['latitude'],lon=r['longitude']) for r in raw.get('results',[])]
