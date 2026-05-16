#pragma once

// Capture cadence. 1000 ms = 1 fps as per the spec.
#define UPLOAD_INTERVAL_MS 1000

// HTTP server (for /stream) and mDNS hostname.
#define HTTP_PORT       80
#define MDNS_HOSTNAME   "birb"   // -> birb.local

// WiFi connect timeout before we boot anyway and keep retrying in the background.
#define WIFI_CONNECT_TIMEOUT_MS 20000
