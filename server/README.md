# birbESP — server

FastAPI service running on the homelab. Receives JPEG uploads from the ESP32-CAM (or `tools/fake_cam.py`), stores them in a date-bucketed folder, tags interesting frames, and serves a mobile-first web UI.

## Quick start

```sh
cd server
docker compose up --build
# open http://localhost:8080/healthz
```

See [`../docs/deploy.md`](../docs/deploy.md) for the homelab deploy guide.

## Layout

```
server/
├── Dockerfile
├── docker-compose.yml
├── app/
│   ├── main.py           # FastAPI routes
│   ├── storage.py        # date-bucket writer + latest pointer
│   ├── highlights.py     # frame-diff "interesting" tagger
│   ├── templates/        # Jinja2 mobile-first HTML
│   ├── static/           # CSS, no JS frameworks
│   └── requirements.txt
└── data/                 # bind-mounted JPEG storage (gitignored)
```
