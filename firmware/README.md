# birbESP — firmware

PlatformIO project for the AI-Thinker ESP32-CAM. The firmware:

- connects to WiFi
- initializes the OV2640 camera (SVGA JPEG)
- captures one frame per second and `POST`s it to the homelab's `/api/upload`
- serves an MJPEG `/stream` endpoint for the browser's live view
- registers as `birb.local` via mDNS

## Build / flash

The ESP32-CAM has no onboard USB. See [`../docs/hardware.md`](../docs/hardware.md)
for the FTDI / ESP32-CAM-MB wiring.

```sh
cd firmware
cp include/secrets.h.example include/secrets.h
$EDITOR include/secrets.h   # WIFI_SSID, WIFI_PASS, UPLOAD_URL

# Hold IO0 to GND, power-cycle, then:
pio run -t upload -t monitor
# Release IO0 and power-cycle to boot normally.
```

## Layout

```
firmware/
├── platformio.ini
├── README.md
├── include/
│   └── secrets.h.example     # template; copy to secrets.h (gitignored)
└── src/
    ├── main.cpp              # setup() + loop()
    ├── config.h              # upload URL, capture interval, hostname
    ├── wifi_setup.{h,cpp}    # station-mode connect + auto-reconnect
    ├── camera.{h,cpp}        # esp_camera init (AI-Thinker pinout)
    ├── uploader.{h,cpp}      # 1 Hz capture + HTTP multipart POST
    └── stream.{h,cpp}        # MJPEG handler on the local WebServer
```
