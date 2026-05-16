#pragma once

#include <esp_camera.h>

// Initialize the OV2640 with AI-Thinker pinout, SVGA (800x600) JPEG. Returns
// ESP_OK on success; logs and returns the underlying error otherwise.
esp_err_t camera_begin();
