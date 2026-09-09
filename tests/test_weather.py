from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
import json,tempfile,time,unittest
from familj.store import Store
from familj.weather import Weather,condition

class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name));self.w=Weather(self.s)
        self.key=tuple(self.s.settings()[k] for k in ['weather_name','weather_lat','weather_lon'])
    def tearDown(self):self.tmp.cleanup()
    def raw(self):
        return dict(current=dict(temperature_2m=17.4,apparent_temperature=16.1,weather_code=2,wind_speed_10m=2.2,is_day=1,time='2026-09-09T18:00'),daily=dict(time=['2026-09-09','2026-09-10'],weather_code=[2,0],temperature_2m_max=[18.1,19.1],temperature_2m_min=[10.1,11.2]))
    def test_initial_offline_returns_placeholder(self):
        self.assertFalse(self.w.snapshot(refresh=False)['ok'])
    def test_success_cached_on_disk(self):
        with patch('familj.weather.get_json',return_value=self.raw()):self.w._refresh(self.key)
        result=self.w.snapshot(False)
        self.assertEqual(result['temp'],17);self.assertEqual(result['wind'],2.2)
        restored=Weather(self.s).snapshot(False);self.assertTrue(restored['ok']);self.assertEqual(restored['temp'],17)
    def test_failure_keeps_previous_data_marked_stale(self):
        with patch('familj.weather.get_json',return_value=self.raw()):self.w._refresh(self.key)
        with patch('familj.weather.get_json',side_effect=OSError('offline')):self.w._refresh(self.key)
        result=self.w.snapshot(False);self.assertTrue(result['ok']);self.assertTrue(result['stale']);self.assertEqual(result['temp'],17)
    def test_location_change_does_not_show_other_location(self):
        with patch('familj.weather.get_json',return_value=self.raw()):self.w._refresh(self.key)
        self.s.save_settings({'weather_name':'Test','weather_lat':'60'})
        self.assertFalse(self.w.snapshot(False)['ok'])
    def test_corrupt_cache_is_ignored(self):
        self.w.file.write_text('{bad data')
        self.assertFalse(Weather(self.s).snapshot(False)['ok'])
    def test_weather_conditions(self):
        for code,icon in [(0,'sun'),(3,'cloud'),(45,'fog'),(65,'rain'),(75,'snow'),(95,'storm')]:self.assertEqual(condition(code)[0],icon)
        self.assertEqual(condition(0,False)[0],'moon')
