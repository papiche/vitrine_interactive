#!/usr/bin/env python3
"""
Interactive Showcase - UPlanet Vitrine
Detects "coucou" gesture to trigger Minority Report-style NOSTR events display
"""
import cv2
import mediapipe as mp
import os
import time
import subprocess
import json
import numpy as np
import re
from collections import deque
from datetime import datetime

# --- Configuration ---
INTRO_VIDEO_FILE = './UPlanet___Un_Meilleur_Internet.mp4'
WEBCAM_INDEX = 0
WINDOW_NAME_VIDEO = 'UPlanet Vitrine'
WINDOW_NAME_CONTROL = 'Control'
WINDOW_NAME_DISPLAY = 'NOSTR Events'

# Paths
GPS_FILE = os.path.expanduser('~/.zen/GPS')
NOSTR_GET_EVENTS_SCRIPT = os.path.expanduser('~/.zen/Astroport.ONE/tools/nostr_get_events.sh')

# --- State Management ---
class VitrineState:
    INTRO = "intro"
    WAITING_GESTURE = "waiting_gesture"
    DISPLAYING_EVENTS = "displaying_events"

# --- Initialization ---
SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080  # Default, will be updated
try:
    import pyautogui
    SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
except:
    pass

mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)
mp_drawing = mp.solutions.drawing_utils

# --- GPS Reading ---
def read_gps_coordinates():
    """Read GPS coordinates from ~/.zen/GPS file
    Supports multiple formats:
    - LAT=48.85\nLON=2.35
    - LAT=48.85; LON=2.35
    - LAT=48.85 LON=2.35
    """
    if not os.path.exists(GPS_FILE):
        print(f"[WARNING] GPS file not found at {GPS_FILE}, using default coordinates")
        return 0.00, 0.00
    
    try:
        with open(GPS_FILE, 'r') as f:
            content = f.read()
            lat = None
            lon = None
            
            # Try to parse line by line first
            for line in content.split('\n'):
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Handle LAT=value
                if line.startswith('LAT='):
                    value = line.split('=', 1)[1].strip()
                    # Remove semicolon if present
                    value = value.split(';')[0].strip()
                    try:
                        lat = float(value)
                    except ValueError:
                        continue
                
                # Handle LON=value
                elif line.startswith('LON='):
                    value = line.split('=', 1)[1].strip()
                    # Remove semicolon if present
                    value = value.split(';')[0].strip()
                    try:
                        lon = float(value)
                    except ValueError:
                        continue
            
            # If not found line by line, try parsing the whole content
            if lat is None or lon is None:
                # Try to find LAT=... and LON=... in the entire content
                lat_match = re.search(r'LAT\s*=\s*([0-9.-]+)', content)
                lon_match = re.search(r'LON\s*=\s*([0-9.-]+)', content)
                
                if lat_match:
                    try:
                        lat = float(lat_match.group(1))
                    except ValueError:
                        pass
                
                if lon_match:
                    try:
                        lon = float(lon_match.group(1))
                    except ValueError:
                        pass
            
            if lat is not None and lon is not None:
                print(f"[INFO] GPS coordinates read: LAT={lat}, LON={lon}")
                # Warn if coordinates are default (0,0 is in the ocean)
                if lat == 0.0 and lon == 0.0:
                    print(f"[WARNING] GPS coordinates are 0.0, 0.0 (default/unset)")
                    print(f"[INFO] Please set your actual coordinates in {GPS_FILE}")
                return lat, lon
            else:
                print(f"[WARNING] Could not parse GPS coordinates from {GPS_FILE}")
                print(f"[INFO] File content preview: {content[:200]}")
                return 0.00, 0.00
    except Exception as e:
        print(f"[ERROR] Failed to read GPS file: {e}")
        import traceback
        traceback.print_exc()
        return 0.00, 0.00

