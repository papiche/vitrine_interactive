#!/usr/bin/env python3
import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import math
import argparse

# --- Configuration via la Ligne de Commande (CLI) ---
parser = argparse.ArgumentParser(
    description="Contrôle de la souris ou détection de gestes via la main avec MediaPipe.",
    formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument(
    '-s', '--source',
    type=str,
    default='rtsp://chapichapo:chapichapo@192.168.1.16:554/stream2',
    help="Source de la vidéo.\n"
         "  - Pour la webcam locale, utilisez '0'.\n"
         "  - (défaut: le flux RTSP de la caméra Tapo)"
)
parser.add_argument(
    '-m', '--mode',
    type=str,
    default='mouse',
    choices=['open', 'click', 'mouse'],
    help="Définit le mode de fonctionnement du script.\n"
         "  - 'open': Détecte si la main est ouverte.\n"
         "  - 'click': Détecte le geste de clic sans bouger la souris.\n"
         "  - 'mouse': Contrôle complet de la souris (défaut)."
)
args = parser.parse_args()

# --- Initialisation ---
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
SMOOTHING_FACTOR = 7
CLICK_DISTANCE_THRESHOLD = 40

mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(static_image_mode=False,
                                max_num_hands=1,
                                min_detection_confidence=0.7,
                                min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# Variables pour le lissage du mouvement
mouse_x, mouse_y = 0, 0

# --- Fonctions Utilitaires ---
def is_hand_open(hand_landmarks):
    """Vérifie si la main est ouverte en se basant sur la position des doigts."""
    finger_tips = [
        (mp_hands.HandLandmark.THUMB_TIP, mp_hands.HandLandmark.THUMB_IP),
        (mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.INDEX_FINGER_PIP),
        (mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP),
        (mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_PIP),
        (mp_hands.HandLandmark.PINKY_TIP, mp_hands.HandLandmark.PINKY_PIP)
    ]
    fingers_open = 0
    # Pouce
    if hand_landmarks.landmark[finger_tips[0][0]].x < hand_landmarks.landmark[finger_tips[0][1]].x:
        fingers_open += 1
    # Autres doigts
    for tip_landmark, pip_landmark in finger_tips[1:]:
        if hand_landmarks.landmark[tip_landmark].y < hand_landmarks.landmark[pip_landmark].y:
            fingers_open += 1
    return fingers_open == 5

# --- Programme principal ---
capture_source = args.source
if args.source.isdigit():
    capture_source = int(args.source)

cap = cv2.VideoCapture(capture_source)

if not cap.isOpened():
    print(f"Erreur: Impossible de se connecter à la source vidéo : {args.source}")
    exit()

print(f"Démarrage depuis la source '{args.source}' en mode '{args.mode}'.")
print("Pressez 'q' sur la fenêtre pour quitter.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame_height, frame_width, _ = frame.shape
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb_frame = cv2.flip(rgb_frame, 1)

    results = hands_detector.process(rgb_frame)
    display_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)

    if results.multi_hand_landmarks:
        hand_landmarks = results.multi_hand_landmarks[0]
        
        # --- Logique basée sur le MODE choisi ---

        # 1. MODE 'OPEN' : Détection de main ouverte
        if args.mode == 'open':
            if is_hand_open(hand_landmarks):
                cv2.putText(display_frame, "Main ouverte", (50, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # 2. MODE 'CLICK' ou 'MOUSE' : Nécessite le calcul de la distance
        elif args.mode in ['click', 'mouse']:
            thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]
            index_finger_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
            
            thumb_px = (thumb_tip.x * frame_width, thumb_tip.y * frame_height)
            index_px = (index_finger_tip.x * frame_width, index_finger_tip.y * frame_height)
            distance = math.sqrt((thumb_px[0] - index_px[0])**2 + (thumb_px[1] - index_px[1])**2)
            
            # --- Mouvement de la souris (uniquement en mode 'mouse') ---
            if args.mode == 'mouse':
                target_screen_x = np.interp(index_finger_tip.x, (0.0, 1.0), (0, SCREEN_WIDTH))
                target_screen_y = np.interp(index_finger_tip.y, (0.0, 1.0), (0, SCREEN_HEIGHT))
                mouse_x += (target_screen_x - mouse_x) / SMOOTHING_FACTOR
                mouse_y += (target_screen_y - mouse_y) / SMOOTHING_FACTOR
                pyautogui.moveTo(mouse_x, mouse_y)
                cv2.circle(display_frame, (int(index_px[0]), int(index_px[1])), 10, (0, 255, 0), -1)

            # --- Détection du clic (dans les deux modes 'click' et 'mouse') ---
            cv2.line(display_frame, (int(thumb_px[0]), int(thumb_px[1])), (int(index_px[0]), int(index_px[1])), (255, 0, 0), 3)
            if distance < CLICK_DISTANCE_THRESHOLD:
                cv2.line(display_frame, (int(thumb_px[0]), int(thumb_px[1])), (int(index_px[0]), int(index_px[1])), (0, 255, 0), 3)
                cv2.circle(display_frame, (int(index_px[0]), int(index_px[1])), 15, (0, 0, 255), -1)
                pyautogui.click()
                pyautogui.sleep(0.2) 
                if args.mode == 'click':
                     cv2.putText(display_frame, "CLIC !", (int(index_px[0]), int(index_px[1]) - 20), 
                                 cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # Dessiner les landmarks dans tous les cas pour un retour visuel
        mp_drawing.draw_landmarks(display_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

    cv2.imshow('Controle Gestuel', display_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- Nettoyage ---
print("Arrêt du script.")
cap.release()
cv2.destroyAllWindows()
hands_detector.close()