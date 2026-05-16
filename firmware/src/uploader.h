#pragma once

// Start a FreeRTOS task that captures one JPEG per UPLOAD_INTERVAL_MS and
// posts it to UPLOAD_URL as multipart/form-data. Frames dropped silently on
// network failure — the cam is meant to be the dumb half of the system.
void uploader_start();
