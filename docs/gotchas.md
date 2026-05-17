# Gotchas

Hard-won lessons from the first build. Read this *before* you start debugging
any of the symptoms below — every one of these cost real hours the first time.

## 1. Loose camera ribbon masquerades as "Failed to communicate with the flash chip"

**Symptom:** When flashing, `esptool` prints
`WARNING: Failed to communicate with the flash chip, read/write operations will fail`,
then dies partway through the write with `Serial data stream stopped` or
`Packet content transfer stopped`. Re-tries fail intermittently — sometimes
further, sometimes earlier.

**Cause:** The OV2640's ribbon cable is not fully seated in the cam's ZIF
connector. When loose, several camera data lines float and create electrical
noise on shared traces, which corrupts SPI-flash signalling even though the
flash chip itself is perfectly healthy.

**Fix:** Press the ZIF lever down, **fully** unseat the ribbon, slide it
straight back in so the contacts go in evenly (no skew), then press the
lever firmly closed. Inspect with a magnifier if you have one — the contacts
must align perfectly with the connector pads.

**Why it's confusing:** The error message points at the flash chip, but the
flash chip is fine. The ribbon is the actual culprit ~80 % of the time on
AI-Thinker boards.

**Best practice for *routine* flashing:** Disconnect the camera ribbon
entirely before every flash, reconnect after `Hash of data verified` and
the reset. The OV2640 shares strapping-pin-adjacent traces with the flash
bus, so even a properly-seated ribbon can occasionally cause flash failures.
Flashing with the camera detached is faster and 100 % reliable. The
firmware tolerates the absent camera at flash time — it'll just halt with
`[cam] init failed: 0x105` until you reconnect and reset.

## 2. GPIO 4 flash LED will overheat the SPI flash

