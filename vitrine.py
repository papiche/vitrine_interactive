#!/usr/bin/env python3
"""
UPlanet Shop Carousel - Vitrine Interactive
A "Minority Report" style gesture-controlled interface for displaying Nostr messages.

Features:
- Hand detection via MediaPipe (webcam stream)
- iPod Cover Flow style navigation
- Horizontal swipe for message navigation
- Open hand to show message details
- Thumbs up to capture photo and post to Nostr
- QR code display for http://127.0.0.1:54321/g1

Usage:
    source ~/.astro/bin/activate
    python vitrine.py [--port PORT] [--camera INDEX]

Author: CopyLaRadio - UPlanet
"""

import os
import sys
import json
import time
import base64
import subprocess
import threading
import argparse
import re
import requests
from datetime import datetime
from pathlib import Path
from io import BytesIO
from collections import deque

# Flask for web server
from flask import Flask, Response, render_template, jsonify, request, send_from_directory
from flask_cors import CORS

# Computer Vision
import cv2
import numpy as np

# MediaPipe for hand detection
import mediapipe as mp

# QR Code generation
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
    print("[WARN] qrcode not installed. pip install qrcode[pil]")

# --- CONFIGURATION ---
HOME = os.path.expanduser("~")
ASTROPORT_PATH = os.path.join(HOME, ".zen/Astroport.ONE")
NOSTR_SCRIPT = os.path.join(ASTROPORT_PATH, "tools/nostr_get_events.sh")
NOSTR_SEND_SCRIPT = os.path.join(ASTROPORT_PATH, "tools/nostr_send_note.py")
PHOTOS_DIR = Path(__file__).parent / "photos"
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

# Ensure directories exist
PHOTOS_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Default camera and display settings
DEFAULT_CAMERA = 0
DEFAULT_PORT = 5555
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Gesture detection zones (normalized 0-1)
ZONE_LEFT = 0.25    # Left 25% -> Previous
ZONE_RIGHT = 0.75   # Right 25% -> Next
ZONE_CENTER = (0.35, 0.65)  # Center 30% -> Detail view

# Gesture thresholds
SWIPE_COOLDOWN = 0.5  # Seconds between swipes
THUMBS_UP_HOLD_TIME = 1.5  # Seconds to hold thumbs up
OPEN_HAND_HOLD_TIME = 1.0  # Seconds to hold open hand for detail view
QR_DISPLAY_TIME = 10  # Seconds to display QR code
DARK_MODE_TIMEOUT = 60  # Seconds without hand to switch back to dark mode

# --- FLASK APP ---
app = Flask(__name__, 
            template_folder=str(TEMPLATES_DIR),
            static_folder=str(STATIC_DIR))
CORS(app)

# --- GLOBAL STATE ---
class GestureState:
    """Tracks gesture detection state"""
    def __init__(self):
        self.hand_detected = False
        self.hand_x = 0.5  # Normalized X position (0-1)
        self.hand_y = 0.5  # Normalized Y position (0-1)
        self.fingers_open = 0  # Count of extended fingers
        self.is_open_hand = False
        self.is_thumbs_up = False
        self.is_fist = False
        self.gesture_name = "none"
        self.action = "idle"  # idle, nav_left, nav_right, detail, detail_close, capture
        self.last_swipe_time = 0
        self.thumbs_up_start = 0
        self.open_hand_start = 0  # Track open hand hold time
        self.current_index = 0  # Current message index
        self.show_detail = False
        self.detail_opened = False  # Track if detail was opened by gesture
        self.show_qr = False
        self.qr_start_time = 0
        self.photo_captured = False
        self.last_photo_path = None
        # Light/Dark mode based on hand presence
        self.light_mode = False
        self.last_hand_seen = 0  # Timestamp when hand was last seen
        self.lock = threading.Lock()

gesture_state = GestureState()

