from __future__ import annotations
import os, json, base64, uuid, subprocess, re, html
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "output"
UP = BASE / "uploads"
OUT.mkdir(exist_ok=True); UP.mkdir(exist_ok=True)
load_dotenv(BASE / ".env")
APP_NAME = os.getenv("APP_NAME", "AI Trí Tuệ")
TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-5.6-luna")
TTS_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("TTS_VOICE", "marin")

app = FastAPI(title=APP_NAME)
app.mount("/output", StaticFiles(directory=OUT), name="output")

INDEX = '''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI Trí Tuệ</title>
<style>body{font-family:system-ui;margin:0;background:#f7f8fb;color:#15171a}.wrap{max-width:760px;margin:auto;padding:28px}.card{background:white;border-radius:20px;padding:22px;box-shadow:0 8px 28px #00000012}h1{margin-top:0}textarea,input,select{width:100%;box-sizing:border-box;padding:13px;border:1px solid #ddd;border-radius:12px;margin:7px 0 14px}button{width:100%;padding:14px;border:0;border-radius:12px;background:#111827;color:white;font-weight:700}.hint{font-size:13px;color:#666}.result{white-space:pre-wrap;margin-top:18px;background:#eef2ff;padding:14px;border-radius:12px}a{color:#1d4ed8}</style></head><body><div class="wrap"><div class="card"><h1>AI Trí Tuệ</h1><p>Hãy nói điều bạn muốn làm. AI sẽ biến nhu cầu thành đầu ra dùng được.</p><form id="f"><label>Nhu cầu</label><textarea name="task" rows="5" placeholder="Ví dụ: Tạo video 45–60 giây để giới thiệu cuốn sách này..."></textarea><label>Đầu ra</label><select name="mode"><option value="research">Nghiên cứu / nội dung</option><option value="audio">Audio MP3</option><option value="video">Video MP4 9:16</option><option value="landing">Landing page</option></select><label>Ảnh (không bắt buộc, tối đa 3)</label><input type="file" name="images" accept="image/*" multiple><div class="hint">Nếu làm video mà không tải ảnh, AI sẽ tự tạo 3 ảnh minh họa.</div><button>Tạo sản phẩm</button></form><div id="r" class="result" style="display:none"></div></div></div><script>const f=document.getElementById('f'),r=document.getElementById('r');f.onsubmit=async(e)=>{e.preventDefault();r.style.display='block';r.textContent='Đang xử lý...';const d=new FormData(f);const x=await fetch('/generate',{method:'POST',body:d});const j=await x.json();if(!x.ok){r.textContent=j.detail||'Có lỗi';return}r.innerHTML='';if(j.message){const p=document.createElement('div');p.textContent=j.message;r.appendChild(p)}if(j.text){const p=document.createElement('pre');p.style.whiteSpace='pre-wrap';p.textContent=j.text;r.appendChild(p)}if(j.url){const a=document.createElement('a');a.href=j.url;a.target='_blank';a.textContent='Mở / tải thành phẩm';r.appendChild(a)}};</script></body></html>'''

@app.get("/", response_class=HTMLResponse)
def home(): return INDEX

def client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(500, "Chưa cấu hình OPENAI_API_KEY trên server.")
    return OpenAI(api_key=key)

