#!/bin/bash
###############################################################################
# UPlanet Vitrine Interactive - Startup Script
#
# Starts the gesture-controlled Nostr message carousel
# Uses the ~/.astro Python virtual environment
#
# Usage:
#   ./start_vitrine.sh [--port PORT] [--camera INDEX]
#
# Default:
#   Port: 5555
#   Camera: 0 (first camera)
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${HOME}/.astro"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
cat << 'EOF'
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   🌍 UPlanet Vitrine Interactive                             ║
    ║   ─────────────────────────────────────────────────────────  ║
    ║                                                              ║
    ║   📡 Nostr Message Carousel with Gesture Control             ║
    ║   🖐️  "Minority Report" style navigation                     ║
    ║   📷 Thumbs up to capture & post photos                      ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check Python virtual environment
if [[ ! -d "$VENV_PATH" ]]; then
    echo -e "${YELLOW}[WARN] Virtual environment not found at $VENV_PATH${NC}"
    echo -e "${YELLOW}[INFO] Creating virtual environment...${NC}"
    python3 -m venv "$VENV_PATH"
fi

# Activate virtual environment
echo -e "${GREEN}[INFO] Activating virtual environment: $VENV_PATH${NC}"
source "$VENV_PATH/bin/activate"

# Check and install dependencies
echo -e "${GREEN}[INFO] Checking dependencies...${NC}"

# Required packages
REQUIRED_PACKAGES=(
    "flask"
    "flask-cors"
    "flask-socketio"
    "opencv-python"
    "mediapipe"
    "numpy"
    "qrcode"
    "Pillow"
    "requests"
)

# Install missing packages
for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if ! python3 -c "import ${pkg//-/_}" 2>/dev/null; then
        # Handle special cases
        case $pkg in
            "opencv-python")
                python3 -c "import cv2" 2>/dev/null || pip install opencv-python-headless --quiet
                ;;
            "flask-cors")
                python3 -c "import flask_cors" 2>/dev/null || pip install flask-cors --quiet
                ;;
            "flask-socketio")
                python3 -c "import flask_socketio" 2>/dev/null || pip install flask-socketio --quiet
                ;;
            "Pillow")
                python3 -c "import PIL" 2>/dev/null || pip install Pillow --quiet
                ;;
			"mediapipe")
                # Forcer une version < 0.10.30 car l'API solutions a été retirée
                pip install "mediapipe<0.10.30" --quiet
                ;;
            *)
                pip install "$pkg" --quiet
                ;;
        esac
        echo -e "${YELLOW}[INFO] Installed: $pkg${NC}"
    fi
done

# NOUVEAU : Forcer le downgrade si la version installée est trop récente et ne possède pas l'API "solutions"
if ! python3 -c "import mediapipe.solutions" 2>/dev/null; then
    echo -e "${YELLOW}[INFO] Downgrading mediapipe to a version < 0.10.30 (Solutions API required)...${NC}"
    pip install "mediapipe<0.10.30" --quiet
fi

echo -e "${GREEN}[OK] All dependencies installed${NC}"

# Change to script directory
cd "$SCRIPT_DIR"

# Parse arguments
PORT=5555
CAMERA=0
DEBUG=""
PROFILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --port|-p)
            PORT="$2"
            shift 2
            ;;
        --camera|-c)
            CAMERA="$2"
            shift 2
            ;;
        --debug|-d)
            DEBUG="--debug"
            shift
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--port PORT] [--camera INDEX] [--debug] [--profile PROFILE]"
            echo ""
            echo "Options:"
            echo "  --port, -p       Server port (default: 5555)"
            echo "  --camera, -c     Camera index (default: 0)"
            echo "  --debug, -d      Enable debug mode"
            echo "  --profile        Force hardware profile: minimal|low|medium|high"
            echo "                   (auto-detected if omitted)"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Set hardware profile override if specified
if [[ -n "$PROFILE" ]]; then
    export VITRINE_PROFILE="$PROFILE"
    echo -e "${YELLOW}[INFO] Hardware profile override: $PROFILE${NC}"
fi

echo -e "${GREEN}[INFO] Starting server on port $PORT with camera $CAMERA${NC}"
echo -e "${CYAN}[INFO] Open http://127.0.0.1:$PORT in your browser${NC}"
echo ""

# Start the server
python3 vitrine.py --port "$PORT" --camera "$CAMERA" $DEBUG

