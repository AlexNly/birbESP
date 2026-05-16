#include "stream.h"

#include <Arduino.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_camera.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "config.h"

static WebServer server(HTTP_PORT);
// Control endpoints (/led/*) run on a separate WebServer instance on
// HTTP_PORT+1, handled by its own FreeRTOS task on core 0. Necessary because
// handle_stream() blocks the main Arduino loop on port 80 for as long as a
// viewer is connected, which would otherwise prevent /led/* from being served.
static WebServer ctrl_server(HTTP_PORT + 1);

static constexpr const char* kStreamBoundary = "frame";
static constexpr uint32_t kStreamFrameDelayMs = 50;   // ~20 fps cap

// GPIO 4 drives the AI-Thinker board's onboard white "flash" LED.
// Kept LOW at boot (see main.cpp); these handlers let the web UI toggle it.
// Default temporary-on duration: 30 s, then auto-off as a safety against
// "left it on, board overheated and scared the birds for an hour".
static constexpr uint8_t kLedPin = 4;
static constexpr uint32_t kLedDefaultMs = 30000;

// 0 = no timer (LED is off, or in permanent-on mode).
// Otherwise, millis() value at which the LED should auto-off.
static volatile unsigned long led_off_at_ms = 0;

static void led_off() {
  digitalWrite(kLedPin, LOW);
  led_off_at_ms = 0;
}
static void led_on(uint32_t duration_ms) {
  digitalWrite(kLedPin, HIGH);
  // duration_ms == 0 means permanent (no timeout).
  led_off_at_ms = duration_ms ? (millis() + duration_ms) : 0;
}

static void led_send_status() {
  bool on = digitalRead(kLedPin) == HIGH;
  bool permanent = on && led_off_at_ms == 0;
  uint32_t remaining_ms = 0;
  if (on && led_off_at_ms != 0) {
    // Signed subtraction wraps cleanly across millis() rollover (~49 d).
    long delta = (long)(led_off_at_ms - millis());
    if (delta > 0) remaining_ms = (uint32_t)delta;
  }
  String body = String("{\"state\":\"") + (on ? "on" : "off")
              + "\",\"permanent\":" + (permanent ? "true" : "false")
              + ",\"remaining_ms\":" + remaining_ms + "}";
  // Responds on the control server (port 81). The control server is what
  // dispatched the request, so .send() here writes to the correct client.
  ctrl_server.send(200, "application/json", body);
}
static void handle_led_status()    { led_send_status(); }
static void handle_led_on()        { led_on(kLedDefaultMs); led_send_status(); }
static void handle_led_on_perm()   { led_on(0);             led_send_status(); }
static void handle_led_off()       { led_off();             led_send_status(); }

static void led_check_timeout() {
  if (led_off_at_ms != 0 && (long)(millis() - led_off_at_ms) >= 0) {
    led_off();
  }
}

// Dedicated watchdog task pinned to core 0 (system core). Necessary because
// handle_stream() blocks the Arduino loop on core 1 for as long as a viewer
// is connected — without this task, led_check_timeout() would never run
// while the live stream is active and the LED would stay on indefinitely.
static void led_watchdog_task(void* /*arg*/) {
  for (;;) {
    led_check_timeout();
    vTaskDelay(pdMS_TO_TICKS(200));
  }
}

// Pumps the control WebServer (port 81). Runs on core 0 so it keeps handling
// /led/* requests even while handle_stream() blocks the Arduino main loop.
static void ctrl_http_task(void* /*arg*/) {
  for (;;) {
    ctrl_server.handleClient();
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

static void handle_root() {
  String body =
    "<!DOCTYPE html><meta name=viewport content='width=device-width,initial-scale=1'>"
    "<title>birbESP cam</title>"
    "<body style='margin:0;background:#000;color:#eee;font:14px sans-serif'>"
    "<p style='padding:10px'>birbESP cam — <a style='color:#f0a830' href='/stream'>open /stream</a></p>"
    "<img style='max-width:100%' src='/stream'>"
    "</body>";
  server.send(200, "text/html", body);
}

static void handle_stream() {
  WiFiClient client = server.client();
  if (!client) return;

  String head =
    String("HTTP/1.1 200 OK\r\n") +
    "Content-Type: multipart/x-mixed-replace; boundary=" + kStreamBoundary + "\r\n"
    "Cache-Control: no-store\r\n"
    "Pragma: no-cache\r\n"
    "Access-Control-Allow-Origin: *\r\n"
    "\r\n";
  client.print(head);

  while (client.connected()) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      delay(50);
      continue;
    }
    client.printf("--%s\r\n", kStreamBoundary);
    client.printf("Content-Type: image/jpeg\r\n");
    client.printf("Content-Length: %u\r\n\r\n", (unsigned)fb->len);
    client.write(fb->buf, fb->len);
    client.print("\r\n");
    esp_camera_fb_return(fb);
    delay(kStreamFrameDelayMs);
  }
}

void stream_begin() {
  server.on("/", handle_root);
  server.on("/stream", handle_stream);
  server.onNotFound([]() { server.send(404, "text/plain", "not found"); });
  server.begin();

  // Control endpoints live on a separate port so they keep responding while
  // /stream holds the main server hostage.
  ctrl_server.on("/led", handle_led_status);
  ctrl_server.on("/led/on", handle_led_on);
  ctrl_server.on("/led/on/permanent", handle_led_on_perm);
  ctrl_server.on("/led/off", handle_led_off);
  ctrl_server.onNotFound([]() { ctrl_server.send(404, "text/plain", "not found"); });
  ctrl_server.begin();

  xTaskCreatePinnedToCore(
      led_watchdog_task, "led_wdt", 4096, nullptr, /*priority=*/1, nullptr,
      /*coreID=*/0);
  xTaskCreatePinnedToCore(
      ctrl_http_task,    "ctrl_http", 8192, nullptr, /*priority=*/1, nullptr,
      /*coreID=*/0);

  if (WiFi.status() == WL_CONNECTED) {
    if (MDNS.begin(MDNS_HOSTNAME)) {
      MDNS.addService("http", "tcp", HTTP_PORT);
      Serial.printf("[mdns] %s.local -> http://%s:%d\n",
                    MDNS_HOSTNAME, WiFi.localIP().toString().c_str(), HTTP_PORT);
    } else {
      Serial.println("[mdns] init failed");
    }
  }
}

void stream_loop() {
  led_check_timeout();
  server.handleClient();
}
