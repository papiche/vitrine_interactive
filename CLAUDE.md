# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vitrine Interactive is a gesture-controlled, browser-based carousel for displaying Nostr messages in an interactive storefront display. It uses hand gesture recognition (MediaPipe), face recognition, and Nostr protocol integration with a "Minority Report" style UI. Designed for Raspberry Pi 4/5 or Linux PC.

## Tech Stack

- **Backend**: Python 3.8+ / Flask / Flask-SocketIO / OpenCV / MediaPipe / face_recognition (optional)
- **Frontend**: Vanilla HTML/CSS/JS (no frameworks — intentional, for minimal RPi overhead)
- **External**: IPFS daemon, Astroport.ONE node (Nostr relay), webcam
- **Venv**: `~/.astro`

## Commands

### Run the application
```bash
./start_vitrine.sh                          # Default: port 5555, camera 0
./start_vitrine.sh --port 8080 --camera 1   # Custom port/camera
./start_vitrine.sh --debug                  # With debug output
```

### Setup & configuration
```bash
./setup_vitrine.sh          # Pre-flight dependency checks
./manage_env.sh init        # Create .env from .env.template
./manage_env.sh show        # View current config
```

### Install dependencies
```bash
python3 -m venv ~/.astro && source ~/.astro/bin/activate
pip install flask flask-cors flask-socketio opencv-python mediapipe numpy qrcode Pillow requests python-dotenv
pip install face_recognition dlib  # Optional, for better face recognition
```

### Face recognition CLI
```bash
python face_recognition_module.py --batch   # Train on all photos
python face_recognition_module.py --stats   # Show statistics
python face_recognition_module.py --users   # List recognized users
```

### Cleanup
```bash
./clean_vitrine_posts.sh    # Photo cleanup utility
```

## Architecture

### Backend (vitrine.py ~1500 lines)
Three concurrent threads:
1. **Camera handler** — continuous frame capture + MediaPipe hand detection at 30 FPS
2. **Nostr feed** — background refresh loop every 30s fetching kind-0/kind-1 events from local Astroport relay
3. **WebSocket emitter** — real-time gesture updates at 30 FPS (when clients connected)

### Frontend (shop_carousel.js + shop_carousel.html)
- Polls `/api/gesture` every 50ms for hand position & gesture state
- Polls `/api/events` every 30s for Nostr messages
- iPod Cover Flow 3D carousel with CSS transforms
- Dark mode (default) / Light mode (triggered by hand detection)

### Photo capture flow (thumbs up gesture)
Browser detects gesture → POST `/api/capture` → backend captures webcam frame → face detection → IPFS upload (with fallback chain: `upload2ipfs.sh` → `ipfs_add` → direct `ipfs add`) → Nostr post → returns QR code + face results

### Face recognition (face_recognition_module.py)
- Stores face embeddings in `faces/embeddings.json` (JSON, no database)
- Falls back gracefully to MediaPipe if `face_recognition` library unavailable
- Photos stored in `photos/`, face data in `faces/`

## Key API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /` | Main UI |
| `GET /video_feed` | MJPEG camera stream |
| `GET /api/gesture` | Current gesture state & progress |
| `GET /api/events` | Nostr messages with profiles |
| `GET /api/config` | Server config & gesture params |
| `GET /api/faces/stats` | Face database statistics |
| `POST /api/faces/process` | Detect faces in a photo |
| `POST /api/faces/batch` | Batch process all photos |

## Configuration

All gesture/UI parameters are in `.env` (see `.env.template`). Key ones:
- `VITRINE_ZONE_LEFT/RIGHT` — navigation trigger zones (0-1)
- `VITRINE_SWIPE_COOLDOWN` — seconds between swipes
- `VITRINE_THUMBS_UP_HOLD_TIME` — hold duration to capture photo
- `VITRINE_FACE_MATCH_THRESHOLD` — face recognition strictness
- `VITRINE_DARK_MODE_TIMEOUT` — seconds to return to dark mode

Slide config and branding are in `vitrine_config.json`.

## Important Constraints

- **MediaPipe version**: Requires `<0.10.30` (solutions API removed in newer versions). `start_vitrine.sh` auto-downgrades if needed.
- **Single hand detection**: MediaPipe configured for max 1 hand.
- **Polling over WebSocket**: HTTP polling is primary; WebSocket is optional fallback.
- **IPFS/Astroport required**: Full Nostr functionality needs Astroport.ONE running and IPFS daemon active.
