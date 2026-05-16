# birbESP

A weekend bird-watching cam, built for two.

An ESP32-CAM points at a bird feeder, captures one frame per second, streams a
live MJPEG view, and uploads stills to a NixOS + Docker homelab. The homelab
hosts a mobile-first web app with a **live** view and a server-curated
**highlights** reel of recent bird activity — built primarily for one person to
enjoy from her phone, and as a documented maker project for everyone else.

> 📐 Design spec: [`docs/specs/birb-esp.md`](docs/specs/birb-esp.md)

## Status

| Component   | State                                                                 |
|-------------|-----------------------------------------------------------------------|
| Spec        | ✅ written                                                             |
| Server      | ✅ scaffold, upload, highlights, mobile UI, docker-compose             |
| Tools       | ✅ `fake_cam.py` for hardware-free UX iteration                        |
| Firmware    | ⏳ next milestone                                                      |
| Build log   | ⏳ add photos as the rig comes together (`docs/photos/`, `build-log.md`) |

## Quickstart (no hardware needed)

```sh
cd server && docker compose up --build &
python -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt
python tools/fake_cam.py --url http://localhost:8080/api/upload
```

Open <http://localhost:8080/> on your phone (use your laptop's LAN IP) and you
should see synthetic frames ticking in, with the occasional "highlight" when
a fake bird appears.

For the homelab deploy and pointing-the-real-cam-at-it, see
[`docs/deploy.md`](docs/deploy.md).

## Layout

```
docs/        design spec, hardware notes, deploy guide
3d-prints/   links to the printed cases
server/      FastAPI + Docker — receives uploads, hosts the web UI
firmware/    ESP32-CAM side — PlatformIO + Arduino (TBD)
tools/       development helpers (e.g. fake_cam.py)
```

## Hardware

See [`docs/hardware.md`](docs/hardware.md) for BOM and flashing notes.
Printed parts live in [`3d-prints/`](3d-prints/).

## License

MIT — see [`LICENSE`](LICENSE).
