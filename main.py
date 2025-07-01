
# main.py
import os
import re
import aiofiles
import asyncio
from fastapi import FastAPI, File, UploadFile, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from cohere import Client as CohereClient
from pathlib import Path

# == Config ==
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

COHERE_API_KEY = os.getenv("COHERE_API_KEY", "your-cohere-api-key")
co = CohereClient(COHERE_API_KEY)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

# == Format Fix Logic ==
def is_valid_format(line):
    return re.match(r"^[^:]+:[^\s]+ \| .*uid =", line) is not None

def chunk_lines(text, chunk_size=15):
    lines = text.strip().splitlines()
    for i in range(0, len(lines), chunk_size):
        yield lines[i:i + chunk_size]

async def fix_with_cohere(chunks):
    fixed_lines = []
    for chunk in chunks:
        prompt = (
            "Fix the following game account lines into this format:\n"
            "'email:password | uid = 123456 (1234) | name = Player | max_rank = Epic | level = 80 | country = id | is_banned = False | credits = your_note'\n"
            "Only return the fixed lines without any explanation or extra text.\n\n"
            + "\n".join(chunk)
        )
        response = co.chat(message=prompt)
        await asyncio.sleep(1.2)
        for line in response.text.strip().splitlines():
            if is_valid_format(line):
                fixed_lines.append(line)
    return fixed_lines

# == Routes ==
@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    text = contents.decode("utf-8")
    lines = text.strip().splitlines()

    valid = [l for l in lines if is_valid_format(l)]
    invalid = [l for l in lines if not is_valid_format(l)]

    if invalid:
        chunks = list(chunk_lines("\n".join(invalid)))
        fixed = await fix_with_cohere(chunks)
        all_lines = valid + fixed
    else:
        all_lines = valid

    output_path = os.path.join(UPLOAD_DIR, f"fixed_{file.filename}")
    async with aiofiles.open(output_path, "w") as f:
        await f.write("\n".join(all_lines))

    return FileResponse(output_path, filename=f"fixed_{file.filename}", media_type="text/plain")
