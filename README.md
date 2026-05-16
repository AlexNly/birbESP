# birbESP

A weekend bird-watching cam.

ESP32-CAM pointed at a feeder, captures one frame per second, streams a live MJPEG view, and uploads stills to a NixOS + Docker homelab. The homelab hosts a mobile-first web app with a live view and a server-curated "highlights" reel of recent bird activity — built primarily for one person to enjoy from her phone.

See [`docs/specs/birb-esp.md`](docs/specs/birb-esp.md) for the design spec.

## Status

Work-in-progress weekend build.

## Layout

```
docs/        design spec, hardware notes, build log
3d-prints/   links to the printed cases
server/      homelab side — FastAPI + Docker
firmware/    ESP32-CAM side — PlatformIO + Arduino framework
tools/       development helpers (e.g. fake-cam uploader for UX iteration)
```

## License

MIT — see [`LICENSE`](LICENSE).
