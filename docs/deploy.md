# Deploy

Three paths, in order of "how realistic is this":

1. **Local dev without Docker** — fastest UX iteration with `fake_cam.py`.
2. **Local Docker test** — confirms the image builds and runs end-to-end.
3. **NixOS homelab deploy** — the real thing.

---

## 1. Local dev without Docker

For iterating on templates and the highlights threshold. No hardware needed.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r server/app/requirements.txt -r tools/requirements.txt

# Terminal A — start the server
BIRB_DATA_DIR=./dev-data uvicorn app.main:app --host 0.0.0.0 --port 8080 \
  --app-dir server

# Terminal B — feed it synthetic frames
python tools/fake_cam.py --url http://localhost:8080/api/upload
```

Open <http://localhost:8080/> on your phone (same WiFi) using your laptop's
LAN IP, e.g. `http://192.168.1.42:8080/`.

---

## 2. Local Docker test

```sh
cd server
docker compose up --build
```

In another terminal:

```sh
python tools/fake_cam.py --url http://localhost:8080/api/upload
```

Stop with `Ctrl-C` in the compose terminal; data persists in `server/data/`.

---

## 3. NixOS homelab deploy

Assumes the host already has Docker enabled (`virtualisation.docker.enable = true;`).
A NixOS-native module is a possible follow-up but not in scope for v1.

### One-time setup

```sh
# On the homelab:
git clone git@github.com:AlexNly/birbESP.git
cd birbESP/server
cp .env.example .env
$EDITOR .env       # set ESP32_STREAM_URL once you know the cam's mDNS hostname
docker compose up -d --build
```

Verify:

```sh
curl http://localhost:8080/healthz
# {"status":"ok"}
```

From your phone on the same LAN, open `http://<homelab-ip>:8080/`.

### Updates

```sh
git pull
docker compose up -d --build
```

### Data

JPEGs are bind-mounted to `server/data/` on the host. Back this up if you care
about the captures. No retention policy is enforced yet — see
[`docs/specs/birb-esp.md`](specs/birb-esp.md) "open questions" for the pending
default.

### Logs

```sh
docker compose logs -f birbesp
```

---

## Pointing the camera at it

Once the firmware lands:

1. Flash the firmware with `firmware/include/secrets.h` containing your WiFi
   creds.
2. In `firmware/src/config.h`, set the upload URL to
   `http://<homelab-ip>:8080/api/upload` (or a hostname if your homelab has a
   stable mDNS name).
3. Power on the cam — check `docker compose logs -f birbesp` for uploads.
4. On the homelab UI, set `ESP32_STREAM_URL` in `.env` to the cam's stream URL
   (e.g. `http://birb.local/stream`) and `docker compose up -d` to reload.

The firmware is the next milestone — not built yet, see the project README.
