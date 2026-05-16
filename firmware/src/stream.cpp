#include "stream.h"

#include <Arduino.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_camera.h>

#include "config.h"

static WebServer server(HTTP_PORT);

static constexpr const char* kStreamBoundary = "frame";
static constexpr uint32_t kStreamFrameDelayMs = 50;   // ~20 fps cap

// GPIO 4 drives the AI-Thinker board's onboard white "flash" LED.
// Kept LOW at boot (see main.cpp); these handlers let the web UI toggle it.
static constexpr uint8_t kLedPin = 4;

static void handle_led_status() {
  bool on = digitalRead(kLedPin) == HIGH;
  server.send(200, "application/json", String("{\"state\":\"") + (on ? "on" : "off") + "\"}");
}
static void handle_led_on() {
  digitalWrite(kLedPin, HIGH);
  server.send(200, "application/json", "{\"state\":\"on\"}");
}
static void handle_led_off() {
  digitalWrite(kLedPin, LOW);
  server.send(200, "application/json", "{\"state\":\"off\"}");
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
  server.on("/led", handle_led_status);
  server.on("/led/on", handle_led_on);
  server.on("/led/off", handle_led_off);
  server.onNotFound([]() { server.send(404, "text/plain", "not found"); });
  server.begin();

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
  server.handleClient();
}
