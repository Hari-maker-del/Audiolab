from pathlib import Path
import shutil
import tempfile
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from audio import analyze, clean
from audio_tools import trim_audio, normalize_audio, fade_audio, reverse_audio, speed_audio, pitch_audio, remove_silence, enhance_voice, merge_audio, mix_audio, eq_audio, compress_audio, noise_reduce_audio, reverb_audio, audio_quality
from engine import IndicF5Engine, LANGS

app=FastAPI(title="Audiolab AI Audio Studio API",version="2.1.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])
BASE=Path(__file__).resolve().parent; REF=BASE/"reference"; OUT=BASE/"outputs"; REF.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True); engine=None

def get_engine():
    global engine
    if engine is None: engine=IndicF5Engine()
    return engine

def save_upload(upload):
    suffix=Path(upload.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False,suffix=suffix) as tmp: shutil.copyfileobj(upload.file,tmp); return Path(tmp.name)

def result_file(path): return FileResponse(path,media_type="audio/wav",filename=Path(path).name)

@app.get("/health")
def health(): return {"status":"ok","product":"Audiolab AI Audio Studio","version":"2.1.0","model":"IndicF5","device":get_engine().device if engine is not None else "not_loaded","languages":list(LANGS.keys()),"modules":["timeline","trim","normalize","fade","reverse","speed","pitch","silence","enhance","eq","compressor","noise-reduction","reverb","merge","mix","quality","voice-generation"]}

@app.post("/analyze")
async def analyze_endpoint(file:UploadFile=File(...)):
    path=save_upload(file)
    try:return analyze(str(path))
    finally:path.unlink(missing_ok=True)

@app.post("/quality")
async def quality_endpoint(file:UploadFile=File(...)):
    path=save_upload(file)
    try:return audio_quality(str(path))
    finally:path.unlink(missing_ok=True)

@app.post("/edit/{operation}")
async def edit_endpoint(operation:str,file:UploadFile=File(...),start:float=Form(0),end:float=Form(0),fade_in:float=Form(0),fade_out:float=Form(0),rate:float=Form(1),semitones:float=Form(0),strength:float=Form(.65),mix:float=Form(.18),decay:float=Form(.55),threshold_db:float=Form(-18),ratio:float=Form(3)):
    path=save_upload(file); output=OUT/f"audiolab_{operation}.wav"
    try:
        if operation=="trim": trim_audio(str(path),start,end if end>0 else 10**9,str(output))
        elif operation=="normalize": normalize_audio(str(path),str(output))
        elif operation=="fade": fade_audio(str(path),str(output),fade_in,fade_out)
        elif operation=="reverse": reverse_audio(str(path),str(output))
        elif operation=="speed": speed_audio(str(path),str(output),rate)
        elif operation=="pitch": pitch_audio(str(path),str(output),semitones)
        elif operation=="silence": remove_silence(str(path),str(output))
        elif operation=="enhance": enhance_voice(str(path),str(output))
        elif operation=="eq": eq_audio(str(path),str(output))
        elif operation=="compress": compress_audio(str(path),str(output),threshold_db,ratio)
        elif operation=="noise-reduce": noise_reduce_audio(str(path),str(output),strength)
        elif operation=="reverb": reverb_audio(str(path),str(output),mix,decay)
        else: raise HTTPException(status_code=400,detail="Unsupported operation.")
        return result_file(str(output))
    finally:path.unlink(missing_ok=True)

@app.post("/merge")
async def merge_endpoint(files:list[UploadFile]=File(...)):
    if len(files)<2: raise HTTPException(status_code=400,detail="Upload at least two audio files.")
    paths=[save_upload(f) for f in files]; output=OUT/"audiolab_merged.wav"
    try: merge_audio([str(p) for p in paths],str(output)); return result_file(str(output))
    finally:
        for p in paths:p.unlink(missing_ok=True)

@app.post("/mix")
async def mix_endpoint(files:list[UploadFile]=File(...),volumes:str=Form("")):
    if not files: raise HTTPException(status_code=400,detail="Upload at least one audio file.")
    paths=[save_upload(f) for f in files]; output=OUT/"audiolab_mix.wav"
    try:
        vals=[float(x) for x in volumes.split(",") if x.strip()] if volumes.strip() else None
        mix_audio([str(p) for p in paths],str(output),vals); return result_file(str(output))
    finally:
        for p in paths:p.unlink(missing_ok=True)

@app.post("/generate")
async def generate_endpoint(text:str=Form(...),language:str=Form("Tamil"),ref_text:str=Form(...),file:UploadFile=File(...)):
    if not text.strip(): return {"error":"Text is required."}
    if not ref_text.strip(): return {"error":"Exact reference transcript is required."}
    if language not in LANGS: return {"error":f"Unsupported language: {language}"}
    source=save_upload(file); cleaned=REF/"request_reference.wav"; output=OUT/"audiolab_generated.wav"
    try: clean(str(source),cleaned); return result_file(get_engine().generate(text,cleaned,ref_text,output))
    finally: source.unlink(missing_ok=True)

if __name__=="__main__":
    import uvicorn; uvicorn.run(app,host="127.0.0.1",port=8000)
