#include <Arduino.h>

#include "config.h"
#include "wifi_setup.h"

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("birbESP firmware booting...");

  if (!wifi_begin()) {
    Serial.println("[wifi] no connection yet — continuing, will retry in background");
  }
}

void loop() {
  delay(1000);
}
