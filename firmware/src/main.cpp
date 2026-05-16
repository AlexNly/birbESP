#include <Arduino.h>

#include "camera.h"
#include "config.h"
#include "stream.h"
#include "uploader.h"
#include "wifi_setup.h"

void setup() {
  // GPIO 4 on AI-Thinker drives the very bright white "flash" LED next to the
  // camera lens — pin it LOW immediately so it never blinds the birds (or her).
  pinMode(4, OUTPUT);
  digitalWrite(4, LOW);

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

  stream_begin();
  uploader_start();
}

void loop() {
  stream_loop();
}
