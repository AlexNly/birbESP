#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("birbESP firmware booting...");
}

void loop() {
  delay(1000);
}
