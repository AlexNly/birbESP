# birbESP — Mobile Bird-Cam for Two

**Status:** Draft · **Author:** Alex · **Date:** 2026-05-16

## Problem

Alex's girlfriend wants to enjoy the birds at the feeder without sitting at the window. Today she has no way to (a) check on the feeder when she's curious from her phone, or (b) catch up on what she missed. A commercial bird-cam is overkill, opaque, and doesn't satisfy Alex's secondary goal: a documented, photographed weekend maker project tracked publicly on GitHub.

## Goal

A LAN-only, mobile-first web app where she can — within one tap from her phone — see a live view of the feeder *right now* and scroll a curated reel of recent bird activity. The build itself is documented, photographed, and committed to GitHub in fine-grained steps so it reads like a build log.

## Non-goals

- Remote access from outside the home network (no Tailscale / Cloudflare in v1)
- Battery-only operation, deep-sleep, or PIR motion-triggering (cam is plugged in 24/7)
- Bird species identification or any ML
- On-device motion detection (server does it)
- Automatic timelapse video, sound capture, night vision
- Multi-camera support, user accounts, push notifications

## Approach

**Dumb cam, smart server.** The ESP32-CAM does the minimum: connect to WiFi, capture one SVGA JPEG per second, POST it to the homelab, and serve an MJPEG `/stream` endpoint on demand. No motion detection, no resolution switching, no SD card. Plugged in via a Wemos 18650 shield that doubles as a small UPS so power blips don't reboot it.

The homelab (NixOS + Docker) runs a single FastAPI container that receives uploads, writes them to a date-bucketed folder, and runs a cheap server-side frame-diff to tag each frame as "boring" or "interesting." A small mobile-first web UI gives her two views: **Live** (latest still + MJPEG iframe from the cam) and **Highlights** (auto-curated reel of frames where pixels actually changed). A **Full timeline** view exists as a fallback. Storage retention is bounded by a nightly prune (default: keep 7 days of raw frames; keep highlights longer).

The repo is the second deliverable. Monorepo layout (`firmware/`, `server/`, `docs/`, `3d-prints/`), commits fine-grained so the GitHub history reads as a step-by-step build log, with photographs in `docs/build-log.md`. 3D-printed cases (ESP32-CAM mount, Wemos 18650 shield case) are linked, not re-hosted.

This beats the alternatives because: ESP32-standalone is fine for live view but terrible for "scroll through stills she missed"; on-device motion detection adds firmware tuning headaches with no upside vs server-side diff; battery-only is incompatible with always-on live view, which she explicitly wants.

## Open questions

- Exact ESP32-CAM board variant (assuming AI-Thinker; user to confirm)
- Wemos 18650 shield version (v1 / v2 / v3) — affects whether 5V boost is always-on or button-toggled
- Homelab hostname / LAN IP (baked into firmware as upload target)
- ~~Retention policy — is 7 days of raw frames + 30 days of highlights the right default given homelab storage budget?~~ **Resolved:** real footage measures ~26 KB/SVGA JPEG → ~2.16 GB/day; production deploy runs `BIRB_RETAIN_DAYS=30` + `BIRB_RETAIN_HIGHLIGHT_DAYS=365` (~66 GB total).
- "Interesting" threshold for the frame-diff (tune empirically once real frames are flowing)
- Mount location: indoor through-window vs outdoor sheltered (affects WiFi reach and weather notes in docs)
- Photo plan — does Alex want a separate "hero shot" of the finished rig for the README?

## First step

Stand up the **server side first, with a fake camera**, on the homelab tonight. Concretely: scaffold the FastAPI app + `docker-compose.yml` + mobile-first templates, plus a 30-line Python script that uploads a synthetic image (with timestamp drawn on it) every second to `localhost:8080/api/upload`. Open the gallery on Alex's phone. This validates the UX she will actually use — the mobile layout, the highlights detection threshold, the live-vs-history split — **without waiting on any hardware or flashing**. If the UX doesn't feel right at this stage, no firmware work has been wasted. Once it feels good, the firmware is the smaller, more mechanical half of the project. Target: 2 focused hours.
