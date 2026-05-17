#pragma once

#include <esp_camera.h>

// Capture cadence. 1000 ms = 1 fps as per the spec.
#define UPLOAD_INTERVAL_MS 1000

// HTTP server (for /stream) and mDNS hostname.
#define HTTP_PORT       80
#define MDNS_HOSTNAME   "birb"   // -> birb.local

// WiFi connect timeout before we boot anyway and keep retrying in the background.
#define WIFI_CONNECT_TIMEOUT_MS 20000

// ---- Camera tuning ----------------------------------------------------------
//
// Frame size on the OV2640. Bigger = more detail, more bytes per JPEG.
// Safe combos that don't trigger DMA EV-EOF-OVF on AI-Thinker boards:
//   FRAMESIZE_SVGA  (800x600)    @ 20 MHz XCLK  — original config
//   FRAMESIZE_XGA   (1024x768)   @ 20 MHz XCLK  — modest bump
//   FRAMESIZE_SXGA  (1280x1024)  @ 20 MHz XCLK  — recommended, ~7 GB/day
//   FRAMESIZE_UXGA  (1600x1200)  @ 10 MHz XCLK  — only viable with halved XCLK
#define CAM_FRAMESIZE   FRAMESIZE_SXGA

// XCLK feeding the sensor. 20 MHz is the AI-Thinker default and works for
// everything up to SXGA. UXGA needs 10 MHz or the I²S DMA falls behind and
// the cam hangs.
#define CAM_XCLK_HZ     20000000

// JPEG quality on the OV2640 scale (0=best, 63=worst). 8 is the sweet spot
// for SXGA/UXGA; 12 is what the spec originally asked for at SVGA.
#define CAM_JPEG_QUALITY 8
