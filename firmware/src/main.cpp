#include <Arduino.h>

#include "camera.h"
#include "config.h"
#include "uploader.h"
#include "wifi_setup.h"

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("birbESP firmware booting...");

  if (camera_begin() != ESP_OK) {
    Serial.println("[cam] camera init failed — halting");
    while (true) delay(1000);
  }

  if (!wifi_begin()) {
    Serial.println("[wifi] no connection yet — continuing, will retry in background");
  }

  uploader_start();
}

void loop() {
  delay(1000);
}
