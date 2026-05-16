# Hardware

## Bill of materials

| Part | Notes |
| --- | --- |
| ESP32-CAM (AI-Thinker, OV2640) | Assumed AI-Thinker variant — most common; pin macros target it. |
| Wemos 18650 charge-circuit shield | TP4056-based charger + 5V boost output. Doubles as a small UPS when USB power is supplied — power blips don't reboot the cam. |
| 1× Samsung/LG/Sony 18650 cell | Any reasonable ~3000 mAh protected cell. |
| FTDI / USB-TTL adapter (3.3V logic) | For flashing the ESP32-CAM. An ESP32-CAM-MB programmer shield works too. |
| Dupont jumper wires (F-F) | A few for flashing + a few for the final 5V/GND power tap. |
| USB-A power source | Any 5V / ≥1A brick. The cam runs plugged in 24/7 — the 18650 is just buffering. |
| 3D-printed cases | See [`../3d-prints/`](../3d-prints/) for the models. |

## Power notes

Cam is **plugged in 24/7**. The Wemos 18650 shield is wired as a buffer:

```
USB-A 5V  ──►  Wemos shield USB-in  ──►  18650 charging
                          │
                          └── 5V boost out  ──►  ESP32-CAM 5V/GND
```

Net effect: brief power blips don't reboot the cam, and you keep the wireless aesthetic for short moves around the apartment.

Expected draw: ~250-400 mA at 5V while streaming + uploading at 1 fps. A fully charged 18650 carries the cam through roughly 4-6 hours of unplugged operation if needed.

## Flashing

The ESP32-CAM has no onboard USB. To flash:

1. Connect FTDI/USB-TTL adapter:
   - FTDI 5V → ESP32-CAM 5V
   - FTDI GND → ESP32-CAM GND
   - FTDI TX → ESP32-CAM U0R (RX)
   - FTDI RX → ESP32-CAM U0T (TX)
2. Short **IO0** to **GND** to enter flash mode.
3. Power cycle (briefly remove 5V).
4. Run `pio run -t upload -t monitor` from the `firmware/` folder.
5. Remove the IO0↔GND short and power cycle again to boot normally.

Easier alternative: an **ESP32-CAM-MB** programmer shield handles all of this with a single micro-USB cable.

## Wiring diagram

TODO — add a photo or Fritzing sketch once the rig is assembled.

## Open hardware questions

- Confirm Wemos shield revision (v1 / v2 / v3) — affects whether the 5V boost output is always-on or button-toggled.
- Mount location: indoor through-window vs outdoor sheltered. The current build assumes indoor; outdoor would need weather-proofing notes.