# --- Gesture Detection ---
def get_gesture(hand_landmarks):
    """Detect basic hand gestures"""
    fingers = {
        'index': (mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.INDEX_FINGER_PIP),
        'middle': (mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP),
        'ring': (mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_PIP),
        'pinky': (mp_hands.HandLandmark.PINKY_TIP, mp_hands.HandLandmark.PINKY_PIP),
    }
    fingers_up = {}
    for name, (tip_idx, pip_idx) in fingers.items():
        tip_y = hand_landmarks.landmark[tip_idx].y
        pip_y = hand_landmarks.landmark[pip_idx].y
        fingers_up[name] = tip_y < pip_y

    if all(fingers_up.values()): 
        return 'open'
    if not any(fingers_up.values()): 
        return 'closed'
    if fingers_up['index'] and not fingers_up['middle'] and not fingers_up['ring'] and not fingers_up['pinky']:
        return 'pointing'
    return None

def detect_coucou_gesture(hand_landmarks, wrist_history, current_time):
    """
    Detect "coucou" gesture (waving hand)
    Criteria: Hand open + lateral movement (wrist x position oscillates)
    """
    if len(wrist_history) < 5:
        return False
    
    wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
    wrist_history.append((wrist.x, current_time))
    
    # Keep only last 1 second of history
    wrist_history[:] = [(x, t) for x, t in wrist_history if current_time - t < 1.0]
    
    if len(wrist_history) < 5:
        return False
    
    # Check if hand is open
    gesture = get_gesture(hand_landmarks)
    if gesture != 'open':
        return False
    
    # Check for lateral oscillation (waving motion)
    x_positions = [x for x, t in wrist_history]
    x_range = max(x_positions) - min(x_positions)
    
    # Waving: significant lateral movement (threshold: 0.1 in normalized coordinates)
    if x_range > 0.1:
        # Count direction changes (oscillation)
        direction_changes = 0
        for i in range(1, len(x_positions) - 1):
            if (x_positions[i] > x_positions[i-1] and x_positions[i+1] < x_positions[i]) or \
               (x_positions[i] < x_positions[i-1] and x_positions[i+1] > x_positions[i]):
                direction_changes += 1
        
        # Waving detected if at least 2 direction changes
        if direction_changes >= 2:
            return True
    
    return False

