#!/usr/bin/env python3
"""
Face Recognition Module for UPlanet Vitrine Interactive

This module handles:
- Face detection in captured photos
- Face embedding extraction
- User database management
- Face matching and recognition

Dependencies:
    pip install face_recognition dlib numpy opencv-python

Alternative (lighter, uses MediaPipe):
    pip install mediapipe opencv-python scikit-learn

Author: CopyLaRadio - UPlanet
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
import cv2

# Try to import face_recognition (preferred for recognition)
try:
    import face_recognition
    HAS_FACE_RECOGNITION = True
    print("[FACE] ✅ face_recognition library available")
except ImportError:
    HAS_FACE_RECOGNITION = False
    print("[FACE] face_recognition not installed. pip install face_recognition dlib")

# MediaPipe for fallback (but has known issues with FaceDetection in some versions)
# We only use it if face_recognition is not available
HAS_MEDIAPIPE = False
if not HAS_FACE_RECOGNITION:
    try:
        import mediapipe as mp
        HAS_MEDIAPIPE = True
        print("[FACE] Using MediaPipe as fallback for face detection")
    except ImportError:
        HAS_MEDIAPIPE = False
else:
    mp = None  # Don't use MediaPipe if face_recognition is available

# --- CONFIGURATION ---
FACES_DIR = Path(__file__).parent / "faces"
EMBEDDINGS_FILE = FACES_DIR / "embeddings.json"
UNKNOWN_DIR = FACES_DIR / "unknown"
USERS_DIR = FACES_DIR / "users"

# Recognition thresholds
FACE_MATCH_THRESHOLD = 0.6  # Lower = stricter matching (0.6 is good default)
MIN_FACE_SIZE = 50  # Minimum face size in pixels

# Ensure directories exist
FACES_DIR.mkdir(exist_ok=True)
UNKNOWN_DIR.mkdir(exist_ok=True)
USERS_DIR.mkdir(exist_ok=True)


class FaceDatabase:
    """Manages the face embeddings database"""
    
    def __init__(self):
        self.embeddings: Dict[str, dict] = {}  # user_id -> {embeddings, metadata}
        self.load()
    
    def load(self):
        """Load embeddings from JSON file"""
        if EMBEDDINGS_FILE.exists():
            try:
                with open(EMBEDDINGS_FILE, 'r') as f:
                    data = json.load(f)
                    # Convert lists back to numpy arrays
                    for user_id, user_data in data.items():
                        self.embeddings[user_id] = {
                            'embeddings': [np.array(e) for e in user_data.get('embeddings', [])],
                            'name': user_data.get('name', ''),
                            'first_seen': user_data.get('first_seen', ''),
                            'last_seen': user_data.get('last_seen', ''),
                            'visit_count': user_data.get('visit_count', 0),
                            'photos': user_data.get('photos', [])
                        }
                print(f"[FACE] Loaded {len(self.embeddings)} users from database")
            except Exception as e:
                print(f"[FACE] Error loading database: {e}")
                self.embeddings = {}
        else:
            self.embeddings = {}
    
    def save(self):
        """Save embeddings to JSON file"""
        try:
            data = {}
            for user_id, user_data in self.embeddings.items():
                data[user_id] = {
                    'embeddings': [e.tolist() for e in user_data.get('embeddings', [])],
                    'name': user_data.get('name', ''),
                    'first_seen': user_data.get('first_seen', ''),
                    'last_seen': user_data.get('last_seen', ''),
                    'visit_count': user_data.get('visit_count', 0),
                    'photos': user_data.get('photos', [])
                }
            
            with open(EMBEDDINGS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"[FACE] Saved {len(self.embeddings)} users to database")
        except Exception as e:
            print(f"[FACE] Error saving database: {e}")
    
    def add_user(self, user_id: str, embedding: np.ndarray, photo_path: str, name: str = "") -> dict:
        """Add a new user or update existing"""
        now = datetime.now().isoformat()
        
        if user_id not in self.embeddings:
            self.embeddings[user_id] = {
                'embeddings': [embedding],
                'name': name,
                'first_seen': now,
                'last_seen': now,
                'visit_count': 1,
                'photos': [photo_path]
            }
        else:
            # Update existing user
            self.embeddings[user_id]['embeddings'].append(embedding)
            self.embeddings[user_id]['last_seen'] = now
            self.embeddings[user_id]['visit_count'] += 1
            self.embeddings[user_id]['photos'].append(photo_path)
            if name and not self.embeddings[user_id]['name']:
                self.embeddings[user_id]['name'] = name
        
        self.save()
        return self.embeddings[user_id]
    
    def get_all_embeddings(self) -> List[Tuple[str, np.ndarray]]:
        """Get all embeddings as (user_id, embedding) pairs"""
        result = []
        for user_id, user_data in self.embeddings.items():
            for embedding in user_data.get('embeddings', []):
                result.append((user_id, embedding))
        return result
    
    def get_user(self, user_id: str) -> Optional[dict]:
        """Get user data by ID"""
        return self.embeddings.get(user_id)
    
    def set_user_name(self, user_id: str, name: str) -> bool:
        """Set a user's name"""
        if user_id in self.embeddings:
            self.embeddings[user_id]['name'] = name
            self.save()
            return True
        return False
    
    def get_stats(self) -> dict:
        """Get database statistics"""
        total_embeddings = sum(
            len(u.get('embeddings', [])) for u in self.embeddings.values()
        )
        return {
            'total_users': len(self.embeddings),
            'total_embeddings': total_embeddings,
            'named_users': sum(1 for u in self.embeddings.values() if u.get('name')),
        }


