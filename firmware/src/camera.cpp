#include "camera.h"

#include <Arduino.h>
#include <esp_camera.h>

#include "config.h"

// AI-Thinker ESP32-CAM pin assignment (same as Espressif's CameraWebServer
// CAMERA_MODEL_AI_THINKER block).
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

esp_err_t camera_begin() {
  camera_config_t cfg = {};
  cfg.ledc_channel  = LEDC_CHANNEL_0;
  cfg.ledc_timer    = LEDC_TIMER_0;
  cfg.pin_d0        = Y2_GPIO_NUM;
  cfg.pin_d1        = Y3_GPIO_NUM;
  cfg.pin_d2        = Y4_GPIO_NUM;
  cfg.pin_d3        = Y5_GPIO_NUM;
  cfg.pin_d4        = Y6_GPIO_NUM;
  cfg.pin_d5        = Y7_GPIO_NUM;
  cfg.pin_d6        = Y8_GPIO_NUM;
  cfg.pin_d7        = Y9_GPIO_NUM;
  cfg.pin_xclk      = XCLK_GPIO_NUM;
  cfg.pin_pclk      = PCLK_GPIO_NUM;
  cfg.pin_vsync     = VSYNC_GPIO_NUM;
  cfg.pin_href      = HREF_GPIO_NUM;
  cfg.pin_sccb_sda  = SIOD_GPIO_NUM;
  cfg.pin_sccb_scl  = SIOC_GPIO_NUM;
  cfg.pin_pwdn      = PWDN_GPIO_NUM;
  cfg.pin_reset     = RESET_GPIO_NUM;
  cfg.xclk_freq_hz  = CAM_XCLK_HZ;
  cfg.pixel_format  = PIXFORMAT_JPEG;

  // PSRAM-backed double-buffered config — see config.h for the framesize /
  // XCLK / quality combo and the safe pairings.
  if (psramFound()) {
    cfg.frame_size   = CAM_FRAMESIZE;
    cfg.jpeg_quality = CAM_JPEG_QUALITY;
    cfg.fb_count     = 2;
    cfg.fb_location  = CAMERA_FB_IN_PSRAM;
    cfg.grab_mode    = CAMERA_GRAB_LATEST;
  } else {
    cfg.frame_size   = FRAMESIZE_VGA;
    cfg.jpeg_quality = 12;
    cfg.fb_count     = 1;
    cfg.fb_location  = CAMERA_FB_IN_DRAM;
    cfg.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;
  }

  esp_err_t err = esp_camera_init(&cfg);
  if (err != ESP_OK) {
    Serial.printf("[cam] init failed: 0x%x\n", err);
    return err;
  }

  // Sensor tuning — enable the OV2640's auto-everything machinery so the
  // image copes with dusk, dawn, bright sun, and cloudy weather without
  // intervention. Slight saturation + sharpness bumps make stored frames
  // pop a bit more.
  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    s->set_whitebal(s, 1);                  // enable AWB
    s->set_awb_gain(s, 1);
    s->set_wb_mode(s, 0);                   // 0 = auto
    s->set_exposure_ctrl(s, 1);             // enable AEC
    s->set_aec2(s, 1);                      // enhanced AEC
    s->set_ae_level(s, 0);                  // -2..2
    s->set_gain_ctrl(s, 1);                 // enable AGC
    s->set_gainceiling(s, GAINCEILING_4X);  // cap noise in low light
    s->set_bpc(s, 1);                       // black-pixel correction
    s->set_wpc(s, 1);                       // white-pixel correction
    s->set_raw_gma(s, 1);                   // gamma correction
    s->set_lenc(s, 1);                      // lens correction
    s->set_dcw(s, 1);                       // downsize EN
    s->set_brightness(s, 0);                // -2..2
    s->set_contrast(s, 1);                  // a touch more contrast
    s->set_saturation(s, 1);                // a touch more colour
    s->set_sharpness(s, 1);                 // mild edge enhancement
    s->set_colorbar(s, 0);                  // no test bar
    s->set_special_effect(s, 0);            // 0 = none
  }
  Serial.printf("[cam] init ok (framesize=%d, xclk=%d Hz, jpeg_q=%d)\n",
                (int)CAM_FRAMESIZE, (int)CAM_XCLK_HZ, (int)CAM_JPEG_QUALITY);
  return ESP_OK;
}
