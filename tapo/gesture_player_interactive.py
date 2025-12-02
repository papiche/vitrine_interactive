#!/usr/bin/env python3
import cv2
import mediapipe as mp
import os
import time
import pyautogui
import numpy as np

# --- Configuration ---
VIDEO_FILE = './UPlanet___Un_Meilleur_Internet.mp4'
WEBCAM_INDEX = 0
WINDOW_NAME_VIDEO = 'Lecteur Video'
WINDOW_NAME_CONTROL = 'Controle'

# --- Vérification du fichier vidéo ---
if not os.path.exists(VIDEO_FILE):
    print(f"Erreur : Le fichier vidéo '{VIDEO_FILE}' n'a pas été trouvé.")
    exit()

# --- Initialisation ---
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(static_image_mode=False,
                                max_num_hands=1,
                                min_detection_confidence=0.7,
                                min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# --- Fonctions de détection de gestes ---
def get_gesture(hand_landmarks):
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

    if all(fingers_up.values()): return 'open'
    if not any(fingers_up.values()): return 'closed'
    if fingers_up['index'] and not fingers_up['middle'] and not fingers_up['ring'] and not fingers_up['pinky']:
        return 'pointing'
    return None

# --- Programme principal ---
cap_webcam = cv2.VideoCapture(WEBCAM_INDEX)
cap_video = cv2.VideoCapture(VIDEO_FILE)

is_playing = False
move_mode = False
last_video_frame = None
last_gesture_time = 0
gesture_cooldown = 0.5

video_w, video_h = 0, 0
is_control_window_positioned = False

cv2.namedWindow(WINDOW_NAME_CONTROL)
cv2.namedWindow(WINDOW_NAME_VIDEO)
window_x, window_y = 100, 100
cv2.moveWindow(WINDOW_NAME_VIDEO, window_x, window_y)

print("Lecteur vidéo interactif démarré.")
print("Pressez 'q' pour quitter.")

while cap_webcam.isOpened():
    ret_cam, cam_frame = cap_webcam.read()
    if not ret_cam: break
    
    if not is_control_window_positioned:
        frame_h, frame_w, _ = cam_frame.shape
        control_x = SCREEN_WIDTH - frame_w - 40
        control_y = SCREEN_HEIGHT - frame_h - 60
        cv2.moveWindow(WINDOW_NAME_CONTROL, control_x, control_y)
        is_control_window_positioned = True
    
    cam_frame = cv2.flip(cam_frame, 1)
    rgb_frame = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2RGB)
    results = hands_detector.process(rgb_frame)

    current_time = time.time()
    if results.multi_hand_landmarks:
        hand_landmarks = results.multi_hand_landmarks[0]
        mp_drawing.draw_landmarks(cam_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
        
        if (current_time - last_gesture_time) > gesture_cooldown:
            gesture = get_gesture(hand_landmarks)
            if gesture == 'pointing':
                if not move_mode: print("Mode DÉPLACEMENT activé"); move_mode = True; last_gesture_time = current_time
            elif gesture == 'open':
                if move_mode: print("Mode DÉPLACEMENT désactivé"); move_mode = False
                is_playing = True; last_gesture_time = current_time
            elif gesture == 'closed' and not move_mode:
                is_playing = False; last_gesture_time = current_time

        if move_mode and video_w > 0:
            # --- MODIFICATIONS APPLIQUÉES ICI ---
            
            # 1. On utilise l'extrémité de l'index comme point de contrôle
            finger_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
            
            # 2. On calcule la zone de déplacement maximale
            max_x = SCREEN_WIDTH - video_w
            max_y = SCREEN_HEIGHT - video_h

            # 3. Mapping avec le doigt et l'inversion horizontale
            target_x = np.interp(finger_tip.x, (0.0, 1.0), (0, max_x))
            target_y = np.interp(finger_tip.y, (0.0, 1.0), (0, max_y))
            
            # NOTE: Pour un mouvement "miroir" NATUREL (main gauche -> fenêtre gauche),
            # remplacez la ligne `target_x` par celle-ci :
            # target_x = np.interp(1 - finger_tip.x, (0.0, 1.0), (0, max_x))
            
            # 4. Affectation directe pour un contrôle instantané
            window_x = int(target_x)
            window_y = int(target_y)
            
            cv2.moveWindow(WINDOW_NAME_VIDEO, window_x, window_y)

    status_text = "MOVING" if move_mode else ("PLAYING" if is_playing else "PAUSED")
    text_color = (0, 165, 255) if move_mode else ((0, 255, 0) if is_playing else (0, 0, 255))
    cv2.putText(cam_frame, status_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, text_color, 3)
    cv2.imshow(WINDOW_NAME_CONTROL, cam_frame)

    if is_playing:
        ret_vid, video_frame = cap_video.read()
        if not ret_vid: cap_video.set(cv2.CAP_PROP_POS_FRAMES, 0); ret_vid, video_frame = cap_video.read()
        if ret_vid: 
            if video_w == 0:
                video_h, video_w, _ = video_frame.shape
            last_video_frame = video_frame

    if last_video_frame is not None:
        cv2.imshow(WINDOW_NAME_VIDEO, last_video_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

print("Arrêt du script.")
cap_webcam.release()
cap_video.release()
cv2.destroyAllWindows()