def text_generate(task: str, mode: str) -> str:
    system = f'''Bạn là {APP_NAME}, trợ lý chuyên biến nhu cầu mơ hồ thành kết quả dùng được.
Ngôn ngữ mặc định: tiếng Việt. Không bịa dữ liệu thương mại, review, giá, số điện thoại, địa chỉ, chính sách, bằng cấp hay cam kết.
Nếu mode=video/audio, tạo lời đọc tự nhiên, rõ, phù hợp 45-60 giây nếu người dùng không nói khác.
Nếu mode=landing, trước tiên tự kiểm tra dữ liệu. Nếu thiếu dữ liệu BẮT BUỘC mà chỉ chủ sản phẩm biết (giá nếu cần hiển thị, liên hệ, cách chốt đơn/đăng ký, địa chỉ nếu cần, chính sách thiết yếu), hãy trả về đúng định dạng:
NEED_INFO:\n- ...\n- ...
Các phần tùy chọn như review/video/case study có thể để bổ sung sau nếu người dùng nói vậy. Nếu đủ dữ liệu, trả về HTML hoàn chỉnh, mobile-first, không markdown fence.
Nếu mode=research, trả kết quả súc tích, thực dụng.'''
    resp = client().responses.create(model=TEXT_MODEL, instructions=system, input=f"MODE={mode}\nYÊU CẦU:\n{task}")
    return resp.output_text.strip()

def tts(text: str, path: Path):
    # OpenAI speech endpoint currently limits input length; chunk and concatenate when needed.
    chunks=[]; cur=""
    for sent in re.split(r'(?<=[.!?…])\s+', text):
        if len(cur)+len(sent)+1>3500:
            chunks.append(cur); cur=sent
        else: cur=(cur+" "+sent).strip()
    if cur: chunks.append(cur)
    parts=[]
    c=client()
    for i,ch in enumerate(chunks):
        p=path.with_name(path.stem+f"_{i}.mp3")
        with c.audio.speech.with_streaming_response.create(model=TTS_MODEL, voice=TTS_VOICE, input=ch,
            instructions="Giọng Việt Nam tự nhiên, ấm áp, rõ chữ, nhịp vừa, có điểm nhấn nhưng không quảng cáo quá đà.") as response:
            response.stream_to_file(p)
        parts.append(p)
    if len(parts)==1: parts[0].replace(path)
    else:
        lst=path.with_suffix('.txt'); lst.write_text('\n'.join([f"file '{p.as_posix()}'" for p in parts]), encoding='utf-8')
        run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(path)])
        for p in parts: p.unlink(missing_ok=True)
        lst.unlink(missing_ok=True)

def run(cmd: List[str]):
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode!=0: raise RuntimeError(p.stderr[-3000:])

def duration(path: Path)->float:
    p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nokey=1:noprint_wrappers=1",str(path)],capture_output=True,text=True)
    return max(1.0,float(p.stdout.strip()))

def gen_image(prompt: str, path: Path):
    c=client()
    r=c.responses.create(model=TEXT_MODEL,input=f"Tạo một ảnh dọc 9:16 minh họa cho cảnh video sau. Không chèn chữ lên ảnh. Phong cách ảnh thật, sạch, tin cậy.\n{prompt}",tools=[{"type":"image_generation","size":"1024x1536","quality":"medium"}])
    b64=None
    for item in r.output:
        if getattr(item,"type","")=="image_generation_call":
            b64=getattr(item,"result",None); break
    if not b64: raise RuntimeError("Không nhận được ảnh từ image generation.")
    path.write_bytes(base64.b64decode(b64))

def prepare_image(src: Path, dst: Path):
    im=Image.open(src).convert("RGB")
    W,H=1080,1920
    scale=max(W/im.width,H/im.height); nw,nh=int(im.width*scale),int(im.height*scale)
    im=im.resize((nw,nh))
    left=(nw-W)//2; top=(nh-H)//2
    im=im.crop((left,top,left+W,top+H)); im.save(dst,quality=92)

