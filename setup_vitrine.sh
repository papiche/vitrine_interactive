#!/bin/bash
################################################################################
# Setup script for Interactive Showcase Vitrine
# Checks dependencies and configuration
################################################################################

echo "=== UPlanet Interactive Showcase Setup ==="
echo ""

# Check Python dependencies
echo "[1/4] Checking Python dependencies..."
python3 -c "import cv2" 2>/dev/null || {
    echo "  ❌ OpenCV not installed. Install with: pip install opencv-python"
    exit 1
}
python3 -c "import mediapipe" 2>/dev/null || {
    echo "  ❌ MediaPipe not installed. Install with: pip install mediapipe"
    exit 1
}
python3 -c "import numpy" 2>/dev/null || {
    echo "  ❌ NumPy not installed. Install with: pip install numpy"
    exit 1
}
echo "  ✅ Python dependencies OK"

# Check GPS file
echo "[2/4] Checking GPS configuration..."
GPS_FILE="$HOME/.zen/GPS"
if [ -f "$GPS_FILE" ]; then
    source "$GPS_FILE"
    if [ -n "${LAT:-}" ] && [ -n "${LON:-}" ]; then
        echo "  ✅ GPS coordinates found: LAT=$LAT, LON=$LON"
    else
        echo "  ⚠️  GPS file exists but LAT/LON not set"
        echo "  Create $GPS_FILE with:"
        echo "    LAT=48.85"
        echo "    LON=2.35"
    fi
else
    echo "  ⚠️  GPS file not found at $GPS_FILE"
    echo "  Create it with:"
    echo "    echo 'LAT=48.85' > $GPS_FILE"
    echo "    echo 'LON=2.35' >> $GPS_FILE"
fi

# Check nostr_get_events.sh
echo "[3/4] Checking NOSTR tools..."
NOSTR_SCRIPT="$HOME/.zen/Astroport.ONE/tools/nostr_get_events.sh"
if [ -f "$NOSTR_SCRIPT" ]; then
    echo "  ✅ nostr_get_events.sh found"
    if [ -x "$NOSTR_SCRIPT" ]; then
        echo "  ✅ Script is executable"
    else
        echo "  ⚠️  Making script executable..."
        chmod +x "$NOSTR_SCRIPT"
    fi
else
    echo "  ⚠️  nostr_get_events.sh not found at $NOSTR_SCRIPT"
    echo "  The showcase will work but won't fetch NOSTR events"
fi

# Check intro video
echo "[4/4] Checking intro video..."
VIDEO_FILE="./UPlanet___Un_Meilleur_Internet.mp4"
if [ -f "$VIDEO_FILE" ]; then
    echo "  ✅ Intro video found: $VIDEO_FILE"
else
    echo "  ⚠️  Intro video not found: $VIDEO_FILE"
    echo "  Please provide an intro video file"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To run the showcase:"
echo "  cd $(pwd)"
echo "  python3 vitrine_interactive.py"
echo ""
echo "Controls:"
echo "  - 'q': Quit"
echo "  - 'r': Reset to intro"
echo "  - Wave your hand: Trigger NOSTR events display"
echo ""





