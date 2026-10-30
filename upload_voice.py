"""Upload a WAV through an authenticated Modal function, never a public upload endpoint."""
import argparse
from pathlib import Path
import modal

p = argparse.ArgumentParser()
p.add_argument('wav', type=Path)
a = p.parse_args()
if a.wav.suffix.lower() != '.wav':
    p.error('Expected WAV')
fn = modal.Function.from_name('private-chatterbox-zh', 'save_voice')
print(fn.remote(a.wav.read_bytes()))
