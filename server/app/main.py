from datetime import datetime, timezone

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .storage import get_store

app = FastAPI(title="birbESP", version="0.1.0")


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
    return JSONResponse({"ok": True, **row})


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