class NostrFeed:
    """Manages Nostr event feed"""
    def __init__(self):
        self.events = []
        self.profiles = {}  # Cache: pubkey -> profile data
        self.loading = True
        self.last_refresh = 0
        self.lock = threading.Lock()
        self._start_refresh_thread()
    
    def _start_refresh_thread(self):
        t = threading.Thread(target=self._refresh_loop, daemon=True)
        t.start()
    
    def _refresh_loop(self):
        while True:
            self._fetch_events()
            self._fetch_profiles()
            time.sleep(30)  # Refresh every 30 seconds
    
    def _fetch_profiles(self):
        """Fetch profiles (kind 0) for all authors"""
        # Get unique pubkeys from events
        with self.lock:
            pubkeys = list(set(e.get('pubkey', '') for e in self.events if e.get('pubkey')))
        
        if not pubkeys or not os.path.exists(NOSTR_SCRIPT):
            return
        
        print(f"[NOSTR] Fetching profiles for {len(pubkeys)} authors...")
        
        for pubkey in pubkeys:
            if pubkey in self.profiles:
                continue  # Already cached
            
            try:
                # Fetch kind 0 for this author
                cmd = [NOSTR_SCRIPT, "--kind", "0", "--author", pubkey, "--limit", "1", "--output", "json"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        if not line.strip():
                            continue
                        try:
                            ev = json.loads(line)
                            # Parse content as JSON (profile data)
                            content = ev.get('content', '{}')
                            profile_data = json.loads(content) if content else {}
                            
                            with self.lock:
                                self.profiles[pubkey] = {
                                    'name': profile_data.get('name', ''),
                                    'display_name': profile_data.get('display_name', ''),
                                    'picture': profile_data.get('picture', ''),
                                    'about': profile_data.get('about', ''),
                                    'nip05': profile_data.get('nip05', ''),
                                    'banner': profile_data.get('banner', ''),
                                    'lud16': profile_data.get('lud16', ''),
                                    'website': profile_data.get('website', ''),
                                }
                            break
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"[NOSTR] Profile fetch error for {pubkey[:8]}: {e}")
        
        print(f"[NOSTR] Cached {len(self.profiles)} profiles")
    
    def _extract_images(self, content, tags=None):
        """Extract image URLs from content and imeta tags"""
        images = []
        
        # Extract from content
        url_pattern = r'(https?://[^\s<>"{}|\\^`\[\]]+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s<>"{}|\\^`\[\]]*)?)'
        content_images = re.findall(url_pattern, content, re.IGNORECASE)
        images.extend(content_images)
        
        # Extract from imeta tags (NIP-94)
        if tags:
            for tag in tags:
                if tag[0] == 'imeta':
                    for i, item in enumerate(tag[1:], 1):
                        if isinstance(item, str):
                            if item.startswith('url '):
                                url = item[4:].strip()
                                if url.startswith('http'):
                                    images.append(url)
                            elif item.startswith('http') and any(ext in item.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                                images.append(item)
        
        return list(set(images))  # Remove duplicates
    
    def _fetch_events(self):
        """Fetch events from Nostr relay"""
        print("[NOSTR] Fetching events...")
        new_events = []
        
        try:
            if not os.path.exists(NOSTR_SCRIPT):
                raise FileNotFoundError(f"Script not found: {NOSTR_SCRIPT}")
            
            cmd = [NOSTR_SCRIPT, "--kind", "1", "--limit", "50", "--output", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if not line.strip():
                        continue
                    try:
                        ev = json.loads(line)
                        images = self._extract_images(ev.get('content', ''), ev.get('tags', []))
                        
                        # Clean content by removing image URLs
                        clean_content = ev.get('content', '')
                        for img_url in images:
                            clean_content = clean_content.replace(img_url, '')
                        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
                        
                        new_events.append({
                            'id': ev.get('id', ''),
                            'pubkey': ev.get('pubkey', ''),
                            'created_at': ev.get('created_at', 0),
                            'content': clean_content,
                            'images': images,
                            'tags': ev.get('tags', [])
                        })
                    except json.JSONDecodeError:
                        continue
            
        except Exception as e:
            print(f"[NOSTR] Error: {e}")
            # Demo data fallback
            demos = [
                {"content": "Welcome to UPlanet CopyLaRadio! 🌍", "images": ["https://raw.githubusercontent.com/papiche/Astroport.ONE/master/ASTROPORT_STATION.png"]},
                {"content": "Decentralized computing powered by Ğ1 libre currency. Join the revolution! 💚", "images": []},
                {"content": "Your data, your rules. No GAFAM surveillance here. 🔒", "images": []},
                {"content": "Powered by IPFS, Nostr, and cooperative economics. 🚀", "images": ["https://ipfs.io/ipfs/QmVLRqJbEQP8h7VQHRuWNZKkBSPbdRNh8LYBGVZVkCWgJF"]},
            ]
            for i, demo in enumerate(demos):
                new_events.append({
                    'id': f'demo_{i}',
                    'pubkey': 'copylaradio',
                    'created_at': int(time.time()) - i * 3600,
                    'content': demo['content'],
                    'images': demo['images'],
                    'tags': []
                })
        
        with self.lock:
            new_events.sort(key=lambda x: x['created_at'], reverse=True)
            self.events = new_events
            self.loading = False
            self.last_refresh = time.time()
            print(f"[NOSTR] Loaded {len(self.events)} events")
    
    def get_events(self):
        with self.lock:
            # Add profile data to each event
            events_with_profiles = []
            for ev in self.events:
                ev_copy = dict(ev)
                pubkey = ev.get('pubkey', '')
                ev_copy['profile'] = self.profiles.get(pubkey, {})
                events_with_profiles.append(ev_copy)
            return events_with_profiles
    
    def get_event(self, index):
        with self.lock:
            if 0 <= index < len(self.events):
                ev = dict(self.events[index])
                pubkey = ev.get('pubkey', '')
                ev['profile'] = self.profiles.get(pubkey, {})
                return ev
            return None
    
    def get_profile(self, pubkey):
        with self.lock:
            return self.profiles.get(pubkey, {})
    
    def count(self):
        with self.lock:
            return len(self.events)

nostr_feed = NostrFeed()

# --- CAMERA & HAND DETECTION ---
class CameraHandler:
    """Handles camera capture and hand detection"""
    
    def __init__(self, camera_index=DEFAULT_CAMERA):
        self.camera_index = camera_index
        self.cap = None
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.running = False
        self.frame_lock = threading.Lock()
        self.current_frame = None
        self.processed_frame = None
    
    def start(self):
        """Start camera capture"""
        if self.running:
            return
        
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            print(f"[CAMERA] Failed to open camera {self.camera_index}")
            return False
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        self.running = True
        t = threading.Thread(target=self._capture_loop, daemon=True)
        t.start()
        print(f"[CAMERA] Started on index {self.camera_index}")
        return True
    
    def stop(self):
        """Stop camera capture"""
        self.running = False
        if self.cap:
            self.cap.release()
    
    def _count_extended_fingers(self, hand_landmarks):
        """Count extended fingers"""
        tips = [
            self.mp_hands.HandLandmark.THUMB_TIP,
            self.mp_hands.HandLandmark.INDEX_FINGER_TIP,
            self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
            self.mp_hands.HandLandmark.RING_FINGER_TIP,
            self.mp_hands.HandLandmark.PINKY_TIP
        ]
        
        pips = [
            self.mp_hands.HandLandmark.THUMB_IP,
            self.mp_hands.HandLandmark.INDEX_FINGER_PIP,
            self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP,
            self.mp_hands.HandLandmark.RING_FINGER_PIP,
            self.mp_hands.HandLandmark.PINKY_PIP
        ]
        
        count = 0
        for i, (tip, pip) in enumerate(zip(tips, pips)):
            tip_y = hand_landmarks.landmark[tip].y
            pip_y = hand_landmarks.landmark[pip].y
            
            # For thumb, check x-axis instead
            if i == 0:
                tip_x = hand_landmarks.landmark[tip].x
                pip_x = hand_landmarks.landmark[pip].x
                # Check if thumb is extended (depends on handedness)
                if abs(tip_x - pip_x) > 0.05:
                    count += 1
            else:
                # Finger is extended if tip is above pip
                if tip_y < pip_y - 0.02:
                    count += 1
        
        return count
    
    def _detect_thumbs_up(self, hand_landmarks):
        """Detect thumbs up gesture - improved detection"""
        thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
        thumb_ip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_IP]
        thumb_mcp = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_MCP]
        thumb_cmc = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_CMC]
        
        index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
        index_pip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_PIP]
        middle_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
        middle_pip = hand_landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP]
        ring_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.RING_FINGER_TIP]
        ring_pip = hand_landmarks.landmark[self.mp_hands.HandLandmark.RING_FINGER_PIP]
        pinky_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.PINKY_TIP]
        pinky_pip = hand_landmarks.landmark[self.mp_hands.HandLandmark.PINKY_PIP]
        
        wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
        
        # Thumb is pointing up (tip above mcp significantly)
        # More lenient: check thumb is extended upward relative to its base
        thumb_extended_up = thumb_tip.y < thumb_mcp.y - 0.05
        
        # Alternative: thumb tip is highest point
        thumb_is_highest = (
            thumb_tip.y < index_tip.y and
            thumb_tip.y < middle_tip.y and
            thumb_tip.y < ring_tip.y and
            thumb_tip.y < pinky_tip.y
        )
        
        # Other fingers are curled (tip below pip = curled)
        index_curled = index_tip.y > index_pip.y
        middle_curled = middle_tip.y > middle_pip.y
        ring_curled = ring_tip.y > ring_pip.y
        pinky_curled = pinky_tip.y > pinky_pip.y
        
        # Count curled fingers (need at least 3 curled)
        curled_count = sum([index_curled, middle_curled, ring_curled, pinky_curled])
        fingers_mostly_closed = curled_count >= 3
        
        # Thumbs up = thumb extended up AND other fingers mostly curled
        return (thumb_extended_up or thumb_is_highest) and fingers_mostly_closed
    
    def _process_gestures(self, hand_landmarks):
        """Process hand landmarks to detect gestures"""
        global gesture_state
        
        # Get palm center (approximate with index finger mcp)
        palm_x = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_MCP].x
        palm_y = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_MCP].y
        
        fingers_open = self._count_extended_fingers(hand_landmarks)
        is_thumbs_up = self._detect_thumbs_up(hand_landmarks)
        is_open_hand = fingers_open >= 4
        is_fist = fingers_open <= 1
        
        with gesture_state.lock:
            gesture_state.hand_detected = True
            gesture_state.hand_x = 1.0 - palm_x  # Flip for mirror view
            gesture_state.hand_y = palm_y
            gesture_state.fingers_open = fingers_open
            gesture_state.is_open_hand = is_open_hand
            gesture_state.is_thumbs_up = is_thumbs_up
            gesture_state.is_fist = is_fist
            
            # Determine action
            current_time = time.time()
            
            # Track last time hand was seen for light/dark mode
            gesture_state.last_hand_seen = current_time
            gesture_state.light_mode = True  # Switch to light mode when hand detected
            
            if is_thumbs_up:
                gesture_state.gesture_name = "thumbs_up"
                gesture_state.open_hand_start = 0  # Reset open hand timer
                if gesture_state.thumbs_up_start == 0:
                    gesture_state.thumbs_up_start = current_time
                elif current_time - gesture_state.thumbs_up_start >= THUMBS_UP_HOLD_TIME:
                    if not gesture_state.photo_captured:
                        gesture_state.action = "capture"
                        gesture_state.photo_captured = True
            else:
                gesture_state.thumbs_up_start = 0
                gesture_state.photo_captured = False
                
                if is_open_hand:
                    gesture_state.gesture_name = "open_hand"
                    # Track open hand hold time for detail view
                    if gesture_state.open_hand_start == 0:
                        gesture_state.open_hand_start = current_time
                    elif current_time - gesture_state.open_hand_start >= OPEN_HAND_HOLD_TIME:
                        if not gesture_state.detail_opened:
                            gesture_state.action = "detail"
                            gesture_state.show_detail = True
                            gesture_state.detail_opened = True
                elif is_fist:
                    gesture_state.gesture_name = "fist"
                    gesture_state.open_hand_start = 0
                    # Close detail when making a fist
                    if gesture_state.detail_opened:
                        gesture_state.action = "detail_close"
                        gesture_state.show_detail = False
                        gesture_state.detail_opened = False
                else:
                    gesture_state.gesture_name = "pointing"
                    gesture_state.open_hand_start = 0
                    
                    # Navigation based on hand position
                    if current_time - gesture_state.last_swipe_time > SWIPE_COOLDOWN:
                        if gesture_state.hand_x < ZONE_LEFT:
                            gesture_state.action = "nav_left"
                            gesture_state.last_swipe_time = current_time
                        elif gesture_state.hand_x > ZONE_RIGHT:
                            gesture_state.action = "nav_right"
                            gesture_state.last_swipe_time = current_time
                        else:
                            gesture_state.action = "idle"
    
    def _capture_loop(self):
        """Main capture loop"""
        global gesture_state
        
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            
            # Mirror the frame
            frame = cv2.flip(frame, 1)
            
            # Convert to RGB for MediaPipe
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb)
            
            # Process hand detection
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    self._process_gestures(hand_landmarks)
                    
                    # Draw hand skeleton
                    self.mp_draw.draw_landmarks(
                        frame, 
                        hand_landmarks, 
                        self.mp_hands.HAND_CONNECTIONS,
                        self.mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                        self.mp_draw.DrawingSpec(color=(255, 0, 0), thickness=2)
                    )
            else:
                with gesture_state.lock:
                    gesture_state.hand_detected = False
                    gesture_state.gesture_name = "none"
                    gesture_state.thumbs_up_start = 0
                    gesture_state.open_hand_start = 0
                    
                    current_time = time.time()
                    
                    # Close detail when hand disappears
                    if gesture_state.detail_opened:
                        gesture_state.action = "detail_close"
                        gesture_state.show_detail = False
                        gesture_state.detail_opened = False
                    else:
                        gesture_state.action = "idle"
                    
                    # Switch to dark mode after timeout without hand
                    if gesture_state.last_hand_seen > 0:
                        time_since_hand = current_time - gesture_state.last_hand_seen
                        if time_since_hand >= DARK_MODE_TIMEOUT:
                            gesture_state.light_mode = False
            
            # Draw gesture info on frame
            with gesture_state.lock:
                action = gesture_state.action
                gesture = gesture_state.gesture_name
                hand_x = gesture_state.hand_x
            
            # Draw zone indicators
            h, w = frame.shape[:2]
            cv2.line(frame, (int(w * ZONE_LEFT), 0), (int(w * ZONE_LEFT), h), (100, 100, 100), 1)
            cv2.line(frame, (int(w * ZONE_RIGHT), 0), (int(w * ZONE_RIGHT), h), (100, 100, 100), 1)
            
            # Draw gesture text
            cv2.putText(frame, f"Gesture: {gesture}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame, f"Action: {action}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            with self.frame_lock:
                self.current_frame = frame.copy()
                self.processed_frame = frame
    
    def get_frame(self):
        """Get current frame as JPEG bytes"""
        with self.frame_lock:
            if self.processed_frame is None:
                return None
            ret, jpeg = cv2.imencode('.jpg', self.processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return jpeg.tobytes() if ret else None
    
    def capture_photo(self):
        """Capture current frame as photo"""
        with self.frame_lock:
            if self.current_frame is None:
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo_{timestamp}.jpg"
            filepath = PHOTOS_DIR / filename
            
            cv2.imwrite(str(filepath), self.current_frame)
            print(f"[CAMERA] Photo saved: {filepath}")
            return str(filepath)

camera = CameraHandler()

# --- IPFS UPLOAD ---
def upload_to_ipfs(file_path):
    """Upload a file to IPFS via the API endpoint or upload2ipfs.sh"""
    import requests
    
    result = {
        'success': False,
        'cid': None,
        'ipfs_url': None,
        'error': None
    }
    
    if not os.path.exists(file_path):
        result['error'] = f"File not found: {file_path}"
        return result
    
    # Try API endpoint first (http://127.0.0.1:54321/api/fileupload)
    API_URL = "http://127.0.0.1:54321"
    
    # Get current player's NPUB
    npub = ""
    current_player = Path(HOME) / ".zen/game/players/.current/.player"
    if current_player.exists():
        player_email = current_player.read_text().strip()
        npub_file = Path(HOME) / f".zen/game/nostr/{player_email}/NPUB"
        if npub_file.exists():
            npub = npub_file.read_text().strip()
    
    try:
        print(f"[IPFS] Uploading {file_path} via API...")
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'image/jpeg')}
            data = {'npub': npub} if npub else {}
            
            response = requests.post(
                f"{API_URL}/api/fileupload",
                files=files,
                data=data,
                timeout=60
            )
        
        if response.status_code == 200:
            resp_json = response.json()
            if resp_json.get('success') or resp_json.get('new_cid'):
                result['success'] = True
                result['cid'] = resp_json.get('new_cid') or resp_json.get('cid')
                result['info_cid'] = resp_json.get('info')
                result['ipfs_url'] = f"https://ipfs.copylaradio.com/ipfs/{result['cid']}"
                print(f"[IPFS] Upload success! CID: {result['cid']}")
                return result
            else:
                result['error'] = resp_json.get('error', 'Unknown error')
        else:
            result['error'] = f"API error: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        print("[IPFS] API not available, trying upload2ipfs.sh...")
    except Exception as e:
        print(f"[IPFS] API error: {e}")
    
    # Fallback: Try upload2ipfs.sh directly
    upload_script_paths = [
        os.path.join(ASTROPORT_PATH, "../UPassport/upload2ipfs.sh"),
        os.path.join(HOME, ".zen/Astroport.ONE/UPassport/upload2ipfs.sh"),
        os.path.join(HOME, "workspace/AAA/UPassport/upload2ipfs.sh"),
    ]
    
    upload_script = None
    for path in upload_script_paths:
        if os.path.exists(path):
            upload_script = path
            break
    
    if upload_script:
        try:
            print(f"[IPFS] Using upload2ipfs.sh: {upload_script}")
            output_json = str(PHOTOS_DIR / f"upload_{datetime.now().strftime('%s')}.json")
            
            cmd = ["bash", upload_script, file_path, output_json]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if proc.returncode == 0 and os.path.exists(output_json):
                with open(output_json, 'r') as f:
                    upload_result = json.load(f)
                    result['success'] = True
                    result['cid'] = upload_result.get('cid')
                    result['info_cid'] = upload_result.get('info')
                    result['ipfs_url'] = f"https://ipfs.copylaradio.com/ipfs/{result['cid']}"
                    print(f"[IPFS] Upload success via script! CID: {result['cid']}")
                os.remove(output_json)
                return result
            else:
                result['error'] = f"upload2ipfs.sh failed: {proc.stderr}"
        except Exception as e:
            result['error'] = f"Script error: {e}"
    
    # Final fallback: Direct IPFS add
    try:
        print("[IPFS] Trying direct IPFS add...")
        cmd = ["ipfs", "add", "-q", file_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if proc.returncode == 0 and proc.stdout.strip():
            cid = proc.stdout.strip()
            result['success'] = True
            result['cid'] = cid
            result['ipfs_url'] = f"https://ipfs.copylaradio.com/ipfs/{cid}"
            print(f"[IPFS] Direct add success! CID: {cid}")
            return result
    except Exception as e:
        result['error'] = f"Direct IPFS add failed: {e}"
    
    print(f"[IPFS] Upload failed: {result['error']}")
    return result

# --- CAPTAIN & NOSTR POSTING ---
def get_captain_keyfile():
    """Get captain's NOSTR keyfile path"""
    # Try to find CAPTAINEMAIL
    captain_email = None
    
    # Check .current player
    current_player = Path(HOME) / ".zen/game/players/.current/.player"
    if current_player.exists():
        captain_email = current_player.read_text().strip()
    
    if captain_email:
        keyfile = Path(HOME) / f".zen/game/nostr/{captain_email}/.secret.nostr"
        if keyfile.exists():
            return str(keyfile)
    
    # Fallback: search in nostr directory
    nostr_dir = Path(HOME) / ".zen/game/nostr"
    if nostr_dir.exists():
        for email_dir in nostr_dir.iterdir():
            if email_dir.is_dir() and '@' in email_dir.name:
                keyfile = email_dir / ".secret.nostr"
                if keyfile.exists():
                    return str(keyfile)
    
    return None

def post_photo_to_nostr(photo_path, message="📸 Photo from UPlanet Vitrine Interactive", ipfs_url=None):
    """Post photo to Nostr via captain's account"""
    keyfile = get_captain_keyfile()
    
    if not keyfile:
        print("[NOSTR] No captain keyfile found")
        return False
    
    if not os.path.exists(NOSTR_SEND_SCRIPT):
        print(f"[NOSTR] Script not found: {NOSTR_SEND_SCRIPT}")
        return False
    
    # Build message with IPFS URL if available
    if ipfs_url:
        full_message = f"{message}\n\n{ipfs_url}"
    else:
        full_message = f"{message}\n\n🖼️ Captured: {os.path.basename(photo_path)}"
    
    try:
        cmd = [
            "python3", NOSTR_SEND_SCRIPT,
            "--keyfile", keyfile,
            "--content", full_message
        ]
        
        # Add image tag if we have IPFS URL (for NIP-94 style)
        if ipfs_url:
            # Add imeta tag for the image
            tags_json = json.dumps([["imeta", f"url {ipfs_url}", "m image/jpeg"]])
            cmd.extend(["--tags", tags_json])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"[NOSTR] Photo message posted successfully{' with IPFS URL' if ipfs_url else ''}")
            return True
        else:
            print(f"[NOSTR] Post failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[NOSTR] Error posting: {e}")
        return False

