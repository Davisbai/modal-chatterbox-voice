"""Private, on-demand Mandarin voice API. Deploy only after reviewing costs."""
import io
import os
import secrets
from pathlib import Path
import modal

app = modal.App("private-chatterbox-zh")
volume = modal.Volume.from_name("private-chatterbox-voice", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.11")
         .apt_install("ffmpeg")
         .pip_install("chatterbox-tts", "fastapi", "pydantic", "soundfile", "python-multipart"))
secret = modal.Secret.from_name("private-chatterbox-api", required_keys=["VOICE_API_KEY"])
VOICE_PATH = Path("/private/voice.wav")

@app.function(image=image, volumes={"/private": volume}, secrets=[secret], timeout=180)
def save_voice(wav_bytes: bytes):
    import soundfile as sf
    if not 1000 < len(wav_bytes) < 15_000_000:
        raise ValueError("WAV must be 1 KB–15 MB")
    info = sf.info(io.BytesIO(wav_bytes))
    if info.format != "WAV" or not 3 <= info.duration <= 60:
        raise ValueError("Provide WAV audio between 3 and 60 seconds")
    VOICE_PATH.write_bytes(wav_bytes)
    os.chmod(VOICE_PATH, 0o600)
    volume.commit()
    return {"saved": True, "duration_seconds": round(info.duration, 2)}

@app.cls(image=image, gpu="L4", volumes={"/private": volume}, secrets=[secret],
         min_containers=0, max_containers=1, scaledown_window=60, timeout=600)
class Speech:
    @modal.enter()
    def load(self):
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        self.model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")

    @modal.method()
    def synthesize(self, text: str):
        import soundfile as sf
        volume.reload()
        if not VOICE_PATH.is_file():
            raise ValueError("Voice reference missing; upload with upload_voice.py")
        wav = self.model.generate(text, language_id="zh", audio_prompt_path=str(VOICE_PATH))
        out = io.BytesIO()
        sf.write(out, wav.squeeze().detach().cpu().numpy(), self.model.sr, format="WAV")
        return out.getvalue()

@app.function(image=modal.Image.debian_slim(python_version="3.11").pip_install("fastapi", "pydantic"),
              secrets=[secret], timeout=600, min_containers=0, max_containers=1,
              scaledown_window=60)
@modal.asgi_app()
def api():
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.responses import Response
    from pydantic import BaseModel, Field
    web = FastAPI(title="Private Chinese Voice API", docs_url=None, redoc_url=None, openapi_url=None)

    class SpeakRequest(BaseModel):
        text: str = Field(min_length=1, max_length=250)

    @web.post("/v1/speech")
    def speak(payload: SpeakRequest, authorization: str | None = Header(default=None)):
        expected = "Bearer " + os.environ["VOICE_API_KEY"]
        if not authorization or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Unauthorized")
        try:
            wav = Speech().synthesize.remote(payload.text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response(wav, media_type="audio/wav", headers={"Cache-Control": "no-store"})
    return web
