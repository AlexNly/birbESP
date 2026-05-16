#pragma once

// Start the local HTTP server on HTTP_PORT with a `/stream` MJPEG endpoint
// and register the mDNS hostname (MDNS_HOSTNAME).local. Call after WiFi is up.
void stream_begin();

// Pump the WebServer. Call from loop() — handles a single client at a time;
// `/stream` deliberately blocks for as long as the viewer is connected.
void stream_loop();
