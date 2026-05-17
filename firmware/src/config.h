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
// Some AI-Thinker module variants are more DMA-sensitive than others; the
// safe-for-everyone defaults pair each framesize with the XCLK that keeps
// the I²S DMA from overflowing (cam_hal: EV-EOF-OVF):
//
//   FRAMESIZE_SVGA  (800x600)    @ 20 MHz XCLK  — original baseline
//   FRAMESIZE_XGA   (1024x768)   @ 20 MHz XCLK  — modest bump
//   FRAMESIZE_SXGA  (1280x1024)  @ 10 MHz XCLK  — default; 2.7x SVGA pixels
//   FRAMESIZE_UXGA  (1600x1200)  @ 10 MHz XCLK  — max; some modules still hang
//
// At 1 fps capture cadence the halved XCLK readout speed is invisible —
// the sensor still produces a frame in a few hundred ms.
#define CAM_FRAMESIZE   FRAMESIZE_SXGA

// XCLK feeding the sensor. 10 MHz is universally compatible at SXGA and
// UXGA across AI-Thinker module revisions. Bump to 20 MHz only if you're
// staying at SVGA/XGA and want maximum sensor framerate (irrelevant at
// our 1 fps upload cadence).
#define CAM_XCLK_HZ     10000000

// JPEG quality on the OV2640 scale (0=best, 63=worst). 8 is the sweet spot
// for SXGA/UXGA; 12 is what the spec originally asked for at SVGA.
#define CAM_JPEG_QUALITY 8