**Symptom:** Within a few minutes of being powered with factory firmware (or
any firmware that doesn't explicitly drive GPIO 4 LOW), the cam gets
**very hot** — the little white LED next to the lens is brutal. After enough
heat soak, the SPI flash chip beside it starts misbehaving: flash failures,
boot loops, audible regulator whine.

**Cause:** AI-Thinker's factory `CameraWebServer` demo leaves the GPIO 4 white
"flash" LED on full brightness at boot. It's drawing ~100 mA continuously and
heats the entire module. The SPI flash chip is millimetres away.

**Fix:** First thing in `setup()` (already in `firmware/src/main.cpp`):
```c
pinMode(4, OUTPUT);
digitalWrite(4, LOW);
```
This is committed firmware-side. The danger window is between unboxing the cam
(factory firmware) and the moment our firmware first runs — keep flash
sessions short, unplug between attempts, **don't leave the cam plugged in
overnight on factory firmware.**

## 3. GPIO 12 strapping → "Failed to communicate with the flash chip" (the *other* cause)

**Symptom:** Same warning as #1, but the camera ribbon is verified seated.
Sometimes works, mostly doesn't.

**Cause:** GPIO 12 is an ESP32 strapping pin. At boot it tells the ESP32 what
voltage its SPI flash uses (LOW = 3.3 V, HIGH = 1.8 V). On AI-Thinker the
flash is always 3.3 V, but GPIO 12 has no pull-down, so if it floats HIGH at
boot the ESP32 talks to the (3.3 V) flash at the wrong voltage → garbled SPI.

**Fix:** Burn a one-time eFuse to force VDD_SPI to 3.3 V permanently. From
PlatformIO's bundled esptool:
```sh
ESPFUSE=$(find ~/.platformio -name 'espefuse.py' | head -1)
python3 "$ESPFUSE" --chip esp32 --port /dev/ttyUSB0 set_flash_voltage 3.3V
# Confirm with "BURN" when prompted.
```
**This is permanent and cannot be undone.** It's safe — it's the correct
setting for this hardware. Espressif themselves recommend it for ESP32-CAM.
A full cold power-cycle (unplug for 5 s) is needed before the new eFuse
takes effect.

## 4. macOS + USB-C + ESP32 flashing is unreliable

**Symptom:** Cam flashes fine from a Linux box but fails on a USB-C-only Mac
with `Serial data stream stopped` or `Packet content transfer stopped`, even
with a known-good cable and a freshly enumerated `/dev/cu.usbserial-*`.

**Cause:** Espressif bug
[ESPTOOL-383](https://github.com/espressif/esptool/issues/712). USB-C-to-USB-A
dongles and Thunderbolt docks introduce signal-timing and power-delivery
quirks that the CH340 chip on the MB shield can't tolerate. A **powered USB
hub** between the Mac and the cam *sometimes* helps but isn't reliable.

**Fix:** **Flash from the homelab.** The homelab has real USB-A ports with
proper power. Steps in [`deploy.md`](deploy.md) under the firmware section.

## 5. Default upload_speed is too aggressive on the MB shield

**Symptom:** Flash fails with `Serial data stream stopped: Possible serial
noise or corruption` immediately after the line `Changing baud rate to 460800`.

**Cause:** The CH340 USB-serial chip on most MB shields, combined with cheap
cables, can't sustain reliable transport at 460800. The initial connect (at
the safe default) succeeds; switching up for the bulk write breaks it.

**Fix:** Already pinned in `firmware/platformio.ini`:
```ini
upload_speed = 115200
```
Costs ~30 s per flash, gains a build that actually completes.

## 6. SPI flash defaults are too aggressive on AI-Thinker

**Symptom:** Even with stable USB power and a seated ribbon, intermittent
`Failed to communicate with the flash chip` warnings.

**Fix:** Already pinned in `platformio.ini`:
```ini
board_build.f_flash = 40000000L
board_build.flash_mode = dio
```
40 MHz DIO is universally compatible. Default 80 MHz QIO is faster but
fragile on this hardware.

## 7. ESP32 HTTPS uploads are too slow for 1 fps

**Symptom:** If you point the cam's `UPLOAD_URL` at `https://birb.ncly.de/...`
instead of plain HTTP, uploads happen but at maybe 0.3 fps, with TLS handshake
warnings filling the serial monitor.

**Cause:** The ESP32's `WiFiClientSecure` does a full TLS handshake per
request (HTTPClient doesn't reuse connections by default). Handshake is
~2 s on an ESP32, so 1 fps is mathematically impossible.

**Fix:** Use **dual-port plain HTTP** on the homelab. The container binds
both `127.0.0.1:8810` (for the nginx → HTTPS public path) and
`192.168.178.124:8810` (LAN-only plain HTTP for the cam). Cam uses the LAN
URL; phones still get HTTPS through `https://birb.ncly.de`.

## 8. `url_for` behind an HTTPS reverse proxy generates http:// links

**Symptom:** The page loads at `https://birb.ncly.de/` but appears completely
unstyled — raw HTML look, default fonts, blue underlined links. View-source
shows `<link rel="stylesheet" href="http://birb.ncly.de/static/style.css">`.

**Cause:** FastAPI sees the request as plain HTTP (nginx terminates TLS and
forwards as HTTP to the container). `Jinja2Templates.url_for()` generates an
absolute URL using whatever scheme `Request.url` reports — so it builds an
`http://` URL. Modern browsers block that as **mixed content** on an HTTPS
page → CSS doesn't load.

**Fix (already applied):**
1. Use a literal relative path in templates: `href="/static/style.css"` (not
   `url_for`). Bulletproof regardless of proxy.
2. Pass `--proxy-headers --forwarded-allow-ips=*` to uvicorn so any future
   `url_for()` calls honour the `X-Forwarded-Proto` header from nginx.

Both are committed.

## 9. mDNS (`birb.local`) doesn't resolve on every router

**Symptom:** Live view doesn't load — the `<img src="http://birb.local/stream">`
tag never resolves the hostname.

**Cause:** Some consumer routers (Fritz!Box with certain firmware, mesh
systems, enterprise WiFi) block multicast DNS or rewrite `.local` queries.

**Fix:** Use the cam's explicit IP address instead of `birb.local`. The cam
prints its IP at boot in the serial log:
```
[wifi] connected, ip=192.168.178.XXX rssi=-50
```
Set the homelab's `ESP32_STREAM_URL` to `http://192.168.178.XXX/stream`
instead of `http://birb.local/stream`.

## 10. UXGA at default XCLK hangs the cam (EV-EOF-OVF)

**Symptom:** After bumping the camera config to `FRAMESIZE_UXGA` (1600×1200),
the cam logs `cam_hal: EV-EOF-OVF` and `camera_fb_get returned null`, then
becomes unresponsive on every port (`/stream`, `/led`, even ping). Reboot
brings it back briefly until it locks up again.

**Cause:** UXGA shifts pixels too fast for the AI-Thinker board's I²S DMA at
the default 20 MHz XCLK — the FIFO overflows mid-frame. SXGA (1280×1024) and
smaller are fine at 20 MHz; UXGA needs the XCLK halved.

**Fix:** In `firmware/src/config.h`, either drop the framesize:
```c
#define CAM_FRAMESIZE  FRAMESIZE_SXGA
#define CAM_XCLK_HZ    20000000
```
…or, if you really want UXGA, halve the XCLK:
```c
#define CAM_FRAMESIZE  FRAMESIZE_UXGA
#define CAM_XCLK_HZ    10000000
```
SXGA at 20 MHz is the recommended default — still 2.7× the pixel count of the
original SVGA without any DMA risk.

---

*If you discover a new gotcha while building or maintaining this, please add
it here — the next person (which might be you) will thank you.*