class FaceRecognizer:
    """Handles face detection and recognition"""
    
    def __init__(self):
        self.database = FaceDatabase()
        self.face_detector = None
        self.mp_face = None
        
        # Initialize MediaPipe face detection as fallback (only if face_recognition not available)
        if not HAS_FACE_RECOGNITION and HAS_MEDIAPIPE:
            try:
                self.mp_face = mp.solutions.face_detection
                self.face_detector = self.mp_face.FaceDetection(
                    model_selection=1,  # 0=short-range (2m), 1=full-range (5m)
                    min_detection_confidence=0.5
                )
                print("[FACE] MediaPipe face detector initialized")
            except Exception as e:
                print(f"[FACE] MediaPipe FaceDetection failed: {e}")
                self.face_detector = None
        
        print(f"[FACE] Recognizer initialized. face_recognition: {HAS_FACE_RECOGNITION}, mediapipe_fallback: {self.face_detector is not None}")
    
    def detect_faces(self, image_path: str) -> List[dict]:
        """
        Detect faces in an image.
        Returns list of {box: (top, right, bottom, left), embedding: np.array}
        """
        if not os.path.exists(image_path):
            print(f"[FACE] Image not found: {image_path}")
            return []
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print(f"[FACE] Could not read image: {image_path}")
            return []
        
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        faces = []
        
        if HAS_FACE_RECOGNITION:
            # Use face_recognition library (best for recognition)
            face_locations = face_recognition.face_locations(rgb_image, model="hog")
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            
            for location, encoding in zip(face_locations, face_encodings):
                top, right, bottom, left = location
                # Filter small faces
                if (bottom - top) >= MIN_FACE_SIZE and (right - left) >= MIN_FACE_SIZE:
                    faces.append({
                        'box': (top, right, bottom, left),
                        'embedding': encoding,
                        'confidence': 1.0  # face_recognition doesn't provide confidence
                    })
        
        elif self.face_detector and self.mp_face:
            # Fallback to MediaPipe (detection only, no embeddings)
            results = self.face_detector.process(rgb_image)
            
            if results.detections:
                h, w = image.shape[:2]
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    left = int(bbox.xmin * w)
                    top = int(bbox.ymin * h)
                    right = int((bbox.xmin + bbox.width) * w)
                    bottom = int((bbox.ymin + bbox.height) * h)
                    
                    # Filter small faces
                    if (bottom - top) >= MIN_FACE_SIZE and (right - left) >= MIN_FACE_SIZE:
                        # Extract face region for simple embedding (histogram-based)
                        face_img = rgb_image[top:bottom, left:right]
                        embedding = self._simple_embedding(face_img)
                        
                        faces.append({
                            'box': (top, right, bottom, left),
                            'embedding': embedding,
                            'confidence': detection.score[0] if detection.score else 0.5
                        })
        
        print(f"[FACE] Detected {len(faces)} faces in {os.path.basename(image_path)}")
        return faces
    
    def _simple_embedding(self, face_image: np.ndarray) -> np.ndarray:
        """
        Create a simple embedding when face_recognition is not available.
        Uses histogram features (less accurate but functional).
        """
        # Resize to standard size
        face_resized = cv2.resize(face_image, (128, 128))
        
        # Convert to grayscale
        gray = cv2.cvtColor(face_resized, cv2.COLOR_RGB2GRAY)
        
        # Compute histogram
        hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
        hist = hist.flatten() / hist.sum()  # Normalize
        
        # Add some spatial information
        # Divide into 4x4 grid and compute local histograms
        h, w = gray.shape
        grid_size = 4
        cell_h, cell_w = h // grid_size, w // grid_size
        
        spatial_features = []
        for i in range(grid_size):
            for j in range(grid_size):
                cell = gray[i*cell_h:(i+1)*cell_h, j*cell_w:(j+1)*cell_w]
                cell_hist = cv2.calcHist([cell], [0], None, [16], [0, 256])
                cell_hist = cell_hist.flatten() / (cell_hist.sum() + 1e-6)
                spatial_features.extend(cell_hist)
        
        # Combine features
        embedding = np.concatenate([hist, np.array(spatial_features)])
        return embedding
    
    def match_face(self, embedding: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Match a face embedding against the database.
        Returns (user_id, distance) or (None, 0) if no match.
        """
        all_embeddings = self.database.get_all_embeddings()
        
        if not all_embeddings:
            return None, 0.0
        
        if HAS_FACE_RECOGNITION:
            # Use face_recognition's compare function
            known_embeddings = [e for _, e in all_embeddings]
            user_ids = [uid for uid, _ in all_embeddings]
            
            distances = face_recognition.face_distance(known_embeddings, embedding)
            
            if len(distances) > 0:
                min_idx = np.argmin(distances)
                min_distance = distances[min_idx]
                
                if min_distance < FACE_MATCH_THRESHOLD:
                    return user_ids[min_idx], 1 - min_distance  # Convert to similarity
        
        else:
            # Simple histogram comparison
            best_match = None
            best_similarity = 0
            
            for user_id, known_embedding in all_embeddings:
                # Use histogram intersection or correlation
                similarity = cv2.compareHist(
                    embedding.astype(np.float32),
                    known_embedding.astype(np.float32),
                    cv2.HISTCMP_CORREL
                )
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = user_id
            
            if best_similarity > 0.7:  # Threshold for histogram matching
                return best_match, best_similarity
        
        return None, 0.0
    
    def process_photo(self, photo_path: str) -> List[dict]:
        """
        Process a photo: detect faces, match against database, save new faces.
        Returns list of results for each detected face.
        """
        results = []
        faces = self.detect_faces(photo_path)
        
        if not faces:
            print(f"[FACE] No faces found in {photo_path}")
            return results
        
        # Load image to extract face crops
        image = cv2.imread(photo_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for i, face in enumerate(faces):
            top, right, bottom, left = face['box']
            embedding = face['embedding']
            
            # Try to match against database
            matched_user_id, similarity = self.match_face(embedding)
            
            # Extract face image
            face_img = image[top:bottom, left:right]
            
            if matched_user_id:
                # Known user - update their record
                user_dir = USERS_DIR / matched_user_id
                user_dir.mkdir(exist_ok=True)
                
                face_filename = f"face_{timestamp}_{i}.jpg"
                face_path = user_dir / face_filename
                cv2.imwrite(str(face_path), face_img)
                
                # Update database
                user_data = self.database.add_user(
                    matched_user_id, 
                    embedding, 
                    str(face_path)
                )
                
                results.append({
                    'status': 'recognized',
                    'user_id': matched_user_id,
                    'name': user_data.get('name', ''),
                    'similarity': similarity,
                    'visit_count': user_data.get('visit_count', 1),
                    'box': face['box'],
                    'face_path': str(face_path)
                })
                
                print(f"[FACE] Recognized user {matched_user_id} (visits: {user_data.get('visit_count')})")
            
            else:
                # New user - create new entry
                new_user_id = f"user_{uuid.uuid4().hex[:8]}"
                user_dir = USERS_DIR / new_user_id
                user_dir.mkdir(exist_ok=True)
                
                face_filename = f"face_{timestamp}_{i}.jpg"
                face_path = user_dir / face_filename
                cv2.imwrite(str(face_path), face_img)
                
                # Add to database
                user_data = self.database.add_user(
                    new_user_id,
                    embedding,
                    str(face_path)
                )
                
                # Also save to unknown for review
                unknown_path = UNKNOWN_DIR / f"{new_user_id}_{face_filename}"
                cv2.imwrite(str(unknown_path), face_img)
                
                results.append({
                    'status': 'new',
                    'user_id': new_user_id,
                    'name': '',
                    'similarity': 0,
                    'visit_count': 1,
                    'box': face['box'],
                    'face_path': str(face_path)
                })
                
                print(f"[FACE] New user registered: {new_user_id}")
        
        return results
    
    def annotate_image(self, image_path: str, output_path: str = None) -> str:
        """
        Create an annotated copy of the image with face boxes and labels.
        Returns path to annotated image.
        """
        if output_path is None:
            base, ext = os.path.splitext(image_path)
            output_path = f"{base}_annotated{ext}"
        
        image = cv2.imread(image_path)
        if image is None:
            return None
        
        faces = self.detect_faces(image_path)
        
        for face in faces:
            top, right, bottom, left = face['box']
            
            # Match face
            matched_user_id, similarity = self.match_face(face['embedding'])
            
            if matched_user_id:
                user = self.database.get_user(matched_user_id)
                name = user.get('name') if user else ''
                label = name if name else matched_user_id[:12]
                color = (0, 255, 0)  # Green for known
            else:
                label = "New visitor"
                color = (0, 165, 255)  # Orange for unknown
            
            # Draw box
            cv2.rectangle(image, (left, top), (right, bottom), color, 2)
            
            # Draw label background
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(image, 
                         (left, top - label_size[1] - 10),
                         (left + label_size[0] + 10, top),
                         color, -1)
            
            # Draw label text
            cv2.putText(image, label, (left + 5, top - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        cv2.imwrite(output_path, image)
        return output_path
    
    def get_stats(self) -> dict:
        """Get recognition statistics"""
        return self.database.get_stats()
    
    def get_all_users(self) -> List[dict]:
        """Get all users with their metadata"""
        users = []
        for user_id, data in self.database.embeddings.items():
            users.append({
                'user_id': user_id,
                'name': data.get('name', ''),
                'first_seen': data.get('first_seen', ''),
                'last_seen': data.get('last_seen', ''),
                'visit_count': data.get('visit_count', 0),
                'photo_count': len(data.get('photos', []))
            })
        return sorted(users, key=lambda x: x.get('last_seen', ''), reverse=True)


# --- BATCH PROCESSING ---
def process_existing_photos(photos_dir: str = None):
    """Process all existing photos to build initial database"""
    if photos_dir is None:
        photos_dir = Path(__file__).parent / "photos"
    else:
        photos_dir = Path(photos_dir)
    
    recognizer = FaceRecognizer()
    
    photo_files = sorted(photos_dir.glob("*.jpg"))
    print(f"[FACE] Processing {len(photo_files)} existing photos...")
    
    total_faces = 0
    for photo_path in photo_files:
        results = recognizer.process_photo(str(photo_path))
        total_faces += len(results)
    
    stats = recognizer.get_stats()
    print(f"\n[FACE] Batch processing complete!")
    print(f"  - Total faces detected: {total_faces}")
    print(f"  - Unique users: {stats['total_users']}")
    print(f"  - Total embeddings: {stats['total_embeddings']}")
    
    return stats


# --- CLI ---
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Face Recognition Module")
    parser.add_argument("--batch", action="store_true", help="Process all existing photos")
    parser.add_argument("--photo", type=str, help="Process a single photo")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--users", action="store_true", help="List all users")
    parser.add_argument("--name", nargs=2, metavar=("USER_ID", "NAME"), help="Set user name")
    
    args = parser.parse_args()
    
    recognizer = FaceRecognizer()
    
    if args.batch:
        process_existing_photos()
    
    elif args.photo:
        results = recognizer.process_photo(args.photo)
        print(json.dumps(results, indent=2, default=str))
    
    elif args.stats:
        stats = recognizer.get_stats()
        print(json.dumps(stats, indent=2))
    
    elif args.users:
        users = recognizer.get_all_users()
        for user in users:
            print(f"  {user['user_id']}: {user.get('name', '(unnamed)')} - {user['visit_count']} visits")
    
    elif args.name:
        user_id, name = args.name
        if recognizer.database.set_user_name(user_id, name):
            print(f"Set name '{name}' for user {user_id}")
        else:
            print(f"User {user_id} not found")
    
    else:
        parser.print_help()

