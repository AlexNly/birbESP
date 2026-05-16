"""Synthetic 1 Hz uploader for UX iteration without hardware.

Generates SVGA JPEGs with a timestamp overlay and an occasional moving "bird"
blob, then POSTs them to the server's /api/upload endpoint. Use this to tune
the gallery layout, highlight threshold, and mobile UI before flashing the
real cam.

    python tools/fake_cam.py --url http://localhost:8080/api/upload

Requires: requests, pillow. See tools/requirements.txt.
"""

from __future__ import annotations

import argparse
import io
import random
import time
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT = 800, 600
BG_COLOR = (30, 60, 35)  # mossy green
BIRD_COLORS = [(220, 200, 90), (220, 120, 60), (90, 60, 200), (240, 240, 240)]


def _font() -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 28)
    except OSError:
        return ImageFont.load_default()


def make_frame(frame_idx: int, bird: tuple | None) -> bytes:
    im = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(im)
    # "Feeder" — static landmark so the empty frames look like something.
    draw.rectangle((340, 380, 460, 560), fill=(90, 60, 35))
    draw.ellipse((300, 340, 500, 420), fill=(120, 80, 40))
    if bird is not None:
        cx, cy, color = bird
        draw.ellipse((cx - 26, cy - 18, cx + 26, cy + 18), fill=color)
        draw.polygon(((cx + 26, cy), (cx + 38, cy - 6), (cx + 38, cy + 6)), fill=color)
    label = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    draw.rectangle((10, 10, 360, 50), fill=(0, 0, 0))
    draw.text((18, 14), f"{label}  f{frame_idx:05d}", fill=(220, 220, 220), font=_font())
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=82)
    return buf.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8080/api/upload")
    parser.add_argument("--fps", type=float, default=1.0)
    parser.add_argument(
        "--bird-chance",
        type=float,
        default=0.18,
        help="Probability per frame that a 'bird' blob appears (0..1).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0,
        help="Stop after this many seconds. 0 = run forever.",
    )
    args = parser.parse_args()

    period = 1.0 / args.fps
    started = time.monotonic()
    i = 0
    session = requests.Session()
    print(f"fake_cam → {args.url} @ {args.fps:g} fps. Ctrl-C to stop.")
    while True:
        bird = None
        if random.random() < args.bird_chance:
            bird = (
                random.randint(120, WIDTH - 120),
                random.randint(120, HEIGHT - 220),
                random.choice(BIRD_COLORS),
            )
        jpeg = make_frame(i, bird)
        try:
            r = session.post(
                args.url,
                files={"image": ("frame.jpg", jpeg, "image/jpeg")},
                timeout=5,
            )
            tag = "★" if r.ok and r.json().get("is_highlight") else " "
            print(f"  {tag} f{i:05d} → {r.status_code}")
        except requests.RequestException as e:
            print(f"  ! f{i:05d} → {e}")
        i += 1
        if args.duration and (time.monotonic() - started) >= args.duration:
            break
        time.sleep(max(0, period - 0.02))


if __name__ == "__main__":
    main()
