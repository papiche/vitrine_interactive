#!/bin/bash
################################################################################
# Setup script for Interactive Showcase Vitrine
# Checks dependencies and configuration
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== UPlanet Interactive Showcase Setup ==="
echo ""

# Check Python dependencies
echo "[1/5] Checking Python dependencies..."
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
echo "[2/5] Checking GPS configuration..."
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
echo "[3/5] Checking NOSTR tools..."
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

# Check intro video (optional)
echo "[4/5] Checking intro video..."
VIDEO_FILE="$SCRIPT_DIR/Intro.mp4"
if [ -f "$VIDEO_FILE" ]; then
    echo "  ✅ Intro video found: $VIDEO_FILE"
else
    echo "  ⚠️  Intro video not found: $VIDEO_FILE (optional)"
fi

# Check .env and offer manage_env.sh
echo "[5/5] Checking .env..."
ENV_FILE="$SCRIPT_DIR/.env"
MANAGE_ENV="$SCRIPT_DIR/manage_env.sh"
if [ -f "$ENV_FILE" ]; then
    echo "  ✅ .env found"
else
    echo "  ⚠️  .env not found (gesture/face params will use defaults)"
    echo "  Create from template: ./manage_env.sh init"
    if [ -x "$MANAGE_ENV" ]; then
        echo ""
        read -r -p "  Run ./manage_env.sh init now? [y/N] " reply
        case "${reply:-n}" in
            [yY][eE][sS]|[yY])
                "$MANAGE_ENV" init
                echo "  Edit .env if needed: ./manage_env.sh show"
                ;;
            *) echo "  Run later: ./manage_env.sh init" ;;
        esac
    fi
fi
if [ -x "$MANAGE_ENV" ]; then
    echo "  Manage config: ./manage_env.sh (init|show|set|get|validate|help)"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To run the showcase:"
echo "  cd $SCRIPT_DIR"
echo "  ./start_vitrine.sh"
echo ""
echo "To manage .env (zones, durations, face recognition):"
echo "  ./manage_env.sh help"
echo ""





