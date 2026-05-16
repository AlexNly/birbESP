import asyncio
import contextlib
import io
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image

from .highlights import get_highlighter
from .storage import get_store, local_tz

_APP_DIR = Path(__file__).resolve().parent
log = logging.getLogger("birbesp")


async def _prune_loop() -> None:
    interval_s = int(os.environ.get("BIRB_PRUNE_INTERVAL_S", "3600"))
    retain_days = int(os.environ.get("BIRB_RETAIN_DAYS", "7"))
    retain_hl_days = int(os.environ.get("BIRB_RETAIN_HIGHLIGHT_DAYS", "30"))
    if retain_days <= 0:
        log.info("[prune] retention disabled (BIRB_RETAIN_DAYS=%d)", retain_days)
        return
    log.info(
        "[prune] retention enabled: raw=%dd highlights=%dd interval=%ds",
        retain_days, retain_hl_days, interval_s,
    )
    while True:
        try:
            stats = await asyncio.to_thread(
                get_store().prune,
                datetime.now(timezone.utc),
                retain_days,
                retain_hl_days,
            )
            if stats.get("deleted_frames", 0):
                log.info(
                    "[prune] dropped %d frames (%.1f MB)",
                    stats["deleted_frames"], stats["deleted_bytes"] / 1e6,
                )
        except Exception:
            log.exception("[prune] failed")
        await asyncio.sleep(interval_s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_prune_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="birbESP", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=_APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=_APP_DIR / "templates")

GALLERY_PAGE_SIZE = 60
_FRAME_RE = re.compile(r"^\d{4}/\d{2}/\d{2}/\d{6}_\d{3}\.jpg$")


def _stream_url() -> str | None:
    return os.environ.get("ESP32_STREAM_URL") or None


# PIL's ROTATE_* constants are *counter-clockwise*. Map "clockwise N°" → the
# equivalent PIL transpose so users can think in normal photographic terms.
_ROTATE_OPS = {
    90:  Image.ROTATE_270,
    180: Image.ROTATE_180,
    270: Image.ROTATE_90,
}


def _rotate_jpeg(jpeg_bytes: bytes, degrees: int) -> bytes:
    """Rotate a JPEG payload clockwise by `degrees` (0/90/180/270)."""
    op = _ROTATE_OPS.get(degrees % 360)
    if op is None:
        return jpeg_bytes
    with Image.open(io.BytesIO(jpeg_bytes)) as im:
        rotated = im.transpose(op)
        buf = io.BytesIO()
        rotated.save(buf, format="JPEG", quality=88)
        return buf.getvalue()


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
    # Server-side rotation for sensors mounted at non-zero physical angles.
    # 0/90/180/270 (clockwise). Other values are silently ignored.
    rotation = int(os.environ.get("BIRB_ROTATE", "0"))
    if rotation:
        payload = await asyncio.to_thread(_rotate_jpeg, payload, rotation)
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


@app.get("/frame/{path:path}", response_class=HTMLResponse)
def frame_detail(request: Request, path: str) -> HTMLResponse:
    if not _FRAME_RE.match(path):
        raise HTTPException(404, "Not found")
    store = get_store()
    row = store.get(path)
    if row is None:
        raise HTTPException(404, "Not found")
    neighbors = store.neighbors(path)
    iso = row["ts_iso"]
    download_name = f"birbESP-{iso[:10]}T{iso[11:19].replace(':', '-')}.jpg"
    return templates.TemplateResponse(
        request,
        "frame.html",
        {
            "active": "gallery",
            "frame": row,
            "newer": neighbors["newer"],
            "older": neighbors["older"],
            "download_name": download_name,
        },
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
    rotation = int(os.environ.get("BIRB_ROTATE", "0")) % 360
    if rotation not in (0, 90, 180, 270):
        rotation = 0
    return templates.TemplateResponse(
        request,
        "live.html",
        {"active": "live", "stream_url": _stream_url(), "rotation": rotation},
    )


@app.get("/api/frames")
def api_frames(since: int, until: int, max: int = 2400) -> JSONResponse:
    if until <= since:
        raise HTTPException(400, "until must be > since")
    if until - since > 7 * 24 * 3600 * 1000:
        raise HTTPException(400, "range too large (max 7 days)")
    return JSONResponse(get_store().list_in_range(since, until, max_count=max))


@app.get("/scrub", response_class=HTMLResponse)
def scrub_page(request: Request, hours: float = 3.0) -> HTMLResponse:
    hours = max(0.25, min(hours, 24.0))
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)
    return templates.TemplateResponse(
        request,
        "scrub.html",
        {
            "active": "scrub",
            "hours": hours,
            "since_ms": int(since.timestamp() * 1000),
            "until_ms": int(now.timestamp() * 1000),
            "windows": [0.5, 1, 3, 6, 12, 24],
        },
    )


@app.get("/highlights", response_class=HTMLResponse)
def highlights_page(request: Request, date: str | None = None) -> HTMLResponse:
    store = get_store()
    if date is None:
        dates = store.dates_with_frames()
        date = dates[0] if dates else datetime.now(local_tz()).strftime("%Y-%m-%d")
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
        date = dates[0] if dates else datetime.now(local_tz()).strftime("%Y-%m-%d")
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