def make_srt(text: str, total: float, path: Path):
    sents=[s.strip() for s in re.split(r'(?<=[.!?…])\s+', text) if s.strip()]
    if not sents: sents=[text]
    def ts(v):
        ms=int((v-int(v))*1000); sec=int(v)%60; m=(int(v)//60)%60; h=int(v)//3600
        return f"{h:02}:{m:02}:{sec:02},{ms:03}"
    out=[]
    for i,s in enumerate(sents):
        a=total*i/len(sents); b=total*(i+1)/len(sents)
        out += [str(i+1),f"{ts(a)} --> {ts(b)}",s,""]
    path.write_text('\n'.join(out),encoding='utf-8')

def render_video(script: str, images: List[Path], audio: Path, out: Path):
    dur=duration(audio); per=dur/len(images)
    clips=[]
    for i,img in enumerate(images):
        clip=out.with_name(f"clip_{out.stem}_{i}.mp4")
        # Subtle zoom gives motion without expensive generative video.
        vf="scale=1200:2134,crop=1080:1920:x='(iw-ow)/2':y='(ih-oh)/2',zoompan=z='min(zoom+0.0006,1.08)':d=1:s=1080x1920:fps=30,format=yuv420p"
        run(["ffmpeg","-y","-loop","1","-i",str(img),"-t",f"{per:.3f}","-vf",vf,"-r","30","-an",str(clip)])
        clips.append(clip)
    lst=out.with_name(out.stem+"_clips.txt")
    lst.write_text('\n'.join([f"file '{p.as_posix()}'" for p in clips]),encoding='utf-8')
    visual=out.with_name(out.stem+"_visual.mp4")
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(visual)])
    srt=out.with_suffix('.srt'); make_srt(script,dur,srt)
    style="FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,Alignment=2,MarginV=120"
    run(["ffmpeg","-y","-i",str(visual),"-i",str(audio),"-vf",f"subtitles={srt.as_posix()}:force_style='{style}'","-c:v","libx264","-preset","medium","-c:a","aac","-shortest",str(out)])
    for p in clips+[visual,lst,srt]: p.unlink(missing_ok=True)

@app.post("/generate")
async def generate(task: str=Form(...), mode: str=Form(...), images: Optional[List[UploadFile]]=File(None)):
    if not task.strip(): raise HTTPException(400,"Hãy nhập nhu cầu.")
    uid=uuid.uuid4().hex[:10]
    try:
        text=text_generate(task,mode)
        if mode=="landing" and text.startswith("NEED_INFO:"):
            return JSONResponse({"message":"Cần thêm một số thông tin bắt buộc trước khi xuất landing page hoàn chỉnh.","text":text.replace("NEED_INFO:","").strip()})
        if mode=="research": return {"text":text}
        if mode=="landing":
            p=OUT/f"landing_{uid}.html"; p.write_text(text,encoding='utf-8')
            return {"message":"Landing page đã tạo.","url":f"/output/{p.name}"}
        audio=OUT/f"audio_{uid}.mp3"; tts(text,audio)
        if mode=="audio": return {"message":"Audio thật đã tạo.","url":f"/output/{audio.name}","text":text}
        if mode=="video":
            srcs=[]
            if images:
                for i,u in enumerate(images[:3]):
                    ext=Path(u.filename or 'x.jpg').suffix or '.jpg'; raw=UP/f"{uid}_{i}{ext}"
                    raw.write_bytes(await u.read()); norm=OUT/f"img_{uid}_{i}.jpg"; prepare_image(raw,norm); srcs.append(norm)
            if not srcs:
                # derive three scenes from script, keeping product/logo claims out of generated visuals
                scene_prompt=text_generate("Từ lời đọc sau, viết đúng 3 mô tả cảnh ảnh dọc, mỗi cảnh một dòng, không chữ trên ảnh, không logo giả, không claim.\n"+text,"research")
                scenes=[x.strip(' -1234567890.').strip() for x in scene_prompt.splitlines() if x.strip()][:3]
                while len(scenes)<3: scenes.append(text[:300])
                for i,s in enumerate(scenes):
                    p=OUT/f"img_{uid}_{i}.png"; gen_image(s,p); srcs.append(p)
            out=OUT/f"video_{uid}.mp4"; render_video(text,srcs,audio,out)
            return {"message":"Video thật đã render: ảnh + chuyển động nhẹ + voice + phụ đề.","url":f"/output/{out.name}","text":text}
        raise HTTPException(400,"Mode không hợp lệ")
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(500,f"Lỗi xử lý: {e}")
