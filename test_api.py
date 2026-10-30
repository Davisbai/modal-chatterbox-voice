import argparse
import os
import requests
p = argparse.ArgumentParser()
p.add_argument('--url', required=True)
p.add_argument('--text', default='大家好，這是我的中文 AI 聲音測試。')
p.add_argument('--output', default='narration.wav')
a = p.parse_args()
key = os.environ.get('VOICE_API_KEY')
if not key:
    p.error('Set VOICE_API_KEY first')
r = requests.post(a.url.rstrip('/')+'/v1/speech', json={'text':a.text}, headers={'Authorization':'Bearer '+key},timeout=600)
r.raise_for_status()
if not r.content.startswith(b'RIFF'):
    raise RuntimeError('Expected WAV response')
open(a.output,'wb').write(r.content)
print('Saved',a.output)
