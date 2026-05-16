import os
import re
from datetime import date as date_cls, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .highlights import get_highlighter
from .storage import get_store

_APP_DIR = Path(__file__).resolve().parent

app = FastAPI(title="birbESP", version="0.1.0")
app.mount("/static", StaticFiles(directory=_APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=_APP_DIR / "templates")

GALLERY_PAGE_SIZE = 60
_FRAME_RE = re.compile(r"^\d{4}/\d{2}/\d{2}/\d{6}_\d{3}\.jpg$")


def _stream_url() -> str | None:
    return os.environ.get("ESP32_STREAM_URL") or None


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/upload")
async def upload(image: UploadFile = File(...)) -> JSONResponse:
    if image.content_type not in {"image/jpeg", "application/octet-stream", None}:
        raise HTTPException(415, f"Unsupported content type: {image.content_type}")
    payload = await image.read()
    if not payload:
        raise HTTPException(400, "Empty upload")
    row = get_store().save_frame(payload, ts=datetime.now(timezone.utc))
    diff_score, is_highlight = get_highlighter().score(payload)
    get_store().mark_highlight(row["filename"], diff_score, is_highlight)
    return JSONResponse(
        {"ok": True, **row, "diff_score": diff_score, "is_highlight": is_highlight}
    )


@app.get("/api/latest.jpg")
def latest_jpg() -> FileResponse:
    row = get_store().latest()
    if row is None:
        raise HTTPException(404, "No frames yet")
    return FileResponse(
        get_store().absolute(row["filename"]),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/frames/{path:path}")
def serve_frame(path: str) -> FileResponse:
    if not _FRAME_RE.match(path):
        raise HTTPException(404, "Not found")
    p = get_store().absolute(path)
    if not p.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(
        p,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    store = get_store()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "active": "home",
            "latest": store.latest(),
            "recent_highlights": store.recent(limit=8, highlights_only=True),
        },
    )


@app.get("/live", response_class=HTMLResponse)
def live(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "live.html",
        {"active": "live", "stream_url": _stream_url()},
    )


@app.get("/highlights", response_class=HTMLResponse)
def highlights_page(request: Request, date: str | None = None) -> HTMLResponse:
    store = get_store()
    if date is None:
        dates = store.dates_with_frames()
        date = dates[0] if dates else date_cls.today().isoformat()
    frames = store.list_by_date(date, highlights_only=True)
    return templates.TemplateResponse(
        request,
        "highlights.html",
        {"active": "highlights", "date": date, "frames": frames},
    )


@app.get("/gallery", response_class=HTMLResponse)
def gallery_page(
    request: Request,
    date: str | None = None,
    page: int = 0,
) -> HTMLResponse:
    store = get_store()
    if date is None:
        dates = store.dates_with_frames()
        date = dates[0] if dates else date_cls.today().isoformat()
    all_frames = store.list_by_date(date)
    page_count = max(1, (len(all_frames) + GALLERY_PAGE_SIZE - 1) // GALLERY_PAGE_SIZE)
    page = max(0, min(page, page_count - 1))
    start = page * GALLERY_PAGE_SIZE
    frames = all_frames[start : start + GALLERY_PAGE_SIZE]
    return templates.TemplateResponse(
        request,
        "gallery.html",
        {
            "active": "gallery",
            "date": date,
            "frames": frames,
            "page": page,
            "page_count": page_count,
            "prev_page": page - 1 if page > 0 else None,
            "next_page": page + 1 if page + 1 < page_count else None,
        },
    )