def generate_qr_code(url="http://127.0.0.1:54321/g1"):
    """Generate QR code image as base64"""
    if not HAS_QRCODE:
        return None
    
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# --- FLASK ROUTES ---

@app.route('/')
def index():
    """Main carousel page"""
    return render_template('shop_carousel.html')

@app.route('/api/events')
def api_events():
    """Get Nostr events"""
    events = nostr_feed.get_events()
    return jsonify({
        'events': events,
        'count': len(events),
        'loading': nostr_feed.loading,
        'last_refresh': nostr_feed.last_refresh
    })

@app.route('/api/gesture')
def api_gesture():
    """Get current gesture state"""
    current_time = time.time()
    
    with gesture_state.lock:
        # Calculate open hand progress (0-1)
        open_hand_progress = 0
        if gesture_state.open_hand_start > 0:
            elapsed = current_time - gesture_state.open_hand_start
            open_hand_progress = min(elapsed / OPEN_HAND_HOLD_TIME, 1.0)
        
        # Calculate thumbs up progress (0-1)
        thumbs_up_progress = 0
        if gesture_state.thumbs_up_start > 0:
            elapsed = current_time - gesture_state.thumbs_up_start
            thumbs_up_progress = min(elapsed / THUMBS_UP_HOLD_TIME, 1.0)
        
        # Calculate time until dark mode
        time_until_dark = 0
        if gesture_state.light_mode and gesture_state.last_hand_seen > 0 and not gesture_state.hand_detected:
            elapsed_since_hand = current_time - gesture_state.last_hand_seen
            time_until_dark = max(0, DARK_MODE_TIMEOUT - elapsed_since_hand)
        
        state = {
            'hand_detected': gesture_state.hand_detected,
            'hand_x': gesture_state.hand_x,
            'hand_y': gesture_state.hand_y,
            'fingers_open': gesture_state.fingers_open,
            'is_open_hand': gesture_state.is_open_hand,
            'is_thumbs_up': gesture_state.is_thumbs_up,
            'is_fist': gesture_state.is_fist,
            'gesture_name': gesture_state.gesture_name,
            'action': gesture_state.action,
            'current_index': gesture_state.current_index,
            'show_detail': gesture_state.show_detail,
            'detail_opened': gesture_state.detail_opened,
            'show_qr': gesture_state.show_qr,
            'qr_start_time': gesture_state.qr_start_time,
            'open_hand_progress': open_hand_progress,
            'thumbs_up_progress': thumbs_up_progress,
            'light_mode': gesture_state.light_mode,
            'time_until_dark': time_until_dark
        }
        
        # Reset action after reading
        if gesture_state.action in ['nav_left', 'nav_right', 'capture', 'detail', 'detail_close']:
            gesture_state.action = 'idle'
    
    return jsonify(state)

