import librosa
import numpy as np
import soundfile as sf
from scipy import signal


def load_audio(path, sr=None):
    y, sample_rate = librosa.load(path, sr=sr, mono=True)
    if y.size == 0:
        raise ValueError("Audio file is empty.")
    return y.astype(np.float32), sample_rate


def write_audio(y, sr, output):
    y = np.nan_to_num(np.asarray(y, dtype=np.float32))
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 1.0:
        y = y / peak * 0.99
    sf.write(output, y, sr, subtype="PCM_16")
    return output


def trim_audio(src, start, end, output):
    y, sr = load_audio(src); a=max(0,int(start*sr)); b=min(len(y),int(end*sr))
    if b<=a: raise ValueError("End time must be greater than start time.")
    return write_audio(y[a:b],sr,output)


def normalize_audio(src, output, target_db=-1.0):
    y,sr=load_audio(src); peak=float(np.max(np.abs(y)))
    if peak: y*=10**(target_db/20)/peak
    return write_audio(y,sr,output)


def fade_audio(src, output, fade_in=0.0, fade_out=0.0):
    y,sr=load_audio(src)
    if fade_in>0:
        n=min(len(y),max(1,int(fade_in*sr))); y[:n]*=np.linspace(0,1,n,dtype=np.float32)
    if fade_out>0:
        n=min(len(y),max(1,int(fade_out*sr))); y[-n:]*=np.linspace(1,0,n,dtype=np.float32)
    return write_audio(y,sr,output)


def reverse_audio(src, output):
    y,sr=load_audio(src); return write_audio(y[::-1],sr,output)


def speed_audio(src, output, rate):
    if not .25<=rate<=4: raise ValueError("Speed must be between 0.25x and 4x.")
    y,sr=load_audio(src); return write_audio(librosa.effects.time_stretch(y,rate=rate),sr,output)


def pitch_audio(src, output, semitones):
    if not -12<=semitones<=12: raise ValueError("Pitch shift must be between -12 and +12 semitones.")
    y,sr=load_audio(src); return write_audio(librosa.effects.pitch_shift(y,sr=sr,n_steps=semitones),sr,output)


def remove_silence(src, output, top_db=32.0):
    y,sr=load_audio(src); result,_=librosa.effects.trim(y,top_db=top_db); return write_audio(result,sr,output)


def eq_audio(src, output, low_db=2.0, mid_db=1.5, high_db=2.0):
    y,sr=load_audio(src); result=y.copy()
    for freq,q,gain in ((180,.9,low_db),(1800,1,mid_db),(5500,.9,high_db)):
        if freq>=sr/2: continue
        A=10**(gain/40); w=2*np.pi*freq/sr; alpha=np.sin(w)/(2*q)
        b=np.array([1+alpha*A,-2*np.cos(w),1-alpha*A]); a=np.array([1+alpha/A,-2*np.cos(w),1-alpha/A])
        result=signal.lfilter(b/a[0],a/a[0],result).astype(np.float32)
    return write_audio(result,sr,output)


def compress_audio(src, output, threshold_db=-18.0, ratio=3.0):
    if not 1<=ratio<=20: raise ValueError("Compression ratio must be between 1 and 20.")
    y,sr=load_audio(src); threshold=10**(threshold_db/20); env=np.abs(y)
    attack=np.exp(-1/max(1,sr*.008)); release=np.exp(-1/max(1,sr*.08)); smooth=np.zeros_like(env); prev=0.
    for i,v in enumerate(env):
        c=attack if v>prev else release; prev=c*prev+(1-c)*v; smooth[i]=prev
    gain=np.ones_like(smooth); over=smooth>threshold; gain[over]=(threshold/np.maximum(smooth[over],1e-8))**(1-1/ratio)
    return write_audio(y*gain,sr,output)


def noise_reduce_audio(src, output, strength=.65):
    y,sr=load_audio(src); strength=float(np.clip(strength,0,1)); n_fft=1024; hop=256
    stft=librosa.stft(y,n_fft=n_fft,hop_length=hop); mag=np.abs(stft); phase=np.angle(stft)
    noise=np.median(mag[:,:max(1,min(8,mag.shape[1]))],axis=1,keepdims=True)
    clean=np.maximum(mag-noise*strength,0); result=librosa.istft(clean*np.exp(1j*phase),hop_length=hop,length=len(y))
    return write_audio(result,sr,output)


def reverb_audio(src, output, mix=.18, decay=.55):
    y,sr=load_audio(src); mix=float(np.clip(mix,0,1)); decay=float(np.clip(decay,.1,.95)); result=y.copy()
    for delay_s in (.035,.055,.085,.12):
        d=max(1,int(delay_s*sr)); wet=np.zeros_like(y)
        if d<len(y): wet[d:]=y[:-d]*(decay**(delay_s/.035))
        result+=wet*mix*.28
    return write_audio(result,sr,output)


def enhance_voice(src, output):
    y,sr=load_audio(src); high=min(9000,sr//2-100)
    if high<=70: return write_audio(y,sr,output)
    sos=signal.butter(4,[70,high],btype="bandpass",fs=sr,output="sos")
    return write_audio(np.tanh(signal.sosfiltfilt(sos,y)*1.25),sr,output)


def merge_audio(paths, output):
    if not paths: raise ValueError("At least one audio file is required.")
    clips=[]; rates=[]
    for p in paths: y,sr=load_audio(p); clips.append(y); rates.append(sr)
    target=rates[0]; converted=[c if sr==target else librosa.resample(c,orig_sr=sr,target_sr=target) for c,sr in zip(clips,rates)]
    return write_audio(np.concatenate(converted),target,output)


def mix_audio(paths, output, volumes=None):
    if not paths: raise ValueError("At least one audio file is required.")
    clips=[]; rates=[]
    for p in paths: y,sr=load_audio(p); clips.append(y); rates.append(sr)
    target=rates[0]; converted=[c if sr==target else librosa.resample(c,orig_sr=sr,target_sr=target) for c,sr in zip(clips,rates)]
    volumes=volumes or [1.0]*len(converted); result=np.zeros(max(map(len,converted)),dtype=np.float32)
    for y,v in zip(converted,volumes): result[:len(y)]+=y*float(v)
    return write_audio(result,target,output)


def audio_quality(path):
    y,sr=load_audio(path); frames=librosa.feature.rms(y=y)[0]; duration=len(y)/sr; peak=float(np.max(np.abs(y))); rms=float(np.sqrt(np.mean(y*y))); clipping=float(np.mean(np.abs(y)>=.999)); silence=float(np.mean(frames<max(float(np.max(frames))*.05,1e-5))); score=100
    if duration<1: score-=20
    if clipping>.01: score-=25
    if rms<.01: score-=20
    if silence>.5: score-=15
    return {"duration":round(duration,2),"sample_rate":sr,"peak":round(peak,4),"rms":round(rms,4),"clipping_ratio":round(clipping,4),"silence_ratio":round(silence,4),"quality_score":max(0,score),"notes":["High clipping detected." if clipping>.01 else "No significant clipping detected.","Very quiet recording." if rms<.01 else "Recording level is usable."]}