# --- NOSTR Events Fetching ---
def get_nostr_events_nearby(lat, lon, radius_km=5.0):
    """
    Fetch NOSTR events near GPS coordinates using nostr_get_events.sh
    Returns list of event dictionaries
    """
    if not os.path.exists(NOSTR_GET_EVENTS_SCRIPT):
        print(f"[WARNING] nostr_get_events.sh not found at {NOSTR_GET_EVENTS_SCRIPT}")
        return []
    
    try:
        # Calculate approximate UMAP cell (0.01° precision)
        umap_lat = round(lat, 2)
        umap_lon = round(lon, 2)
        
        # Query events with geolocation tag
        # Get recent events (last 7 days)
        since_timestamp = int(time.time()) - (7 * 24 * 60 * 60)
        
        all_events = []
        
        # Fetch text notes (kind 1)
        cmd = [
            NOSTR_GET_EVENTS_SCRIPT,
            '--kind', '1',
            '--tag-g', f"{umap_lat},{umap_lon}",
            '--since', str(since_timestamp),
            '--limit', '50',
            '--output', 'json'
        ]
        
        print(f"[INFO] Fetching NOSTR events near {umap_lat},{umap_lon}...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        event = json.loads(line)
                        all_events.append(event)
                    except json.JSONDecodeError:
                        continue
        
        # Also fetch DID documents (kind 30800) in the area
        cmd_did = [
            NOSTR_GET_EVENTS_SCRIPT,
            '--kind', '30800',
            '--tag-g', f"{umap_lat},{umap_lon}",
            '--since', str(since_timestamp),
            '--limit', '20',
            '--output', 'json'
        ]
        
        result_did = subprocess.run(cmd_did, capture_output=True, text=True, timeout=10)
        if result_did.returncode == 0:
            for line in result_did.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        event = json.loads(line)
                        all_events.append(event)
                    except json.JSONDecodeError:
                        continue
        
        # Sort by created_at (newest first)
        all_events.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        
        print(f"[INFO] Found {len(all_events)} NOSTR events (notes + DIDs)")
        return all_events
        
    except subprocess.TimeoutExpired:
        print("[ERROR] Timeout fetching NOSTR events")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to fetch NOSTR events: {e}")
        return []

# --- Minority Report Display ---
def create_minority_report_display(events, screen_width, screen_height):
    """
    Create a Minority Report-style display of NOSTR events
    Returns OpenCV image with futuristic UI
    """
    # Create dark blue/black background (futuristic)
    display = np.zeros((screen_height, screen_width, 3), dtype=np.uint8)
    display[:, :] = (5, 5, 15)  # Dark blue background
    
    if not events:
        # No events message with style
        text = "No NOSTR events found nearby"
        subtext = "Check back later or move to a different location"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, 2, 3)[0]
        text_x = (screen_width - text_size[0]) // 2
        text_y = screen_height // 2
        
        # Glowing effect
        cv2.putText(display, text, (text_x, text_y), font, 2, (0, 100, 255), 5)
        cv2.putText(display, text, (text_x, text_y), font, 2, (0, 255, 255), 3)
        
        subtext_size = cv2.getTextSize(subtext, font, 0.8, 2)[0]
        subtext_x = (screen_width - subtext_size[0]) // 2
        cv2.putText(display, subtext, (subtext_x, text_y + 60), font, 0.8, (150, 150, 150), 2)
        return display
    
    # Display events in Minority Report style
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 2
    margin = 60
    card_spacing = 15
    
    y_offset = 80
    
    # Title with glow effect
    title = "NOSTR EVENTS - DECENTRALIZED NETWORK"
    subtitle = f"Found {len(events)} events in your area"
    title_size = cv2.getTextSize(title, font, 1.2, 3)[0]
    title_x = (screen_width - title_size[0]) // 2
    
    # Title glow
    cv2.putText(display, title, (title_x, y_offset), font, 1.2, (0, 50, 150), 5)
    cv2.putText(display, title, (title_x, y_offset), font, 1.2, (0, 200, 255), 3)
    
    subtitle_size = cv2.getTextSize(subtitle, font, 0.7, 2)[0]
    subtitle_x = (screen_width - subtitle_size[0]) // 2
    cv2.putText(display, subtitle, (subtitle_x, y_offset + 40), font, 0.7, (100, 255, 100), 2)
    
    y_offset += 100
    
    # Display events in cards
    for i, event in enumerate(events[:25]):  # Limit to 25 events
        if y_offset > screen_height - 120:
            break
        
        # Extract event data
        event_kind = event.get('kind', 0)
        event_id = event.get('id', '')[:12] + '...'
        content = event.get('content', '')
        created_at = event.get('created_at', 0)
        pubkey = event.get('pubkey', '')[:12] + '...'
        
        # Parse DID if kind 30800
        event_type = "Note"
        event_color = (200, 200, 255)  # Light blue for notes
        if event_kind == 30800:
            event_type = "DID Document"
            event_color = (100, 255, 100)  # Green for DIDs
            try:
                did_content = json.loads(content)
                did_id = did_content.get('id', 'did:nostr:...')
                if 'metadata' in did_content:
                    email = did_content['metadata'].get('email', '')
                    if email:
                        content = f"DID: {did_id}\nEmail: {email}"
            except:
                pass
        
        # Format timestamp
        try:
            dt = datetime.fromtimestamp(created_at)
            time_str = dt.strftime('%H:%M:%S')
            date_str = dt.strftime('%Y-%m-%d')
        except:
            time_str = "??:??:??"
            date_str = "????-??-??"
        
        # Truncate content if too long (wrap text)
        max_content_len = 100
        if len(content) > max_content_len:
            content = content[:max_content_len-3] + '...'
        
        # Card dimensions
        card_y = y_offset
        card_height = 100
        card_x = margin
        card_width = screen_width - 2 * margin
        
        # Card background with gradient effect
        overlay = display.copy()
        # Different colors for different event types
        if event_kind == 30800:
            card_color = (10, 30, 10)  # Dark green tint
        else:
            card_color = (15, 15, 25)  # Dark blue tint
        
        cv2.rectangle(overlay, (card_x, card_y), (card_x + card_width, card_y + card_height), 
                     card_color, -1)
        # Border
        cv2.rectangle(overlay, (card_x, card_y), (card_x + card_width, card_y + card_height), 
                     event_color, 2)
        cv2.addWeighted(overlay, 0.8, display, 0.2, 0, display)
        
        # Event number and type (left side)
        event_label = f"#{i+1} [{event_type}]"
        cv2.putText(display, event_label, (card_x + 15, card_y + 25), 
                   font, 0.6, event_color, 2)
        
        # Event ID (small, top right)
        id_text = f"ID: {event_id}"
        id_size = cv2.getTextSize(id_text, font, 0.4, 1)[0]
        cv2.putText(display, id_text, (card_x + card_width - id_size[0] - 15, card_y + 25), 
                   font, 0.4, (150, 150, 150), 1)
        
        # Content (main area)
        content_y = card_y + 50
        # Split content into lines if needed
        words = content.split(' ')
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            test_size = cv2.getTextSize(test_line, font, font_scale, thickness)[0]
            if test_size[0] > card_width - 40:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
        
        for line_idx, line in enumerate(lines[:2]):  # Max 2 lines
            cv2.putText(display, line, (card_x + 15, content_y + line_idx * 25), 
                       font, font_scale, (255, 255, 255), thickness)
        
        # Timestamp and pubkey (bottom)
        info_text = f"{date_str} {time_str} | Author: {pubkey}"
        info_size = cv2.getTextSize(info_text, font, 0.4, 1)[0]
        cv2.putText(display, info_text, (card_x + 15, card_y + card_height - 10), 
                   font, 0.4, (180, 180, 180), 1)
        
        y_offset += card_height + card_spacing
    
    # Footer
    footer_text = "UPlanet Interactive Showcase | Press 'q' to quit, 'r' to reset"
    footer_size = cv2.getTextSize(footer_text, font, 0.5, 1)[0]
    footer_x = (screen_width - footer_size[0]) // 2
    cv2.putText(display, footer_text, (footer_x, screen_height - 20), 
               font, 0.5, (100, 100, 100), 1)
    
    return display