@app.route('/api/profile/<pubkey>')
def api_profile(pubkey):
    """Get profile for a specific pubkey"""
    profile = nostr_feed.get_profile(pubkey)
    return jsonify({
        'pubkey': pubkey,
        'profile': profile,
        'found': bool(profile)
    })

@app.route('/api/capture', methods=['POST'])
def api_capture():
    """Capture photo, upload to IPFS, and post to Nostr"""
    photo_path = camera.capture_photo()
    
    if not photo_path:
        return jsonify({'success': False, 'error': 'Failed to capture photo'})
    
    # Upload to IPFS
    print(f"[CAPTURE] Uploading photo to IPFS: {photo_path}")
    ipfs_result = upload_to_ipfs(photo_path)
    
    ipfs_url = None
    ipfs_cid = None
    
    if ipfs_result['success']:
        ipfs_cid = ipfs_result['cid']
        ipfs_url = ipfs_result['ipfs_url']
        print(f"[CAPTURE] IPFS upload success: {ipfs_url}")
    else:
        print(f"[CAPTURE] IPFS upload failed: {ipfs_result['error']}")
    
    # Post to Nostr (with IPFS URL if available)
    posted = post_photo_to_nostr(photo_path, ipfs_url=ipfs_url)
    
    # Generate QR code
    qr_data = generate_qr_code()
    
    with gesture_state.lock:
        gesture_state.show_qr = True
        gesture_state.qr_start_time = time.time()
        gesture_state.last_photo_path = photo_path
    
    return jsonify({
        'success': True,
        'photo_path': photo_path,
        'ipfs_cid': ipfs_cid,
        'ipfs_url': ipfs_url,
        'posted': posted,
        'qr_code': qr_data,
        'qr_url': 'http://127.0.0.1:54321/g1'
    })

