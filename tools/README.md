# tools/

Development helpers — not part of the deployed system.

## `fake_cam.py`

Pretends to be the ESP32-CAM. Generates synthetic SVGA JPEGs with a timestamp
overlay and an occasional "bird" blob, then POSTs them to the server's upload
endpoint at 1 Hz. Useful for iterating on the mobile UI and the highlights
threshold without any hardware.

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt

# Server must be running first (see server/README.md).
python tools/fake_cam.py --url http://localhost:8080/api/upload
```

Useful flags:

- `--fps 2`            → upload faster than 1 Hz
- `--bird-chance 0.05` → rarer "birds" (lower highlight rate)
- `--duration 60`      → stop after one minute (handy for CI / smoke tests)
