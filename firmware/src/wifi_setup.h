#pragma once

#include <Arduino.h>

// Connect to WIFI_SSID/WIFI_PASS in station mode and install an auto-reconnect
// event handler. Returns true if connected before WIFI_CONNECT_TIMEOUT_MS;
// returns false otherwise but reconnect attempts continue in the background.
bool wifi_begin();