@app.route('/api/qr')
def api_qr():
    """Get QR code for G1 link"""
    qr_data = generate_qr_code()
    return jsonify({
        'qr_code': qr_data,
        'url': 'http://127.0.0.1:54321/g1'
    })

@app.route('/api/set_index', methods=['POST'])
def api_set_index():
    """Set current message index"""
    data = request.get_json() or {}
    new_index = data.get('index', 0)
    
    max_index = nostr_feed.count() - 1
    new_index = max(0, min(new_index, max_index))
    
    with gesture_state.lock:
        gesture_state.current_index = new_index
    
    return jsonify({'success': True, 'index': new_index})

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    def generate():
        while True:
            frame = camera.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.033)  # ~30 fps
    
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/photos/<filename>')
def serve_photo(filename):
    """Serve captured photos"""
    return send_from_directory(str(PHOTOS_DIR), filename)

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory(str(STATIC_DIR), filename)

# --- MAIN ---
def main():
    parser = argparse.ArgumentParser(description='UPlanet Vitrine Interactive')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help=f'Port (default: {DEFAULT_PORT})')
    parser.add_argument('--camera', type=int, default=DEFAULT_CAMERA, help=f'Camera index (default: {DEFAULT_CAMERA})')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    args = parser.parse_args()
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   🌍 UPlanet Vitrine Interactive                             ║
    ║   ─────────────────────────────────────────────────────────  ║
    ║                                                              ║
    ║   📡 Nostr Message Carousel with Gesture Control             ║
    ║   🖐️  Hand gestures for "Minority Report" navigation         ║
    ║   📷 Thumbs up to capture & post photos                      ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Start camera
    camera.camera_index = args.camera
    if not camera.start():
        print("[ERROR] Failed to start camera. Check connection.")
        sys.exit(1)
    
    print(f"[SERVER] Starting on http://127.0.0.1:{args.port}")
    print(f"[SERVER] Webcam feed: http://127.0.0.1:{args.port}/video_feed")
    print(f"[SERVER] Press Ctrl+C to stop")
    
    try:
        app.run(host='0.0.0.0', port=args.port, debug=args.debug, threaded=True)
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
    finally:
        camera.stop()

if __name__ == '__main__':
    main()

