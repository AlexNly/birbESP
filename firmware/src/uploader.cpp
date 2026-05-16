#include "uploader.h"

#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <esp_camera.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "config.h"
#include "secrets.h"

static constexpr const char* kBoundary = "----birbESPBoundary";

static bool post_jpeg(const uint8_t* jpeg, size_t jpeg_len) {
  String prefix = String("--") + kBoundary + "\r\n"
                + "Content-Disposition: form-data; name=\"image\"; filename=\"frame.jpg\"\r\n"
                + "Content-Type: image/jpeg\r\n\r\n";
  String suffix = String("\r\n--") + kBoundary + "--\r\n";

  size_t total = prefix.length() + jpeg_len + suffix.length();
  uint8_t* body = (uint8_t*)(psramFound() ? ps_malloc(total) : malloc(total));
  if (!body) {
    Serial.printf("[up] alloc %u failed\n", (unsigned)total);
    return false;
  }
  memcpy(body, prefix.c_str(), prefix.length());
  memcpy(body + prefix.length(), jpeg, jpeg_len);
  memcpy(body + prefix.length() + jpeg_len, suffix.c_str(), suffix.length());

  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(4000);
  http.begin(UPLOAD_URL);
  http.addHeader("Content-Type", String("multipart/form-data; boundary=") + kBoundary);
  int code = http.POST(body, total);
  http.end();
  free(body);

  if (code <= 0) {
    Serial.printf("[up] POST failed: %s\n", HTTPClient::errorToString(code).c_str());
    return false;
  }
  if (code / 100 != 2) {
    Serial.printf("[up] POST -> %d\n", code);
    return false;
  }
  return true;
}

static void upload_task(void*) {
  uint32_t sent = 0;
  uint32_t failed = 0;
  for (;;) {
    const uint32_t start = millis();
    if (WiFi.status() == WL_CONNECTED) {
      camera_fb_t* fb = esp_camera_fb_get();
      if (fb) {
        if (post_jpeg(fb->buf, fb->len)) {
          sent++;
        } else {
          failed++;
        }
        esp_camera_fb_return(fb);
      } else {
        Serial.println("[up] camera_fb_get returned null");
        failed++;
      }
    }
    if ((sent + failed) % 30 == 0) {
      Serial.printf("[up] sent=%u failed=%u heap=%u psram=%u\n",
                    sent, failed, (unsigned)ESP.getFreeHeap(),
                    (unsigned)ESP.getFreePsram());
    }
    const uint32_t elapsed = millis() - start;
    if (elapsed < UPLOAD_INTERVAL_MS) {
      vTaskDelay(pdMS_TO_TICKS(UPLOAD_INTERVAL_MS - elapsed));
    }
  }
}

void uploader_start() {
  xTaskCreatePinnedToCore(upload_task, "upload", 12288, nullptr, 1, nullptr, 1);
}
