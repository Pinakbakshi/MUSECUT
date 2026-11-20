from __future__ import annotations
import os, re, shutil, subprocess, tempfile, zipfile
from pathlib import Path
from typing import Optional
from starlette.background import BackgroundTask
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

app = FastAPI(title="MUSECUT Processing API", version="0.1.0")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET","POST"], allow_headers=["*"])
MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "500")) * 1024 * 1024
ROOT = Path(os.getenv("MUSECUT_WORKDIR", "/tmp/musecut"))
ROOT.mkdir(parents=True, exist_ok=True)

@app.get("/health")
def health():
    return {"ok": True, "service": "musecut-worker", "ffmpeg": shutil.which("ffmpeg") is not None}

def parse_srt(data: str):
    cues=[]
    for block in re.split(r"\n\s*\n", data.replace("\r","").strip()):
        lines=block.splitlines()
        timing=next((x for x in lines if "-->" in x),None)
        if not timing: continue
        a,b=[x.strip().split(" ")[0] for x in timing.split("-->")]
        def sec(t):
            h,m,s=t.replace(",",".").split(":")
            return int(h)*3600+int(m)*60+float(s)
        text=" ".join(lines[lines.index(timing)+1:]).strip()
        if text: cues.append((sec(a),sec(b),re.sub(r"<[^>]+>","",text)))
    return cues

def parse_lrc(data: str):
    cues=[]
    for line in data.splitlines():
        m=re.match(r"\[(\d{2}):(\d{2})(?:\.(\d{1,3}))?\](.*)",line)
        if m:
            t=int(m.group(1))*60+int(m.group(2))+float("0."+((m.group(3) or "0").ljust(3,"0")))
            if m.group(4).strip(): cues.append((t,t+4,m.group(4).strip()))
    return cues

def ass_time(t: float):
    cs=max(0,int(round(t*100)))
    return f"{cs//360000}:{(cs//6000)%60:02d}:{(cs//100)%60:02d}.{cs%100:02d}"

@app.post("/api/generate")
async def generate(video: UploadFile=File(...), lyrics: str=Form(""), clip_count: int=Form(5), timed_lyrics: Optional[UploadFile]=File(None)):
    suffix=Path(video.filename or "video.mp4").suffix.lower()
    if suffix not in {".mp4",".mov",".webm",".m4v"}: raise HTTPException(400,"Upload an MP4, MOV or WebM video.")
    if not timed_lyrics: raise HTTPException(422,"This first renderer needs timestamped .srt or .lrc lyrics. Plain-text forced alignment is a planned next milestone.")
    ext=Path(timed_lyrics.filename or "").suffix.lower()
    if ext not in {".srt",".lrc"}: raise HTTPException(400,"Timed lyrics must be an .srt or .lrc file.")
    work=Path(tempfile.mkdtemp(prefix="job-",dir=ROOT))
    try:
        source=work/("source"+suffix); size=0
        with source.open("wb") as f:
            while chunk:=await video.read(1024*1024):
                size+=len(chunk)
                if size>MAX_BYTES: raise HTTPException(413,"Video exceeds configured upload limit.")
                f.write(chunk)
        timed=(await timed_lyrics.read()).decode("utf-8-sig",errors="replace")
        cues=parse_lrc(timed) if ext==".lrc" else parse_srt(timed)
        if not cues: raise HTTPException(422,"No timed lyric cues found. Check the SRT/LRC format.")
        probe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(source)],capture_output=True,text=True)
        if probe.returncode: raise HTTPException(422,"Could not read uploaded video.")
        duration=float(probe.stdout.strip())
        windows=[]
        for i in range(len(cues)):
            start=max(0,cues[i][0]-2); end=min(duration,cues[min(len(cues)-1,i+5)][1]+2)
            if 12<=end-start<=48 and all(abs(start-x[0])>=8 for x in windows): windows.append((start,end))
        if not windows:
            start=max(0,min(c[0] for c in cues)-2); windows=[(start,min(duration,start+min(30,duration)))]
        windows=windows[:max(3,min(10,clip_count))]
        rendered=[]
        for idx,(start,end) in enumerate(windows,1):
            ass=work/f"captions-{idx}.ass"; events=[]
            for a,b,line in cues:
                if b<start or a>end: continue
                safe=line.replace("{","\\{").replace("}","\\}")
                events.append(f"Dialogue: 0,{ass_time(max(0,a-start))},{ass_time(max(0,min(end,b)-start))},Lyric,,0,0,0,,{safe}")
            header="[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Lyric,Arial,68,&H00FFFFFF,&H0000D7FF,&H00101018,&H80000000,1,0,1,4,2,2,90,90,250,1\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
            ass.write_text(header+"\n".join(events)+"\n",encoding="utf-8")
            out=work/f"musecut-reel-{idx:02d}.mp4"
            vf=f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,subtitles={ass.as_posix()}"
            cmd=["ffmpeg","-y","-ss",str(start),"-i",str(source),"-t",str(end-start),"-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","21","-c:a","aac","-b:a","192k","-movflags","+faststart",str(out)]
            run=subprocess.run(cmd,capture_output=True,text=True)
            if run.returncode: raise HTTPException(500,"FFmpeg render failed: "+run.stderr[-500:])
            rendered.append(out)
        archive=work/"musecut-reels.zip"
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
            for p in rendered: z.write(p,p.name)
        return FileResponse(archive,media_type="application/zip",filename="musecut-reels.zip",background=BackgroundTask(shutil.rmtree,work,ignore_errors=True))
    except HTTPException:
        shutil.rmtree(work,ignore_errors=True); raise
    except Exception as exc:
        shutil.rmtree(work,ignore_errors=True); raise HTTPException(500,f"Generation failed: {type(exc).__name__}: {exc}")
