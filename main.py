from __future__ import annotations

import os
import re
import html
import json
import uuid
import base64
import mimetypes
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

BASE = Path(__file__).resolve().parent
OUT = BASE / "output"
UP = BASE / "uploads"
OUT.mkdir(exist_ok=True)
UP.mkdir(exist_ok=True)
load_dotenv(BASE / ".env")

APP_NAME = os.getenv("APP_NAME", "AI Trí Tuệ")
TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-5.6-luna")
TTS_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("TTS_VOICE", "marin")
MAX_FILES = int(os.getenv("MAX_FILES", "5"))
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "10"))

app = FastAPI(title=APP_NAME)
app.mount("/output", StaticFiles(directory=OUT), name="output")

INDEX = r'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Trí Tuệ</title>
<style>
:root{--bg:#f6f8fc;--card:#fff;--text:#101828;--muted:#667085;--line:#d0d5dd;--brand:#101828;--soft:#eef4ff}
*{box-sizing:border-box}body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:var(--bg);color:var(--text)}
.wrap{max-width:780px;margin:auto;padding:22px 14px 44px}.card{background:var(--card);border-radius:24px;padding:24px;box-shadow:0 10px 35px #10182812}
h1{font-size:42px;line-height:1.05;margin:0 0 12px}.lead{font-size:18px;line-height:1.5;margin:0 0 24px;color:#344054}
label{display:block;font-weight:700;margin:16px 0 7px}textarea,input,select{width:100%;padding:13px 14px;border:1px solid var(--line);border-radius:13px;background:#fff;font:inherit;color:var(--text)}
textarea{min-height:132px;resize:vertical}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.drop{border:1px dashed #98a2b3;border-radius:16px;padding:15px;background:#fafcff}.drop input{border:0;padding:4px 0}
.hint{font-size:13px;color:var(--muted);line-height:1.45;margin-top:5px}.files{display:flex;flex-wrap:wrap;gap:7px;margin-top:9px}.chip{font-size:12px;padding:5px 8px;background:#eef2f6;border-radius:999px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
button{width:100%;padding:15px;border:0;border-radius:14px;background:var(--brand);color:#fff;font-weight:800;font-size:17px;margin-top:18px;cursor:pointer}button:disabled{opacity:.55;cursor:wait}
.result{margin-top:20px;background:var(--soft);padding:17px;border-radius:16px;line-height:1.58;overflow-wrap:anywhere}.result h1,.result h2,.result h3{font-size:1.08rem;margin:14px 0 7px}.result ul,.result ol{padding-left:22px}.result p{margin:8px 0}.result a{color:#175cd3;font-weight:700}.status{color:#475467}
@media(max-width:600px){.wrap{padding:0}.card{border-radius:0;min-height:100vh;padding:22px 18px}h1{font-size:39px}.grid{grid-template-columns:1fr}}
</style>
</head>
<body><div class="wrap"><div class="card">
<h1>AI Trí Tuệ</h1>
<p class="lead">Nói điều bạn cần, hoặc gửi ảnh/tài liệu/link. AI sẽ tự hiểu ngữ cảnh và biến đầu vào thành kết quả dùng được.</p>
<form id="f">
<label>Nhu cầu</label>
<textarea name="task" placeholder="Ví dụ: Phân tích tài liệu này và rút ra 5 điều quan trọng. Hoặc chỉ gửi ảnh bìa sách, AI sẽ tự nhận diện và phân tích."></textarea>
<div class="grid">
<div><label>Đầu ra</label><select name="mode"><option value="research">Nghiên cứu / nội dung</option><option value="audio">Audio MP3</option><option value="video">Video MP4 9:16</option><option value="landing">Landing page</option></select></div>
<div><label>Link (không bắt buộc)</label><input name="links" type="url" inputmode="url" placeholder="https://..."></div>
</div>
<label>Ảnh & tài liệu</label>
<div class="drop">
<input id="attachments" type="file" name="attachments" multiple accept="image/*,.pdf,.txt,.md,.csv,.json,.docx,.pptx">
<div class="hint">Tối đa 5 tệp, mỗi tệp tối đa 10 MB. Hỗ trợ ảnh, PDF và các tài liệu phổ biến. Với video, tối đa 3 ảnh đầu sẽ được dùng làm cảnh; nếu không có ảnh, AI tự tạo ảnh minh họa.</div>
<div id="fileList" class="files"></div>
</div>
<button id="submitBtn">Tạo sản phẩm</button>
</form>
<div id="r" class="result" style="display:none"></div>
</div></div>
<script>
const f=document.getElementById('f'),r=document.getElementById('r'),btn=document.getElementById('submitBtn'),inp=document.getElementById('attachments'),fl=document.getElementById('fileList');
inp.onchange=()=>{fl.innerHTML='';[...inp.files].forEach(x=>{const s=document.createElement('span');s.className='chip';s.textContent=x.name;fl.appendChild(s)})};
function esc(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}
function md(s){let x=esc(s);x=x.replace(/^### (.*)$/gm,'<h3>$1</h3>').replace(/^## (.*)$/gm,'<h2>$1</h2>').replace(/^# (.*)$/gm,'<h1>$1</h1>');x=x.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>');x=x.replace(/^\s*[-•] (.*)$/gm,'<li>$1</li>');x=x.replace(/(?:<li>.*<\/li>\n?)+/g,m=>'<ul>'+m+'</ul>');x=x.replace(/^\s*\d+[.)]\s+(.*)$/gm,'<li>$1</li>');x=x.replace(/\n{2,}/g,'</p><p>').replace(/\n/g,'<br>');return '<p>'+x+'</p>'}
f.onsubmit=async(e)=>{e.preventDefault();r.style.display='block';r.innerHTML='<div class="status">Đang xử lý…</div>';btn.disabled=true;const d=new FormData(f);try{const x=await fetch('/generate',{method:'POST',body:d});const j=await x.json();if(!x.ok){r.textContent=j.detail||'Có lỗi';return}r.innerHTML='';if(j.message){const p=document.createElement('p');p.textContent=j.message;r.appendChild(p)}if(j.text){const box=document.createElement('div');box.innerHTML=md(j.text);r.appendChild(box)}if(j.url){const a=document.createElement('a');a.href=j.url;a.target='_blank';a.textContent='Mở / tải thành phẩm';r.appendChild(a)}}catch(err){r.textContent='Không kết nối được máy chủ. Hãy thử lại.'}finally{btn.disabled=false}};
</script></body></html>'''


@app.get("/", response_class=HTMLResponse)
def home():
    return INDEX


def client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(500, "Chưa cấu hình OPENAI_API_KEY trên server.")
    return OpenAI(api_key=key)


@dataclass
class Uploaded:
    name: str
    content_type: str
    data: bytes
    is_image: bool


def safe_name(name: str) -> str:
    name = Path(name or "upload.bin").name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:120] or "upload.bin"


async def collect_uploads(files: Optional[List[UploadFile]]) -> List[Uploaded]:
    if not files:
        return []
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"Tối đa {MAX_FILES} tệp mỗi lần.")
    out: List[Uploaded] = []
    max_bytes = MAX_FILE_MB * 1024 * 1024
    for f in files:
        data = await f.read()
        if len(data) > max_bytes:
            raise HTTPException(400, f"Tệp {f.filename} vượt quá {MAX_FILE_MB} MB.")
        name = safe_name(f.filename or "upload.bin")
        ctype = f.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
        is_image = ctype.startswith("image/") or Path(name).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        out.append(Uploaded(name=name, content_type=ctype, data=data, is_image=is_image))
    return out


def multimodal_content(task: str, links: str, uploads: List[Uploaded]) -> list[dict]:
    user_text = task.strip()
    if links.strip():
        user_text += ("\n\nLINK NGƯỜI DÙNG CUNG CẤP:\n" + links.strip())
    if not user_text and uploads:
        user_text = (
            "Tôi chỉ gửi tư liệu mà chưa mô tả chi tiết. Hãy chủ động nhận diện nội dung, "
            "giải thích nó là gì, rút ra các ý quan trọng và đề xuất bước tiếp theo hữu ích nhất."
        )
    content: list[dict] = [{"type": "input_text", "text": user_text or "Hãy giúp tôi xử lý nội dung này."}]
    for u in uploads:
        b64 = base64.b64encode(u.data).decode("ascii")
        if u.is_image:
            content.append({"type": "input_image", "image_url": f"data:{u.content_type};base64,{b64}", "detail": "auto"})
        else:
            content.append({"type": "input_file", "filename": u.name, "file_data": b64})
    return content


def text_generate(task: str, mode: str, uploads: List[Uploaded], links: str = "", extra_instruction: str = "") -> str:
    system = f'''Bạn là {APP_NAME}, trợ lý chuyên biến tri thức và nhu cầu mơ hồ thành kết quả dùng được.
Ngôn ngữ mặc định: tiếng Việt.

NGUYÊN TẮC ĐẦU VÀO:
- Người dùng có thể chỉ gửi ảnh, tài liệu hoặc link mà viết rất ít. Khi dữ liệu đủ để suy luận hợp lý, hãy chủ động nhận diện nội dung và làm phần việc còn lại, không bắt họ viết prompt dài.
- Nếu ảnh là bìa sách/sản phẩm/tài liệu: đọc những gì nhìn thấy, nhận diện đối tượng, rồi kết hợp nguồn công khai khi cần để giải thích chính xác.
- Nếu có tài liệu: ưu tiên nội dung tài liệu; phân biệt điều có trong tài liệu, thông tin nguồn công khai và phần tổng hợp/suy luận.
- Không giả vờ đã đọc phần tài liệu không được cung cấp hoặc không truy cập được.
- Nếu có link công khai, dùng web search khi cần để lấy thông tin mới hoặc kiểm chứng.

AN TOÀN & TRUNG THỰC:
- Không bịa giá, số điện thoại, địa chỉ, review, chính sách, bằng cấp, nguồn gốc, thành tích hay cam kết.
- Với sức khỏe/tài chính/pháp lý, tránh cam kết chắc chắn và nêu giới hạn phù hợp.

ĐẦU RA:
- mode=research: trả kết quả rõ, thực dụng, có cấu trúc; nếu đã nghiên cứu nguồn công khai thì nêu nguồn chính ở cuối.
- mode=audio/video: tạo lời đọc tự nhiên; mặc định 45–60 giây nếu người dùng không nói khác.
- mode=landing: nếu thiếu dữ liệu thương mại BẮT BUỘC mà chỉ chủ sản phẩm biết (giá nếu phải hiển thị, liên hệ, cách chốt đơn/đăng ký, địa chỉ nếu cần, chính sách thiết yếu), trả đúng:
NEED_INFO:\n- ...\n- ...
Nếu đủ dữ liệu, trả HTML hoàn chỉnh mobile-first, không markdown fence.
{extra_instruction}'''

    tools = []
    if re.search(r"https?://", (task or "") + " " + (links or ""), re.I) or uploads:
        tools = [{"type": "web_search"}]

    kwargs = {
        "model": TEXT_MODEL,
        "instructions": system,
        "input": [{"role": "user", "content": multimodal_content(task, links, uploads)}],
    }
    if tools:
        kwargs["tools"] = tools
    resp = client().responses.create(**kwargs)
    return resp.output_text.strip()


def tts(text: str, path: Path):
    chunks, cur = [], ""
    for sent in re.split(r"(?<=[.!?…])\s+", text):
        if len(cur) + len(sent) + 1 > 3500:
            if cur:
                chunks.append(cur)
            cur = sent
        else:
            cur = (cur + " " + sent).strip()
    if cur:
        chunks.append(cur)
    parts = []
    c = client()
    for i, ch in enumerate(chunks):
        p = path.with_name(path.stem + f"_{i}.mp3")
        with c.audio.speech.with_streaming_response.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=ch,
            instructions="Giọng Việt Nam tự nhiên, ấm áp, rõ chữ, nhịp vừa, có điểm nhấn nhưng không quảng cáo quá đà.",
        ) as response:
            response.stream_to_file(p)
        parts.append(p)
    if len(parts) == 1:
        parts[0].replace(path)
    else:
        lst = path.with_suffix(".txt")
        lst.write_text("\n".join([f"file '{p.as_posix()}'" for p in parts]), encoding="utf-8")
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(path)])
        for p in parts:
            p.unlink(missing_ok=True)
        lst.unlink(missing_ok=True)


def run(cmd: List[str]):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-3000:])


def duration(path: Path) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        capture_output=True,
        text=True,
    )
    return max(1.0, float(p.stdout.strip()))


def gen_image(prompt: str, path: Path):
    c = client()
    r = c.responses.create(
        model=TEXT_MODEL,
        input=f"Tạo một ảnh dọc 9:16 minh họa cho cảnh video sau. Không chèn chữ lên ảnh. Phong cách ảnh thật, sạch, tin cậy.\n{prompt}",
        tools=[{"type": "image_generation", "size": "1024x1536", "quality": "medium"}],
    )
    b64 = None
    for item in r.output:
        if getattr(item, "type", "") == "image_generation_call":
            b64 = getattr(item, "result", None)
            break
    if not b64:
        raise RuntimeError("Không nhận được ảnh từ image generation.")
    path.write_bytes(base64.b64decode(b64))


def prepare_image_bytes(data: bytes, dst: Path):
    import io
    im = Image.open(io.BytesIO(data)).convert("RGB")
    W, H = 1080, 1920
    scale = max(W / im.width, H / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh))
    left, top = (nw - W) // 2, (nh - H) // 2
    im = im.crop((left, top, left + W, top + H))
    im.save(dst, quality=92)


def make_srt(text: str, total: float, path: Path):
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()] or [text]

    def ts(v):
        ms = int((v - int(v)) * 1000)
        sec = int(v) % 60
        m = (int(v) // 60) % 60
        h = int(v) // 3600
        return f"{h:02}:{m:02}:{sec:02},{ms:03}"

    out = []
    for i, s in enumerate(sents):
        a, b = total * i / len(sents), total * (i + 1) / len(sents)
        out += [str(i + 1), f"{ts(a)} --> {ts(b)}", s, ""]
    path.write_text("\n".join(out), encoding="utf-8")


def render_video(script: str, images: List[Path], audio: Path, out: Path):
    dur = duration(audio)
    per = dur / len(images)
    clips = []
    for i, img in enumerate(images):
        clip = out.with_name(f"clip_{out.stem}_{i}.mp4")
        vf = "scale=1200:2134,crop=1080:1920:x='(iw-ow)/2':y='(ih-oh)/2',zoompan=z='min(zoom+0.0006,1.08)':d=1:s=1080x1920:fps=30,format=yuv420p"
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-t", f"{per:.3f}", "-vf", vf, "-r", "30", "-an", str(clip)])
        clips.append(clip)
    lst = out.with_name(out.stem + "_clips.txt")
    lst.write_text("\n".join([f"file '{p.as_posix()}'" for p in clips]), encoding="utf-8")
    visual = out.with_name(out.stem + "_visual.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(visual)])
    srt = out.with_suffix(".srt")
    make_srt(script, dur, srt)
    style = "FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,Alignment=2,MarginV=120"
    run(["ffmpeg", "-y", "-i", str(visual), "-i", str(audio), "-vf", f"subtitles={srt.as_posix()}:force_style='{style}'", "-c:v", "libx264", "-preset", "medium", "-c:a", "aac", "-shortest", str(out)])
    for p in clips + [visual, lst, srt]:
        p.unlink(missing_ok=True)


@app.post("/generate")
async def generate(
    task: str = Form(""),
    mode: str = Form("research"),
    links: str = Form(""),
    attachments: Optional[List[UploadFile]] = File(None),
):
    uploads = await collect_uploads(attachments)
    if not task.strip() and not links.strip() and not uploads:
        raise HTTPException(400, "Hãy nhập nhu cầu hoặc gửi ít nhất một ảnh/tài liệu/link.")

    uid = uuid.uuid4().hex[:10]
    try:
        text = text_generate(task, mode, uploads, links)

        if mode == "landing" and text.startswith("NEED_INFO:"):
            return JSONResponse({
                "message": "Cần thêm một số thông tin bắt buộc trước khi xuất landing page hoàn chỉnh.",
                "text": text.replace("NEED_INFO:", "").strip(),
            })

        if mode == "research":
            return {"text": text}

        if mode == "landing":
            p = OUT / f"landing_{uid}.html"
            p.write_text(text, encoding="utf-8")
            return {"message": "Landing page đã tạo.", "url": f"/output/{p.name}"}

        audio = OUT / f"audio_{uid}.mp3"
        tts(text, audio)
        if mode == "audio":
            return {"message": "Audio đã tạo.", "url": f"/output/{audio.name}", "text": text}

        if mode == "video":
            srcs: List[Path] = []
            image_uploads = [u for u in uploads if u.is_image][:3]
            for i, u in enumerate(image_uploads):
                norm = OUT / f"img_{uid}_{i}.jpg"
                prepare_image_bytes(u.data, norm)
                srcs.append(norm)

            if not srcs:
                scene_prompt = text_generate(
                    "Từ lời đọc sau, viết đúng 3 mô tả cảnh ảnh dọc, mỗi cảnh một dòng, không chữ trên ảnh, không logo giả, không claim.\n" + text,
                    "research",
                    [],
                    "",
                    extra_instruction="Chỉ trả đúng 3 dòng mô tả cảnh.",
                )
                scenes = [x.strip(" -1234567890.").strip() for x in scene_prompt.splitlines() if x.strip()][:3]
                while len(scenes) < 3:
                    scenes.append(text[:300])
                for i, s in enumerate(scenes):
                    p = OUT / f"img_{uid}_{i}.png"
                    gen_image(s, p)
                    srcs.append(p)

            out = OUT / f"video_{uid}.mp4"
            render_video(text, srcs, audio, out)
            return {
                "message": "Video đã render: ảnh + chuyển động nhẹ + voice + phụ đề.",
                "url": f"/output/{out.name}",
                "text": text,
            }

        raise HTTPException(400, "Mode không hợp lệ")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Lỗi xử lý: {e}")
