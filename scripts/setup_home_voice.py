#!/usr/bin/env python3
"""Explicit on-device setup; no passwords or network settings in Git."""
from __future__ import annotations
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def remote_module():
    spec=importlib.util.spec_from_file_location('remote_setup54',ROOT/'scripts/setup_remote.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def address():
    from familj.remote_access import StatusReader
    remote=remote_module()
    d=StatusReader(ROOT/'data').get(remote.pin_exists(ROOT))
    if not d.get('configured') or not d.get('url'):
        print(d['title']);print(d['detail'])
        print('No address guessed. Set admin PIN, then run: python3 scripts/setup_home_voice.py remote')
        return 1
    print('\nSAME APP ADDRESS FOR HOME WI-FI AND 4G/5G:\n\n'+d['url']+'\n')
    print('Open this exact address in Safari once and Add to Home Screen.')
    print('Tailscale must stay connected on the iPhone on BOTH Wi-Fi and cellular.')
    print('Test the NEW icon on both networks before removing the old local-IP icon.')
    print('This confirms configuration, not end-to-end mobile reachability.')
    return 0


def voice():
    if not sys.platform.startswith('linux'):
        raise RuntimeError('Run voice setup on Raspberry Pi, not Windows.')
    binary=shutil.which('espeak-ng')
    if not binary:
        print('Install the local Swedish voice with: sudo apt-get install -y espeak-ng')
        print('No cloud TTS, sound output changes, kiosk or startup changes.')
        if input('Install from your configured OS repositories? [y/N] ').strip().lower() not in ('y','yes','j','ja'):
            print('Cancelled. App is unchanged.');return 1
        subprocess.run(['sudo','apt-get','update'],check=True)
        subprocess.run(['sudo','apt-get','install','-y','espeak-ng'],check=True)
        binary=shutil.which('espeak-ng')
    if not binary:raise RuntimeError('eSpeak NG was not found after installation.')
    with tempfile.TemporaryDirectory(prefix='familj-voice-test-') as folder:
        wav=Path(folder)/'test.wav'
        subprocess.run([binary,'-v','sv','-s','155','-w',str(wav),'--stdin'],
            input='Hej! Nu kan jag l\u00e4sa dina uppgifter.'.encode(),check=True,timeout=20)
        with wave.open(str(wav),'rb') as w:
            if w.getnframes()<1:raise RuntimeError('No audio produced.')
    print('Swedish WAV generation OK. No audio has been played yet.')
    print('Select Headphones / Analog Stereo in the Pi desktop volume menu.')
    print('Then enable a profile at /admin/speech and test on the WALL DISPLAY.')
    print('The voice is lightweight and robotic, not a natural neural voice.')
    return 0


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['voice','remote','address','all']);a=p.parse_args()
    try:
        if a.action in ('voice','all'):
            code=voice()
            if code:return code
        if a.action in ('remote','all'):
            if not sys.platform.startswith('linux'):raise RuntimeError('Run remote setup on Raspberry Pi.')
            remote_module().enable(ROOT)
        if a.action in ('address','remote','all'):return address()
    except (Exception,KeyboardInterrupt) as e:
        print('STOP: '+str(e),file=sys.stderr);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
