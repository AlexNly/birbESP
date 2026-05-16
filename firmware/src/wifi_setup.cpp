#include "wifi_setup.h"

#include <WiFi.h>

#include "config.h"
#include "secrets.h"

static void on_wifi_event(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.printf("[wifi] connected, ip=%s rssi=%d\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      Serial.println("[wifi] disconnected, reconnecting...");
      WiFi.reconnect();
      break;
    default:
      break;
  }
}

bool wifi_begin() {
  WiFi.persistent(false);          // don't wear flash on every boot
  WiFi.setAutoReconnect(true);
  WiFi.mode(WIFI_STA);
  WiFi.onEvent(on_wifi_event);
  WiFi.setSleep(false);            // keep latency low for the live stream
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.printf("[wifi] connecting to '%s'...\n", WIFI_SSID);
  const uint32_t deadline = millis() + WIFI_CONNECT_TIMEOUT_MS;
  while (WiFi.status() != WL_CONNECTED && millis() < deadline) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  return WiFi.status() == WL_CONNECTED;
}