# --- Main Program ---
def main():
    # Check intro video
    if not os.path.exists(INTRO_VIDEO_FILE):
        print(f"[ERROR] Intro video file '{INTRO_VIDEO_FILE}' not found.")
        print("[INFO] Please provide an intro video file.")
        return
    
    # Read GPS coordinates
    lat, lon = read_gps_coordinates()
    print(f"[INFO] GPS coordinates: LAT={lat}, LON={lon}")
    
    # Initialize video capture
    cap_webcam = cv2.VideoCapture(WEBCAM_INDEX)
    cap_video = cv2.VideoCapture(INTRO_VIDEO_FILE)
    
    if not cap_webcam.isOpened():
        print(f"[ERROR] Could not open webcam {WEBCAM_INDEX}")
        return
    
    # State management
    state = VitrineState.INTRO
    wrist_history = deque(maxlen=30)
    last_gesture_time = 0
    gesture_cooldown = 2.0  # 2 seconds cooldown after gesture detection
    events_data = []
    events_display = None
    
    # Window setup
    cv2.namedWindow(WINDOW_NAME_VIDEO, cv2.WINDOW_NORMAL)
    cv2.namedWindow(WINDOW_NAME_CONTROL, cv2.WINDOW_NORMAL)
    cv2.namedWindow(WINDOW_NAME_DISPLAY, cv2.WINDOW_NORMAL)
    
    # Set window positions
    cv2.moveWindow(WINDOW_NAME_VIDEO, 0, 0)
    cv2.moveWindow(WINDOW_NAME_CONTROL, SCREEN_WIDTH - 400, SCREEN_HEIGHT - 300)
    cv2.moveWindow(WINDOW_NAME_DISPLAY, 0, 0)
    
    # Make video window fullscreen
    cv2.setWindowProperty(WINDOW_NAME_VIDEO, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setWindowProperty(WINDOW_NAME_DISPLAY, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    print("[INFO] Interactive showcase started.")
    print("[INFO] Phase 1: Intro video playing...")
    print("[INFO] Phase 2: Waiting for 'coucou' gesture...")
    print("[INFO] Press 'q' to quit.")
    
    video_w, video_h = 0, 0
    is_playing_intro = True
    
    while cap_webcam.isOpened():
        ret_cam, cam_frame = cap_webcam.read()
        if not ret_cam:
            break
        
        cam_frame = cv2.flip(cam_frame, 1)
        rgb_frame = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2RGB)
        results = hands_detector.process(rgb_frame)
        
        current_time = time.time()
        
        # State: INTRO - Play intro video
        if state == VitrineState.INTRO:
            if is_playing_intro:
                ret_vid, video_frame = cap_video.read()
                if not ret_vid:
                    # Loop video
                    cap_video.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret_vid, video_frame = cap_video.read()
                
                if ret_vid:
                    if video_w == 0:
                        video_h, video_w, _ = video_frame.shape
                    
                    # Add invitation text overlay
                    overlay = video_frame.copy()
                    text = "Wave your hand to discover NOSTR events!"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    text_size = cv2.getTextSize(text, font, 1.2, 3)[0]
                    text_x = (video_w - text_size[0]) // 2
                    text_y = video_h - 50
                    cv2.rectangle(overlay, (text_x - 20, text_y - 40), 
                                 (text_x + text_size[0] + 20, text_y + 10), 
                                 (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.6, video_frame, 0.4, 0, video_frame)
                    cv2.putText(video_frame, text, (text_x, text_y), 
                               font, 1.2, (0, 255, 255), 3)
                    
                    cv2.imshow(WINDOW_NAME_VIDEO, video_frame)
            
            # Check for coucou gesture to transition
            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                mp_drawing.draw_landmarks(cam_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                
                if detect_coucou_gesture(hand_landmarks, wrist_history, current_time):
                    if (current_time - last_gesture_time) > gesture_cooldown:
                        print("[INFO] 'Coucou' gesture detected! Fetching NOSTR events...")
                        state = VitrineState.DISPLAYING_EVENTS
                        is_playing_intro = False
                        last_gesture_time = current_time
                        
                        # Fetch NOSTR events
                        events_data = get_nostr_events_nearby(lat, lon)
                        if events_data:
                            events_display = create_minority_report_display(
                                events_data, SCREEN_WIDTH, SCREEN_HEIGHT
                            )
                            print(f"[INFO] Displaying {len(events_data)} NOSTR events")
                        else:
                            print("[INFO] No events found, creating empty display")
                            events_display = create_minority_report_display(
                                [], SCREEN_WIDTH, SCREEN_HEIGHT
                            )
        
        # State: DISPLAYING_EVENTS - Show Minority Report interface
        elif state == VitrineState.DISPLAYING_EVENTS:
            if events_display is not None:
                cv2.imshow(WINDOW_NAME_DISPLAY, events_display)
            
            # Draw hand landmarks on control window
            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                mp_drawing.draw_landmarks(cam_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
        
        # Control window (always show camera feed)
        status_text = f"State: {state.upper()}"
        if state == VitrineState.INTRO:
            status_text += " - Wave to interact!"
        elif state == VitrineState.DISPLAYING_EVENTS:
            status_text += f" - {len(events_data)} events"
        
        cv2.putText(cam_frame, status_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow(WINDOW_NAME_CONTROL, cam_frame)
        
        # Handle key press
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            # Reset to intro
            print("[INFO] Resetting to intro...")
            state = VitrineState.INTRO
            is_playing_intro = True
            cap_video.set(cv2.CAP_PROP_POS_FRAMES, 0)
            events_data = []
            events_display = None
            wrist_history.clear()
    
    print("[INFO] Stopping showcase...")
    cap_webcam.release()
    cap_video.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

